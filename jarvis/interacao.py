"""
Camada de interação: junta tela, voz, microfone e o Guardião.

Toda pergunta do Jarvis aceita as duas formas, para ser intuitivo:
  * DIGITAR a resposta e apertar ENTER, ou
  * apertar ENTER (com a linha vazia) e FALAR.
No modo "mãos-livres", o Jarvis já fica escutando sozinho.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator

from jarvis import ui
from jarvis.audio.efeitos import Efeitos
from jarvis.audio.ouvido import Microfone, Transcritor
from jarvis.audio.voz import Voz
from jarvis.seguranca import Guardiao
from jarvis.texto import ler_valor, normalizar, numero_por_palavras, palavras, radicais, separar_frases
from jarvis.web.ponte import JanelaFechada

PALAVRAS_SIM = {"sim", "s", "claro", "quero", "pode", "isso", "uhum", "aham", "ok", "beleza", "bora",
                "vamos", "certeza", "positivo", "afirmativo", "yes", "rezei", "fiz", "consegui"}
PALAVRAS_SAIR = {"sair", "voltar", "cancelar", "parar", "chega", "tchau", "menu"}
# Como o Whisper costuma escrever "Jarvis" quando a criança chama
VARIANTES_ATIVACAO = ("jarvis", "jarves", "jarvi", "djarvis", "jarbas", "jarvas", "jervis")
JANELA_CONVERSA_S = 20  # depois de uma resposta, dá para continuar sem repetir "Jarvis"
_ORDINAIS = {"primeira": 1, "primeiro": 1, "segunda": 2, "segundo": 2, "terceira": 3, "terceiro": 3,
             "quarta": 4, "quarto": 4, "quinta": 5, "quinto": 5, "sexta": 6, "sexto": 6, "setima": 7}


class Interacao:
    def __init__(self, voz: Voz, efeitos: Efeitos, guardiao: Guardiao, microfone: Microfone | None,
                 transcritor: Transcritor | None, modo_escuta: str = "apertar_enter", silencio_fim_ms: int = 900,
                 palavra_ativacao: str = "jarvis"):
        self.voz = voz
        self.efeitos = efeitos
        self.guardiao = guardiao
        self.microfone = microfone
        self.transcritor = transcritor
        self.maos_livres = modo_escuta == "maos_livres" and self.escuta_ativa
        self.silencio_fim_ms = silencio_fim_ms
        self.palavras_ativacao = {normalizar(palavra_ativacao), *VARIANTES_ATIVACAO}
        self.nome_crianca = "Você"
        self.ultimo_bloqueio: str | None = None  # 'linguagem' ou 'doutrina' (para o registro dos pais)
        self._ultima_fala = 0.0

    @property
    def escuta_ativa(self) -> bool:
        return self.microfone is not None and self.transcritor is not None

    # ------------------------------------------------------------------ falar
    def dizer(self, texto: str, titulo: str = "J.A.R.V.I.S.", cor: str = ui.CORES["jarvis"],
              voz: dict | None = None, mostrar: bool = True) -> None:
        if mostrar:
            ui.fala(texto, titulo, cor)
        try:
            self.voz.falar(texto, voz)
        except KeyboardInterrupt:
            self.voz.alto_falante.parar()
        self._ultima_fala = time.monotonic()

    def responder_em_fluxo(self, tokens: Iterator[str], titulo: str = "J.A.R.V.I.S.",
                           cor: str = ui.CORES["jarvis"], voz: dict | None = None,
                           autorizados: str = "") -> tuple[str, bool]:
        """
        Mostra e fala a resposta da IA frase por frase, enquanto ela é gerada.
        Cada frase passa pelo Guardião ANTES de aparecer na tela ou ser falada.
        Retorna (texto_final, foi_bloqueado).
        """
        ui.estado("pensando")
        fluxo = self.voz.iniciar_fluxo(voz)
        falado: list[str] = []
        buffer, bloqueado = "", False
        self.ultimo_bloqueio = None

        def entregar(frases: list[str]) -> bool:
            """Mostra e fala as frases aprovadas; retorna False se a resposta precisa parar."""
            for frase in frases:
                frase, motivo = self.guardiao.revisar_frase(frase, autorizados)
                if motivo:
                    self.ultimo_bloqueio = motivo
                    if motivo == "citacao":  # citação inventada: só essa frase fica de fora
                        continue
                    return False
                if frase:
                    painel.acrescentar(frase)
                    fluxo.adicionar(frase)
                    falado.append(frase)
            return True

        try:
            with ui.PainelAoVivo(titulo, cor) as painel:
                for token in tokens:
                    buffer += token
                    frases, buffer = separar_frases(buffer)
                    if not entregar(frases):
                        bloqueado = True
                        break
                if not bloqueado:
                    finais = separar_frases(buffer, final=True)[0]
                    if finais and falado and not re.search(r"[.!?…)\"”]\s*$", finais[-1]):
                        finais = finais[:-1]  # resposta cortada no limite de tamanho: não fala a frase pela metade
                    bloqueado = not entregar(finais)
                if not falado and self.ultimo_bloqueio == "citacao":
                    bloqueado = True  # não sobrou nenhuma frase segura
                if bloqueado:
                    aviso = (self.guardiao.resposta_citacao if self.ultimo_bloqueio == "citacao"
                             else self.guardiao.resposta_saida_bloqueada)
                    painel.acrescentar(aviso)
            if bloqueado:
                fluxo.cancelar()
                self.voz.falar(aviso, voz)
                return aviso, True
            fluxo.finalizar()
        except KeyboardInterrupt:
            fluxo.cancelar()
            ui.info("(resposta interrompida)")
        except Exception:
            fluxo.cancelar()  # ex.: o Ollama caiu no meio da resposta
            raise
        finally:
            close = getattr(tokens, "close", None)
            if close:
                close()
            self._ultima_fala = time.monotonic()
            ui.estado("ocioso")
        return " ".join(falado), False

    def celebrar(self, eventos: list) -> None:
        for e in eventos:
            ui.evento(e.tipo, e.texto, e.dados.get("descricao", ""))
            self.efeitos.tocar(e.som)
        grandes = [e for e in eventos if e.tipo in ("nivel", "medalha", "missoes")]
        if grandes:
            frases = []
            for e in grandes:
                if e.tipo == "nivel":
                    frases.append(f"Uau! Você subiu de nível! Agora você é {e.dados['nome']}!")
                elif e.tipo == "medalha":
                    frases.append(f"Nova medalha desbloqueada: {e.texto.split(':', 1)[-1].strip(' !')}!")
                else:
                    frases.append("Todas as missões do dia concluídas! Dia perfeito, agente!")
            self.voz.falar(" ".join(frases))

    # ----------------------------------------------------------------- ouvir
    def ouvir(self, rotulo: str | None = None, tipo: str = "texto", opcoes: list[str] | None = None) -> str:
        """
        Lê o que a criança digitou ou falou. Retorna '' se nada foi entendido.
        ``tipo`` e ``opcoes`` dizem à interface gráfica que controle mostrar (botões, teclado numérico...).
        """
        if self.maos_livres:
            return self._escutar_com_ativacao()
        if rotulo is None:
            rotulo = "🎤 ENTER para falar, ou digite" if self.escuta_ativa else "⌨️  Digite"
        try:
            digitado = ui.entrada(rotulo, tipo, opcoes).strip()
        except JanelaFechada:
            raise  # a janela foi fechada: o Jarvis desliga de uma vez
        except EOFError:
            return "sair"
        if digitado or not self.escuta_ativa:
            return digitado
        return self._escutar(espera_max_s=8.0)

    def _escutar_com_ativacao(self) -> str:
        """Mãos-livres: atende quem disser 'Jarvis' (ou continuar logo após uma resposta)."""
        while True:
            texto = self._escutar(espera_max_s=None)
            if not texto:
                continue
            chamado = remover_ativacao(texto, self.palavras_ativacao)
            if chamado is not None:
                return chamado
            if time.monotonic() - self._ultima_fala <= JANELA_CONVERSA_S:
                return texto
            ui.info("(Para me chamar, comece com \"Jarvis\".)")

    def _escutar(self, espera_max_s: float | None) -> str:
        self.efeitos.tocar("ativar")
        ui.estado("ouvindo")
        try:
            with ui.carregando("🎙️  Ouvindo… pode falar!"):
                audio = self.microfone.gravar_frase(espera_max_s=espera_max_s, silencio_fim_ms=self.silencio_fim_ms,
                                                    ao_nivel=ui.nivel_microfone)
        except KeyboardInterrupt:
            ui.estado("ocioso")
            return ""
        except Exception as exc:
            ui.estado("ocioso")
            ui.erro(f"Problema com o microfone: {exc}")
            return ""
        if audio is None:
            ui.estado("ocioso")
            ui.info("Não ouvi nada. Tente de novo, ou digite!")
            return ""
        self.efeitos.tocar("ouvido")
        ui.estado("pensando")
        with ui.carregando("⚡ Decodificando sua voz…"):
            texto = self.transcritor.transcrever(audio)
        ui.estado("ocioso")
        if texto:
            ui.crianca_disse(self.nome_crianca, texto)
        else:
            ui.info("Não entendi direito. Pode repetir?")
        return texto

    # ------------------------------------------------------- perguntas guiadas
    def escolher(self, pergunta: str, opcoes: list[str], titulo: str = "Escolha", falar: bool = True,
                 cor: str = ui.CORES["jarvis"]) -> int | None:
        """Mostra opções numeradas. Aceita número, letra, 'a segunda' ou o nome da opção."""
        ui.menu(titulo, opcoes, cor, pergunta)
        if falar:
            self.dizer(pergunta, mostrar=False)
        for _ in range(3):
            resposta = self.ouvir("Sua escolha (número, letra ou fale)", tipo="escolha", opcoes=opcoes)
            if not resposta:
                continue
            indice = interpretar_escolha(resposta, opcoes)
            if indice == 0:
                return None
            if indice is not None:
                return indice - 1
            ui.aviso("Não entendi. Diga o número da opção, ou 0 para voltar.")
        return None

    def confirmar(self, pergunta: str, falar: bool = True) -> bool:
        if falar:
            self.dizer(pergunta)
        else:
            ui.fala(pergunta)
        return interpretar_sim(self.ouvir("Sim ou não", tipo="sim_nao"))

    def pedir_valor(self, pergunta: str, falar: bool = True, permitir_zero: bool = False) -> int | None:
        """Valor em centavos. None = cancelou. Com ``permitir_zero``, '0' é uma resposta válida."""
        if falar:
            self.dizer(pergunta)
        rotulo = "Valor (ex.: 2,50)" + (" — 0 = só pontos, 'voltar' cancela" if permitir_zero else " — 0 cancela")
        for _ in range(3):
            resposta = self.ouvir(rotulo, tipo="valor")
            if not resposta or normalizar(resposta) in PALAVRAS_SAIR:
                return None
            valor = ler_valor(resposta)
            if valor is not None:
                return valor if valor > 0 or permitir_zero else None
            ui.aviso("Não entendi o valor. Exemplos: 3  •  2,50  •  dois reais e cinquenta")
        return None

    def pedir_numero(self, pergunta: str, falar: bool = True) -> int | None:
        if falar:
            self.dizer(pergunta)
        for _ in range(3):
            resposta = self.ouvir("Número", tipo="numero")
            if not resposta or normalizar(resposta) in PALAVRAS_SAIR:
                return None
            numero = numero_por_palavras(resposta.replace("%", " "))
            if numero is not None:
                return numero
            ui.aviso("Diga ou digite um número, por exemplo 10.")
        return None

    def pedir_texto(self, pergunta: str, falar: bool = True) -> str:
        if falar:
            self.dizer(pergunta)
        resposta = self.ouvir("Digite ou fale", tipo="texto")
        return "" if normalizar(resposta) in PALAVRAS_SAIR else resposta


def remover_ativacao(texto: str, palavras_ativacao: set[str]) -> str | None:
    """'Jarvis, que horas são?' -> 'que horas são?'. None se ninguém chamou o Jarvis."""
    for palavra in palavras(texto):
        if palavra in palavras_ativacao:
            m = re.search(rf"(?i)\b{re.escape(palavra)}\w*\W*", normalizar(texto))
            resto = texto[m.end():].strip() if m else texto
            return resto or texto
    return None


def interpretar_sim(resposta: str) -> bool:
    t = normalizar(resposta)
    if not t or re.search(r"\b(nao|nunca|negativo|nem)\b", t):
        return False
    return bool(PALAVRAS_SIM & set(palavras(t)))


def interpretar_escolha(resposta: str, opcoes: list[str]) -> int | None:
    """Retorna 1..n para uma opção, 0 para 'voltar', None se não entendeu."""
    t = normalizar(resposta).strip(" .!?")
    if t in PALAVRAS_SAIR or t == "0":
        return 0
    m = re.fullmatch(r"(?:opcao|numero|letra|alternativa)?\s*([0-9]+|[a-h])\)?", t)
    if m:
        valor = m.group(1)
        indice = int(valor) if valor.isdigit() else ord(valor) - ord("a") + 1
        return indice if 0 <= indice <= len(opcoes) else None
    for palavra in palavras(t):
        if palavra in _ORDINAIS and _ORDINAIS[palavra] <= len(opcoes):
            return _ORDINAIS[palavra]
    # pelo nome: a opção com mais radicais em comum
    alvo = set(radicais(t))
    if not alvo:
        return None
    notas = [len(alvo & set(radicais(op))) for op in opcoes]
    melhor = max(notas)
    if melhor and notas.count(melhor) == 1:
        return notas.index(melhor) + 1
    return None
