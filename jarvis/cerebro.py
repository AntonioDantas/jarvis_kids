"""
Cérebro do Jarvis: conversa com o modelo de linguagem LOCAL via Ollama.

* Respostas em streaming (palavra por palavra), para o Jarvis começar a
  falar quase instantaneamente.
* Memória curta das últimas trocas (conversa natural, contexto pequeno = rápido).
* Mantém o modelo carregado na memória (keep_alive) para não "esfriar".
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator

from config import PlanoIA


class ErroCerebro(RuntimeError):
    """Erro com mensagem amigável para mostrar à família."""


MENSAGEM_SEM_OLLAMA = (
    "O motor de IA (Ollama) não está ligado. No Windows e no Mac, abra o aplicativo Ollama; "
    "no Linux, rode 'ollama serve' num terminal. Depois, ligue o Jarvis de novo. "
    "Ainda não instalou? Baixe grátis em https://ollama.com/download"
)


class FiltroPensamento:
    """Remove blocos <think>...</think> de modelos que 'pensam em voz alta'."""

    ABRE, FECHA = "<think>", "</think>"

    def __init__(self) -> None:
        self.dentro = False
        self.buffer = ""

    def filtrar(self, texto: str) -> str:
        self.buffer += texto
        saida = ""
        while True:
            if self.dentro:
                fim = self.buffer.find(self.FECHA)
                if fim < 0:
                    self.buffer = self.buffer[-len(self.FECHA):]
                    return saida
                self.buffer, self.dentro = self.buffer[fim + len(self.FECHA):], False
                continue
            inicio = self.buffer.find(self.ABRE)
            if inicio >= 0:
                saida += self.buffer[:inicio]
                self.buffer, self.dentro = self.buffer[inicio + len(self.ABRE):], True
                continue
            corte = self.buffer.rfind("<")
            if corte >= 0 and self.ABRE.startswith(self.buffer[corte:]):
                saida += self.buffer[:corte]       # pode ser o começo de "<think>"
                self.buffer = self.buffer[corte:]
            else:
                saida, self.buffer = saida + self.buffer, ""
            return saida

    def finalizar(self) -> str:
        resto, self.buffer = ("" if self.dentro else self.buffer), ""
        return resto


def _campo(objeto, nome: str, padrao=None):
    """Lê um campo tanto de dicionários quanto dos objetos do cliente ollama."""
    if isinstance(objeto, dict):
        return objeto.get(nome, padrao)
    return getattr(objeto, nome, padrao)


def status_em_portugues(status: str) -> str:
    """'pulling 6a0746a1ec1a' -> 'baixando'; 'verifying sha256 digest' -> 'conferindo o arquivo'..."""
    s = status.lower()
    for chave, traducao in (("manifest", "preparando"), ("pulling", "baixando"), ("verifying", "conferindo o arquivo"),
                            ("writing", "finalizando"), ("success", "pronto!")):
        if s.startswith(chave) or (chave == "manifest" and chave in s and "pulling" in s):
            return traducao
    return status


class Cerebro:
    def __init__(self, plano: PlanoIA, host: str = "", turnos_memoria: int = 6):
        import ollama

        self._ollama = ollama
        self.plano = plano
        self.cliente = ollama.Client(host=host or None)
        self.historico: deque = deque(maxlen=max(2, turnos_memoria * 2))

    @property
    def modelo(self) -> str:
        return self.plano.modelo_llm

    # ------------------------------------------------------------- servidor
    def modelos_instalados(self) -> list[str]:
        try:
            resposta = self.cliente.list()
        except Exception as exc:
            raise ErroCerebro(MENSAGEM_SEM_OLLAMA) from exc
        nomes = []
        for m in _campo(resposta, "models", []) or []:
            nome = _campo(m, "model") or _campo(m, "name")
            if nome:
                nomes.append(nome)
        return nomes

    def modelo_instalado(self) -> bool:
        alvo = self.modelo if ":" in self.modelo else f"{self.modelo}:latest"
        return alvo in self.modelos_instalados()

    def baixar_modelo(self, progresso: Callable[[str, int, int], None]) -> None:
        try:
            for passo in self.cliente.pull(self.modelo, stream=True):
                progresso(status_em_portugues(_campo(passo, "status", "") or ""), _campo(passo, "completed", 0) or 0,
                          _campo(passo, "total", 0) or 0)
        except Exception as exc:
            raise ErroCerebro(f"Não consegui baixar o modelo '{self.modelo}': {exc}") from exc

    def aquecer(self, system_prompt: str | None = None) -> None:
        """
        Carrega o modelo na memória. Com ``system_prompt``, o Ollama também já processa as regras
        do Jarvis e guarda em cache: a primeira pergunta da criança é respondida bem mais rápido.
        """
        try:
            if system_prompt is None:
                self.cliente.generate(model=self.modelo, prompt="", keep_alive=self.plano.manter_carregado)
            else:
                self.cliente.chat(model=self.modelo, messages=[{"role": "system", "content": system_prompt},
                                                               {"role": "user", "content": "Oi"}],
                                  options={**self.plano.opcoes_ollama, "num_predict": 1},
                                  keep_alive=self.plano.manter_carregado)
        except Exception:
            pass

    # ------------------------------------------------------------- conversa
    def responder(self, pergunta: str, system_prompt: str, fontes: str | None = None,
                  temperatura: float | None = None) -> Iterator[str]:
        mensagens = [{"role": "system", "content": system_prompt}, *self.historico]
        # As fontes vão na mesma mensagem da pergunta: modelos pequenos dão mais atenção ao que está perto dela
        # (o Ollama junta todas as mensagens "system" no começo, longe da pergunta).
        conteudo = f"{fontes}\n\nPERGUNTA DA CRIANÇA: {pergunta}" if fontes else pergunta
        mensagens.append({"role": "user", "content": conteudo})
        filtro = FiltroPensamento()
        try:
            for parte in self.cliente.chat(
                model=self.modelo,
                messages=mensagens,
                stream=True,
                options=self.plano.opcoes_ollama if temperatura is None else {**self.plano.opcoes_ollama,
                                                                                "temperature": temperatura},
                keep_alive=self.plano.manter_carregado,
            ):
                texto = filtro.filtrar(_campo(_campo(parte, "message", {}), "content", "") or "")
                if texto:
                    yield texto
        except ConnectionError as exc:
            raise ErroCerebro(MENSAGEM_SEM_OLLAMA) from exc
        except self._ollama.ResponseError as exc:
            if getattr(exc, "status_code", 0) == 404:
                raise ErroCerebro(f"O modelo '{self.modelo}' não está instalado. Rode: ollama pull {self.modelo}") from exc
            raise ErroCerebro(f"O motor de IA respondeu com um erro: {exc}") from exc
        resto = filtro.finalizar()
        if resto:
            yield resto

    def memorizar(self, pergunta: str, resposta: str) -> None:
        self.historico.append({"role": "user", "content": pergunta})
        self.historico.append({"role": "assistant", "content": resposta})

    def esquecer(self) -> None:
        self.historico.clear()
