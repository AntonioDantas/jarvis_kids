"""
Servidor local da interface gráfica (só biblioteca padrão do Python).

Segurança:
* escuta apenas em 127.0.0.1 (nada sai do computador e ninguém da rede acessa);
* a API exige o token secreto da sessão (vai no endereço que abre a janela);
* confere o cabeçalho Host (bloqueia "DNS rebinding") e a Origem dos envios;
* política de conteúdo rígida: a página só carrega arquivos do próprio Jarvis.
"""

from __future__ import annotations

import json
import mimetypes
import queue
import re
import sys
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jarvis.web.ponte import Ponte

PASTA_STATIC = Path(__file__).parent / "static"
PORTA_PADRAO = 8765
ACOES = ("silenciar", "maos_livres_ligar", "maos_livres_desligar")
MAX_CORPO = 16_384
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
TIPOS = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".html": "text/html; charset=utf-8", ".ttf": "font/ttf", ".svg": "image/svg+xml",
         ".json": "application/json", ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8"}


def _data(texto: str) -> date | None:
    try:
        return date.fromisoformat(str(texto)[:10])
    except ValueError:
        return None


class Manipulador(BaseHTTPRequestHandler):
    server: ServidorJarvis
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # silencioso: nada de registro de acessos
        pass

    # ------------------------------------------------------------- utilidades
    @property
    def ponte(self) -> Ponte:
        return self.server.ponte

    def _cabecalhos_seguranca(self) -> None:
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")

    def _json(self, obj, codigo: int = 200) -> None:
        corpo = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self._cabecalhos_seguranca()
        self.end_headers()
        self.wfile.write(corpo)

    def _host_valido(self) -> bool:
        host = self.headers.get("Host", "")
        return host in self.server.hosts_validos

    def _origem_valida(self) -> bool:
        origem = self.headers.get("Origin")
        return origem is None or origem in self.server.origens_validas

    def _token_valido(self, consulta: dict) -> bool:
        token = self.headers.get("X-Jarvis-Token") or (consulta.get("t") or [""])[0]
        return bool(token) and token == self.ponte.token

    def _corpo(self) -> dict | None:
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if tamanho <= 0 or tamanho > MAX_CORPO:
            return None
        if "application/json" not in self.headers.get("Content-Type", ""):
            return None  # formulários de outros sites não conseguem mandar JSON sem permissão (CORS)
        try:
            dados = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return dados if isinstance(dados, dict) else None

    def _preparar(self, exige_token: bool) -> dict | None:
        url = urlparse(self.path)
        consulta = parse_qs(url.query)
        if not self._host_valido():
            self._json({"erro": "host inválido"}, 403)
            return None
        if exige_token and not (self._origem_valida() and self._token_valido(consulta)):
            self._json({"erro": "acesso negado"}, 403)
            return None
        return {"caminho": url.path, "consulta": consulta}

    # ----------------------------------------------------------------- rotas
    def do_GET(self) -> None:
        caminho = urlparse(self.path).path
        req = self._preparar(exige_token=caminho.startswith("/api/"))
        if req is None:
            return
        if caminho == "/api/eventos":
            return self._eventos()
        if caminho == "/api/agenda":
            return self._agenda_listar(req["consulta"])
        if caminho in ("/", "/index.html"):
            return self._arquivo("index.html")
        if caminho.startswith("/static/"):
            return self._arquivo(caminho.removeprefix("/static/"))
        self._json({"erro": "não encontrado"}, 404)

    def do_POST(self) -> None:
        req = self._preparar(exige_token=True)
        if req is None:
            return
        dados = self._corpo()
        if dados is None:
            return self._json({"erro": "pedido inválido"}, 400)
        if req["caminho"] == "/api/responder":
            ok = self.ponte.responder(str(dados.get("id", "")), str(dados.get("valor", ""))[:500])
            return self._json({"ok": ok}, 200 if ok else 409)
        if req["caminho"] == "/api/agenda":
            return self._agenda_adicionar(dados)
        if req["caminho"] == "/api/acao":
            acao = str(dados.get("acao", ""))
            if acao in ACOES and self.ponte.ao_acao:
                self.ponte.ao_acao(acao)
            return self._json({"ok": True})
        self._json({"erro": "não encontrado"}, 404)

    def do_DELETE(self) -> None:
        req = self._preparar(exige_token=True)
        if req is None:
            return
        if req["caminho"] != "/api/agenda":
            return self._json({"erro": "não encontrado"}, 404)
        agenda = self.ponte.agenda
        evento_id = (req["consulta"].get("id") or [""])[0]
        if agenda is None or not re.fullmatch(r"[0-9a-f]{8}", evento_id):
            return self._json({"erro": "compromisso não encontrado"}, 404)
        if not agenda.remover(evento_id):
            return self._json({"erro": "compromisso não encontrado"}, 404)
        self._agenda_mudou()
        self._json({"ok": True})

    # ------------------------------------------------------- arquivos da tela
    def _arquivo(self, relativo: str) -> None:
        alvo = (PASTA_STATIC / relativo).resolve()
        if not alvo.is_file() or PASTA_STATIC.resolve() not in alvo.parents:
            return self._json({"erro": "não encontrado"}, 404)
        corpo = alvo.read_bytes()
        tipo = TIPOS.get(alvo.suffix) or mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self._cabecalhos_seguranca()
        self.end_headers()
        self.wfile.write(corpo)

    # ------------------------------------------------- eventos em tempo real
    def _eventos(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Connection", "keep-alive")
        self._cabecalhos_seguranca()
        self.end_headers()
        fila = self.ponte.conectar()
        try:
            self.wfile.write(b"retry: 1500\n\n")
            self.wfile.flush()
            while not self.server.desligando:
                try:
                    evento = fila.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")  # mantém a conexão viva
                    self.wfile.flush()
                    continue
                dados = json.dumps(evento, ensure_ascii=False, default=str)
                self.wfile.write(f"data: {dados}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            self.ponte.desconectar(fila)
            self.close_connection = True

    # ---------------------------------------------------------------- agenda
    def _agenda_listar(self, consulta: dict) -> None:
        agenda = self.ponte.agenda
        if agenda is None:
            return self._json([])
        hoje = date.today()
        inicio = _data((consulta.get("start") or [""])[0]) or hoje.replace(day=1)
        fim = _data((consulta.get("end") or [""])[0]) or inicio + timedelta(days=42)
        if fim <= inicio or (fim - inicio).days > 120:
            return self._json({"erro": "período inválido"}, 400)
        self._json(agenda.para_calendario(inicio, fim))

    def _agenda_adicionar(self, dados: dict) -> None:
        agenda = self.ponte.agenda
        if agenda is None:
            return self._json({"erro": "Escolha o seu perfil primeiro."}, 409)
        titulo = " ".join(str(dados.get("titulo", "")).split())[:60]
        dia = _data(dados.get("data", ""))
        hora = str(dados.get("hora", "") or "")
        if not titulo or dia is None:
            return self._json({"erro": "Coloque um nome e uma data."}, 400)
        if hora and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hora):
            return self._json({"erro": "Horário inválido."}, 400)
        if self.ponte.verificar_texto:
            problema = self.ponte.verificar_texto(titulo)
            if problema:
                return self._json({"erro": problema}, 422)
        try:
            evento = agenda.adicionar(titulo, dia, hora, str(dados.get("categoria", "outro")),
                                      str(dados.get("repetir", "")))
        except ValueError as exc:
            return self._json({"erro": str(exc)}, 400)
        self._agenda_mudou()
        self._json({"ok": True, "evento": evento})

    def _agenda_mudou(self) -> None:
        self.ponte.emitir("agenda_mudou")
        if self.ponte.ao_mudar_agenda:
            try:
                self.ponte.ao_mudar_agenda()
            except Exception:
                pass


class ServidorJarvis(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, ponte: Ponte, porta: int):
        super().__init__(("127.0.0.1", porta), Manipulador)
        self.ponte = ponte
        self.desligando = False
        porta_real = self.server_address[1]
        self.hosts_validos = {f"127.0.0.1:{porta_real}", f"localhost:{porta_real}"}
        self.origens_validas = {f"http://{h}" for h in self.hosts_validos}

    def handle_error(self, request, client_address) -> None:
        # Janela fechada ou recarregada no meio de um pedido é normal: não enche o terminal de mensagens.
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)

    @property
    def porta(self) -> int:
        return self.server_address[1]

    @property
    def endereco(self) -> str:
        return f"http://127.0.0.1:{self.porta}/?t={self.ponte.token}"

    def desligar(self) -> None:
        self.desligando = True
        self.shutdown()
        self.server_close()


def iniciar_servidor(ponte: Ponte, porta: int = PORTA_PADRAO) -> ServidorJarvis:
    """Liga o servidor numa thread. Se a porta estiver ocupada, tenta as próximas (ou qualquer livre)."""
    ultima_falha: OSError | None = None
    for tentativa in [porta + i for i in range(10)] + [0]:
        try:
            servidor = ServidorJarvis(ponte, tentativa)
            break
        except OSError as exc:
            ultima_falha = exc
    else:
        raise ultima_falha or OSError("sem porta livre")
    threading.Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.3}, daemon=True,
                     name="servidor-jarvis").start()
    return servidor
