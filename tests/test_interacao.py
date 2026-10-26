"""Fluxo de resposta: cada frase da IA passa pelo Guardião antes de ser mostrada e falada."""

from jarvis.interacao import Interacao
from jarvis.seguranca import Guardiao


class FluxoFalso:
    def __init__(self, falado):
        self.falado, self.cancelado = falado, False

    def adicionar(self, frase):
        self.falado.append(frase)

    def finalizar(self):
        pass

    def cancelar(self):
        self.cancelado = True


class VozFalsa:
    def __init__(self):
        self.falado = []

    def iniciar_fluxo(self, voz=None):
        self.fluxo = FluxoFalso(self.falado)
        return self.fluxo

    def falar(self, texto, voz=None):
        self.falado.append(texto)


class EfeitosFalsos:
    def tocar(self, nome):
        pass


def criar_interacao():
    return Interacao(VozFalsa(), EfeitosFalsos(), Guardiao(), microfone=None, transcritor=None)


def test_resposta_normal_e_falada_frase_a_frase():
    io = criar_interacao()
    tokens = iter(["Olá, ag", "ente! Deus é ", "amor. Quer saber mais?"])
    texto, bloqueado = io.responder_em_fluxo(tokens)
    assert not bloqueado
    assert io.voz.falado == ["Olá, agente!", "Deus é amor.", "Quer saber mais?"]
    assert texto == "Olá, agente! Deus é amor. Quer saber mais?"


def test_resposta_com_palavrao_e_bloqueada_antes_de_ser_falada():
    io = criar_interacao()
    tokens = iter(["Boa pergunta! ", "Isso é uma merda. ", "Mais texto."])
    texto, bloqueado = io.responder_em_fluxo(tokens)
    assert bloqueado and texto == io.guardiao.resposta_saida_bloqueada
    assert not any("merda" in f for f in io.voz.falado)
    assert io.voz.fluxo.cancelado


def test_sem_microfone_a_escuta_fica_desligada():
    assert not criar_interacao().escuta_ativa


def test_citacao_inventada_tira_so_a_frase_dela():
    io = criar_interacao()
    tokens = iter(['A hóstia consagrada é Jesus de verdade. O Papa disse que "a hóstia é um pequeno pão do céu para '
                   'as crianças". Que tal visitar Jesus no sacrário? '])
    texto, bloqueado = io.responder_em_fluxo(tokens)
    assert not bloqueado and io.ultimo_bloqueio == "citacao"
    assert io.voz.falado == ["A hóstia consagrada é Jesus de verdade.", "Que tal visitar Jesus no sacrário?"]
    assert "pequeno pão" not in texto


def test_citacao_inventada_sozinha_vira_aviso():
    io = criar_interacao()
    tokens = iter(['Santo Agostinho disse: "quem canta reza duas vezes por dia na escola".'])
    texto, bloqueado = io.responder_em_fluxo(tokens)
    assert bloqueado and texto == io.guardiao.resposta_citacao


def test_citacao_presente_nas_fontes_e_falada():
    io = criar_interacao()
    frase = 'São João Bosco dizia: "Sejam sempre alegres".'
    texto, bloqueado = io.responder_em_fluxo(iter([frase]), autorizados="Frase autêntica: Sejam sempre alegres")
    assert not bloqueado and io.voz.falado == [frase]
