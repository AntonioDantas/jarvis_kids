"""
Ponte entre o Jarvis (Python) e a janela futurista (navegador).

* Python -> janela: eventos em tempo real (Server-Sent Events). Um histórico curto é
  reenviado quando a janela recarrega, para nada se perder.
* Janela -> Python: quando o Jarvis faz uma pergunta (``pedir``), a janela mostra o
  controle certo (botões, teclado numérico, PIN...) e devolve a resposta.

Se a janela for fechada, ``pedir`` desiste depois de um tempo e o Jarvis desliga com calma.
"""

from __future__ import annotations

import queue
import secrets
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable

# Só o último de cada um importa (são "estado", não conversa): vão para quem conectar depois.
ESTADOS = {"estado", "carregando", "hud", "lateral", "progresso", "config"}
# Passageiros: não ficam guardados.
PASSAGEIROS = {"nivel_mic", "voz", "abrir_planner", "agenda_mudou", "pedido_fim", "desligado"}
ESPERA_SEM_JANELA_S = 25
ESPERA_PRIMEIRA_JANELA_S = 120


class JanelaFechada(EOFError):
    """A janela do Jarvis foi fechada (tratada como 'tchau')."""


class Ponte:
    def __init__(self) -> None:
        self.token = secrets.token_urlsafe(18)
        self._trava = threading.Lock()
        self._clientes: list[queue.Queue] = []
        self._historico: deque = deque(maxlen=300)
        self._estados: dict[str, dict] = {}
        self._pedido: dict | None = None
        self._ao_responder: Callable[[], None] | None = None
        self._respondido = False
        self._respostas: queue.Queue = queue.Queue()
        self._seq = 0
        self._sem_clientes_desde = time.monotonic()
        self.ja_conectou = False
        self.janela_viva: Callable[[], bool] | None = None  # processo do navegador em modo aplicativo
        # Preenchidos pelo main depois de escolher o perfil (usados pela API):
        self.agenda = None
        self.verificar_texto: Callable[[str], str | None] | None = None  # Guardião para textos da agenda
        self.ao_mudar_agenda: Callable[[], None] | None = None
        self.ao_acao: Callable[[str], None] | None = None

    # ---------------------------------------------------------------- clientes
    def conectar(self) -> queue.Queue:
        fila: queue.Queue = queue.Queue()
        with self._trava:
            fila.put({"tipo": "reinicio"})
            for evento in self._historico:
                fila.put(evento)
            for evento in self._estados.values():
                fila.put(evento)
            if self._pedido:
                fila.put(self._pedido)
            self._clientes.append(fila)
            self.ja_conectou = True
        return fila

    def desconectar(self, fila: queue.Queue) -> None:
        with self._trava:
            if fila in self._clientes:
                self._clientes.remove(fila)
            if not self._clientes:
                self._sem_clientes_desde = time.monotonic()

    @property
    def tem_janela(self) -> bool:
        return bool(self._clientes)

    def _janela_foi_fechada(self) -> bool:
        if self.tem_janela:
            return False
        parado = time.monotonic() - self._sem_clientes_desde
        if self.janela_viva is not None and self.ja_conectou and not self.janela_viva():
            return parado > 2  # o processo da janela terminou: foi fechada de verdade
        return parado > (ESPERA_SEM_JANELA_S if self.ja_conectou else ESPERA_PRIMEIRA_JANELA_S)

    # ----------------------------------------------------------------- eventos
    def emitir(self, tipo: str, **dados) -> None:
        with self._trava:
            self._seq += 1
            evento = {"tipo": tipo, "seq": self._seq, **dados}
            if tipo == "limpar":
                self._historico.clear()
            if tipo in ESTADOS:
                self._estados[tipo] = evento
            elif tipo not in PASSAGEIROS:
                chave = dados.get("substitui")
                if chave:  # ex.: resposta em fluxo: só a versão mais nova fica no histórico
                    for antigo in [e for e in self._historico if e.get("substitui") == chave]:
                        self._historico.remove(antigo)
                self._historico.append(evento)
            for fila in self._clientes:
                fila.put(evento)

    # ----------------------------------------------------------------- pedidos
    def pedir(self, pedido: dict, ao_responder: Callable[[], None] | None = None) -> str:
        """
        Mostra um controle na janela e espera a resposta da criança. ``ao_responder`` é chamado no
        instante em que a resposta chega (ex.: o microfone do mãos-livres para de escutar na hora do toque).
        """
        pid = uuid.uuid4().hex[:10]
        evento = {"tipo": "pedido", "id": pid, **pedido}
        with self._trava:
            self._pedido = evento
            self._ao_responder = ao_responder
            self._respondido = False
            for fila in self._clientes:
                fila.put(evento)
        try:
            while True:
                try:
                    resposta = self._respostas.get(timeout=0.5)
                except queue.Empty:
                    if self._janela_foi_fechada():
                        raise JanelaFechada() from None
                    continue
                if resposta["id"] == pid:
                    return str(resposta["valor"])
        finally:
            with self._trava:
                self._pedido = None
            self.emitir("pedido_fim", id=pid)

    def responder(self, pid: str, valor: str) -> bool:
        """Só a primeira resposta vale (toque e voz ao mesmo tempo não respondem duas vezes)."""
        with self._trava:
            atual = self._pedido
            if not atual or atual["id"] != pid or self._respondido:
                return False
            self._respondido = True
            aviso = self._ao_responder
        if aviso:
            aviso()
        self._respostas.put({"id": pid, "valor": valor})
        return True

    def responder_pedido_atual(self, valor: str, espera_s: float = 3.0) -> bool:
        """Responde a pergunta que estiver na tela (usado pela voz no modo mãos-livres)."""
        limite = time.monotonic() + espera_s
        while time.monotonic() < limite:
            atual = self._pedido
            if atual:
                return self.responder(atual["id"], valor)
            time.sleep(0.05)
        return False

    def refazer_pedido(self) -> bool:
        """Se a pergunta na tela veio da escuta (ouvir), pede para ela ser feita de novo no modo atual."""
        atual = self._pedido
        if atual and atual.get("escuta"):
            from jarvis.ui import REFAZER

            return self.responder(atual["id"], REFAZER)
        return False

    @property
    def pedido_atual(self) -> dict | None:
        return self._pedido
