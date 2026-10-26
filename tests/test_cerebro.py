import pytest

from config import Hardware, planejar
from jarvis.cerebro import Cerebro, ErroCerebro, FiltroPensamento


def test_filtro_de_pensamento_entre_pedacos():
    filtro = FiltroPensamento()
    pedacos = ["Olá", " <thi", "nk>raciocínio ", "secreto</th", "ink> agente!", " Tudo <b>bem"]
    saida = "".join(filtro.filtrar(p) for p in pedacos) + filtro.finalizar()
    assert saida == "Olá  agente! Tudo <b>bem"


class ClienteFalso:
    def __init__(self, partes=None, erro=None):
        self.partes, self.erro, self.recebido = partes or [], erro, None

    def chat(self, **kwargs):
        self.recebido = kwargs
        if self.erro:
            raise self.erro
        return iter({"message": {"content": p}} for p in self.partes)

    def list(self):
        return {"models": [{"model": "llama3.2:3b"}]}


@pytest.fixture
def cerebro():
    return Cerebro(planejar(Hardware("cpu", "", 0, 16, 8)))


def test_responder_em_streaming_com_fontes(cerebro):
    cerebro.cliente = ClienteFalso(["<think>hmm</think>Deus ", "é amor."])
    assert "".join(cerebro.responder("Quem é Deus?", "SISTEMA", "FONTES")) == "Deus é amor."
    mensagens = cerebro.cliente.recebido["messages"]
    assert [m["role"] for m in mensagens] == ["system", "user"]
    assert mensagens[-1]["content"].startswith("FONTES") and "PERGUNTA DA CRIANÇA: Quem é Deus?" in mensagens[-1]["content"]
    assert cerebro.cliente.recebido["keep_alive"] == "30m"


def test_memoria_curta(cerebro):
    cerebro.cliente = ClienteFalso(["ok"])
    cerebro.memorizar("pergunta", "resposta")
    list(cerebro.responder("nova", "SISTEMA"))
    assert [m["role"] for m in cerebro.cliente.recebido["messages"]] == ["system", "user", "assistant", "user"]
    cerebro.esquecer()
    assert not cerebro.historico


def test_modelo_instalado(cerebro):
    cerebro.cliente = ClienteFalso()
    assert cerebro.modelo_instalado()


def test_erro_de_conexao_vira_mensagem_amigavel(cerebro):
    cerebro.cliente = ClienteFalso(erro=ConnectionError("sem servidor"))
    with pytest.raises(ErroCerebro, match="Ollama"):
        list(cerebro.responder("oi", "SISTEMA"))
