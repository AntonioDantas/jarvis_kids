"""Acionamento só pela voz ("Jarvis, ..."), no terminal e na janela — com microfone e Whisper simulados."""

import threading
import time

import numpy as np
import pytest

from jarvis import ui
from jarvis.interacao import Interacao
from jarvis.seguranca import Guardiao
from jarvis.web.ponte import Ponte
from jarvis.web.tela_web import TelaWeb


class MicrofoneFalso:
    """Devolve as falas da lista, uma por gravação; sem falas, fica esperando até ser cancelado."""

    def __init__(self, falas, atraso=0.05):
        self.falas, self.atraso = list(falas), atraso
        self.cancelamentos = 0

    def gravar_frase(self, espera_max_s=None, silencio_fim_ms=900, ao_detectar_fala=None, ao_nivel=None,
                     cancelar=None, **_):
        inicio = time.monotonic()
        while not self.falas:
            if cancelar is not None and cancelar.is_set():
                self.cancelamentos += 1
                return None
            if espera_max_s is not None and time.monotonic() - inicio > espera_max_s:
                return None
            time.sleep(0.01)
        time.sleep(self.atraso)
        if cancelar is not None and cancelar.is_set():
            self.cancelamentos += 1
            return None
        if ao_detectar_fala:
            ao_detectar_fala()
        indice = len(TranscritorFalso.textos)
        TranscritorFalso.textos.append(self.falas.pop(0))
        return np.full(4000, indice, dtype=np.float32)


class TranscritorFalso:
    textos: list[str] = []

    def transcrever(self, audio):
        return TranscritorFalso.textos[int(audio[0])]


class EfeitosFalsos:
    def __init__(self):
        self.tocados = []

    def tocar(self, nome):
        self.tocados.append(nome)


class VozFalsa:
    def falar(self, texto, voz=None):
        pass


def criar(falas, modo="maos_livres"):
    TranscritorFalso.textos = []
    return Interacao(VozFalsa(), EfeitosFalsos(), Guardiao(), MicrofoneFalso(falas), TranscritorFalso(), modo)


@pytest.fixture(autouse=True)
def tela_do_terminal():
    ui.usar_tela(None)
    yield
    ui.usar_tela(None)


# ------------------------------------------------------------------ terminal
def test_conversa_da_casa_e_ignorada_e_o_chamado_e_atendido():
    io = criar(["Mãe, cadê o meu tênis?", "eu acho que o Jarvis é legal", "Jarvis, conta uma história"])
    assert io.ouvir() == "conta uma história"
    # nenhum bip para as conversas que não eram com o Jarvis; só o "entendi" do chamado
    assert io.efeitos.tocados == ["ouvido"]


def test_so_dizer_jarvis_abre_a_escuta_para_o_pedido():
    io = criar(["Jarvis!", "qual é a capital do Brasil?"])
    assert io.ouvir() == "qual é a capital do Brasil?"
    assert io.efeitos.tocados[0] == "ativar"  # bip: "pode falar"


def test_logo_depois_de_uma_pergunta_do_jarvis_pode_responder_sem_chamar():
    io = criar(["letra B"])
    io._ultima_fala = time.monotonic()  # o Jarvis acabou de falar
    assert io.ouvir() == "letra B"


def test_microfone_quebrado_desliga_o_maos_livres_sem_travar():
    io = criar([])

    class Quebrado:
        def gravar_frase(self, **_):
            raise OSError("sem microfone")

    io.microfone = Quebrado()
    io_sleep = time.sleep
    try:
        time.sleep = lambda _s: None  # não espera 1 s entre as tentativas no teste
        assert io.ouvir() == ""
    finally:
        time.sleep = io_sleep
    assert io.maos_livres is False


# -------------------------------------------------------------------- janela
def rodar_ouvir(io, **kwargs):
    resultado = {}
    t = threading.Thread(target=lambda: resultado.update(texto=io.ouvir(**kwargs)), daemon=True)
    t.start()
    return t, resultado


def esperar_pedido(ponte, campo="controle", valor=None, tempo=3.0):
    limite = time.monotonic() + tempo
    while time.monotonic() < limite:
        pedido = ponte.pedido_atual
        if pedido and (valor is None or pedido.get(campo) == valor):
            return pedido
        time.sleep(0.01)
    raise AssertionError("a janela não recebeu a pergunta")


def test_na_janela_a_voz_responde_a_pergunta_da_tela():
    ponte = Ponte()
    ui.usar_tela(TelaWeb(ponte))
    io = criar(["Jarvis, abre o quiz"])
    io.microfone.atraso = 0.2
    t, resultado = rodar_ouvir(io, tipo="principal")
    pedido = esperar_pedido(ponte)
    assert pedido["escuta"] == "maos_livres"
    t.join(3)
    assert resultado["texto"] == "abre o quiz" and ponte.pedido_atual is None


def test_na_janela_os_botoes_continuam_funcionando_no_maos_livres():
    ponte = Ponte()
    ui.usar_tela(TelaWeb(ponte))
    io = criar([])  # ninguém fala
    t, resultado = rodar_ouvir(io, tipo="quiz", opcoes=["A", "B"])
    pedido = esperar_pedido(ponte)
    ponte.responder(pedido["id"], "b")
    t.join(3)
    assert resultado["texto"] == "b"
    assert io.microfone.cancelamentos == 1  # o microfone parou antes de o Jarvis voltar a falar


def test_continuar_na_janela_nao_liga_o_microfone():
    ponte = Ponte()
    ui.usar_tela(TelaWeb(ponte))
    io = criar([])
    t, resultado = rodar_ouvir(io, rotulo="Diga próximo", tipo="continuar")
    ponte.responder(esperar_pedido(ponte)["id"], "")
    t.join(3)
    assert resultado["texto"] == "" and "ativar" not in io.efeitos.tocados


def test_ligar_o_maos_livres_vale_na_pergunta_que_ja_esta_na_tela():
    ponte = Ponte()
    tela = TelaWeb(ponte)
    tela.configurar(True, "x", {}, {})
    ui.usar_tela(tela)
    io = criar(["Jarvis, oi"], modo="apertar_enter")
    io.microfone.atraso = 0.2
    t, resultado = rodar_ouvir(io, tipo="principal")
    assert esperar_pedido(ponte)["escuta"] == "botao"
    io.maos_livres = True
    tela.maos_livres(True)  # botão "Mãos-livres" da janela
    esperar_pedido(ponte, "escuta", "maos_livres")
    t.join(3)
    assert resultado["texto"] == "oi"


def test_pergunta_que_nao_veio_da_escuta_nao_e_refeita():
    ponte = Ponte()
    ui.usar_tela(TelaWeb(ponte))
    resultado = {}
    t = threading.Thread(target=lambda: resultado.update(pin=ui.entrada("PIN", "pin")), daemon=True)
    t.start()
    pedido = esperar_pedido(ponte)
    assert not ponte.refazer_pedido()  # o PIN dos pais não recebe a resposta especial
    ponte.responder(pedido["id"], "1234")
    t.join(3)
    assert resultado["pin"] == "1234"
