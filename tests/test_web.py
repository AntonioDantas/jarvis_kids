"""Janela futurista: ponte de eventos, servidor local (com as travas de segurança) e TelaWeb."""

import http.client
import json
import threading
import time
from datetime import date

import numpy as np
import pytest

from jarvis.agenda import Agenda
from jarvis.web import ponte as modulo_ponte
from jarvis.web.ponte import JanelaFechada, Ponte
from jarvis.web.servidor import iniciar_servidor
from jarvis.web.tela_web import TelaWeb, dados_laterais, envelope_da_voz


def coletar(fila) -> list[dict]:
    eventos = []
    while not fila.empty():
        eventos.append(fila.get_nowait())
    return eventos


# ----------------------------------------------------------------- ponte
def test_janela_que_conecta_depois_recebe_historico_e_estado_atual():
    ponte = Ponte()
    ponte.emitir("fala", texto="Olá!")
    ponte.emitir("estado", nome="pensando")
    ponte.emitir("estado", nome="ocioso")
    ponte.emitir("nivel_mic", valor=0.5)  # passageiro: não fica guardado
    tipos = [(e["tipo"], e.get("nome")) for e in coletar(ponte.conectar())]
    assert tipos == [("reinicio", None), ("fala", None), ("estado", "ocioso")]


def test_resposta_em_fluxo_guarda_so_a_versao_mais_nova():
    ponte = Ponte()
    for texto in ("Deus", "Deus é", "Deus é amor."):
        ponte.emitir("fala", texto=texto, substitui="fluxo-1")
    falas = [e for e in coletar(ponte.conectar()) if e["tipo"] == "fala"]
    assert [f["texto"] for f in falas] == ["Deus é amor."]


def test_pedido_espera_a_resposta_da_janela():
    ponte = Ponte()
    fila = ponte.conectar()
    resultado = {}
    t = threading.Thread(target=lambda: resultado.update(valor=ponte.pedir({"controle": "sim_nao"})))
    t.start()
    for _ in range(100):
        pedidos = [e for e in list(fila.queue) if e["tipo"] == "pedido"]
        if pedidos:
            break
        time.sleep(0.01)
    assert not ponte.responder("id-errado", "sim")
    assert ponte.responder(pedidos[0]["id"], "sim")
    t.join(2)
    assert resultado["valor"] == "sim" and ponte.pedido_atual is None


def test_janela_fechada_desliga_o_jarvis(monkeypatch):
    ponte = Ponte()
    ponte.desconectar(ponte.conectar())
    ponte.janela_viva = lambda: False
    monkeypatch.setattr(modulo_ponte, "ESPERA_SEM_JANELA_S", 0)
    ponte._sem_clientes_desde -= 5
    with pytest.raises(JanelaFechada):
        ponte.pedir({"controle": "principal"})
    assert issubclass(JanelaFechada, EOFError)  # o resto do Jarvis trata como "tchau"


# ---------------------------------------------------------------- servidor
@pytest.fixture
def servidor(tmp_path):
    ponte = Ponte()
    ponte.agenda = Agenda(tmp_path / "agenda.json")
    ponte.verificar_texto = lambda t: "Esse texto não pode ir para a agenda." if "palavrao" in t else None
    srv = iniciar_servidor(ponte, 0)
    yield srv
    srv.desligar()


def pedir(srv, metodo, caminho, corpo=None, token=True, cabecalhos=None):
    conexao = http.client.HTTPConnection("127.0.0.1", srv.porta, timeout=5)
    h = {"Content-Type": "application/json"}
    if token:
        h["X-Jarvis-Token"] = srv.ponte.token
    h.update(cabecalhos or {})
    conexao.request(metodo, caminho, body=json.dumps(corpo) if corpo is not None else None, headers=h)
    resposta = conexao.getresponse()
    dados = resposta.read()
    conexao.close()
    return resposta, dados


def test_pagina_e_arquivos_com_politica_de_seguranca(servidor):
    resposta, corpo = pedir(servidor, "GET", "/", token=False)
    assert resposta.status == 200 and b"J.A.R.V.I.S." in corpo
    assert "default-src 'self'" in resposta.getheader("Content-Security-Policy")
    resposta, _ = pedir(servidor, "GET", "/static/app.js", token=False)
    assert resposta.status == 200 and resposta.getheader("Content-Type").startswith("text/javascript")


@pytest.mark.parametrize("caminho", ["/static/../servidor.py", "/static/%2e%2e/ponte.py", "/main.py", "/static/"])
def test_nao_sai_da_pasta_da_tela(servidor, caminho):
    resposta, _ = pedir(servidor, "GET", caminho, token=False)
    assert resposta.status == 404


def test_api_exige_token(servidor):
    resposta, _ = pedir(servidor, "GET", "/api/agenda", token=False)
    assert resposta.status == 403
    resposta, _ = pedir(servidor, "POST", "/api/responder", {"id": "x", "valor": "1"}, token=False)
    assert resposta.status == 403


def test_bloqueia_outro_site_e_dns_rebinding(servidor):
    resposta, _ = pedir(servidor, "POST", "/api/responder", {"id": "x", "valor": "1"},
                        cabecalhos={"Origin": "https://site-malicioso.com"})
    assert resposta.status == 403
    resposta, _ = pedir(servidor, "GET", "/", token=False, cabecalhos={"Host": "jarvis.ataque.com"})
    assert resposta.status == 403


def test_envio_sem_json_e_recusado(servidor):
    resposta, _ = pedir(servidor, "POST", "/api/responder", None, cabecalhos={"Content-Type": "text/plain"})
    assert resposta.status == 400


def test_agenda_pela_janela(servidor):
    resposta, corpo = pedir(servidor, "POST", "/api/agenda",
                            {"titulo": "Prova de matemática", "data": "2026-10-30", "hora": "08:00", "categoria": "escola"})
    assert resposta.status == 200
    evento_id = json.loads(corpo)["evento"]["id"]
    _, corpo = pedir(servidor, "GET", "/api/agenda?start=2026-10-25&end=2026-11-01")
    eventos = json.loads(corpo)
    assert any(e["title"] == "📚 Prova de matemática" and e["start"] == "2026-10-30T08:00:00" for e in eventos)
    assert any(e["extendedProps"]["categoria"] == "missa" for e in eventos)  # domingo: Dia do Senhor
    resposta, _ = pedir(servidor, "DELETE", f"/api/agenda?id={evento_id}")
    assert resposta.status == 200
    resposta, _ = pedir(servidor, "DELETE", "/api/agenda?id=../../x")
    assert resposta.status == 404


@pytest.mark.parametrize("corpo", [
    {"titulo": "", "data": "2026-10-30"},
    {"titulo": "Futebol", "data": "ontem"},
    {"titulo": "Futebol", "data": "2026-10-30", "hora": "25:99"},
])
def test_agenda_valida_os_campos(servidor, corpo):
    resposta, _ = pedir(servidor, "POST", "/api/agenda", corpo)
    assert resposta.status == 400


def test_guardiao_confere_o_texto_da_agenda(servidor):
    resposta, corpo = pedir(servidor, "POST", "/api/agenda", {"titulo": "um palavrao", "data": "2026-10-30"})
    assert resposta.status == 422 and "não pode" in json.loads(corpo)["erro"]


def test_periodo_grande_demais_e_recusado(servidor):
    resposta, _ = pedir(servidor, "GET", "/api/agenda?start=2026-01-01&end=2027-01-01")
    assert resposta.status == 400


# --------------------------------------------------------------- TelaWeb
def test_entrada_vira_pedido_com_o_menu_e_resposta_volta():
    ponte = Ponte()
    tela = TelaWeb(ponte)
    tela.menu("🧠 QUIZ", ["[bold]Fé[/]", "Bíblia"], "#00d7ff", "Escolha a categoria")
    fila = ponte.conectar()

    def responder():
        for _ in range(200):
            pedidos = [e for e in list(fila.queue) if e["tipo"] == "pedido"]
            if pedidos:
                ponte.responder(pedidos[0]["id"], "2")
                return
            time.sleep(0.01)

    threading.Thread(target=responder).start()
    assert tela.entrada("Sua escolha", "escolha", ["Fé", "Bíblia"]) == "2"
    pedido = next(e for e in coletar(fila) if e["tipo"] == "pedido")
    assert pedido["controle"] == "escolha" and pedido["menu"]["opcoes"] == ["Fé", "Bíblia"]
    assert pedido["menu"]["pergunta"] == "Escolha a categoria"


def test_tabela_converte_barras_e_marcacao():
    from jarvis import ui

    ponte = Ponte()
    TelaWeb(ponte).tabela("[bold]Missões[/]", ["Missão", "Progresso"], [["Rezar", ui.barra(1, 2, 10)]], "#5fffaf")
    tabela = [e for e in coletar(ponte.conectar()) if e["tipo"] == "tabela"][0]
    assert tabela["titulo"] == "Missões" and tabela["linhas"][0] == ["Rezar", {"barra": 0.5}]


def test_envelope_da_voz_fica_entre_0_e_1():
    taxa = 24_000
    t = np.linspace(0, 1, taxa, endpoint=False)
    audio = (np.sin(2 * np.pi * 220 * t) * np.linspace(0, 1, taxa)).astype(np.float32)
    envelope = envelope_da_voz(audio, taxa)
    assert len(envelope) == 30 and max(envelope) == 1.0 and min(envelope) >= 0
    assert envelope[-1] > envelope[0]  # o volume sobe junto com o áudio
    assert envelope_da_voz(np.zeros(0, dtype=np.float32), taxa) == []


def test_painel_lateral_mostra_liturgia_agenda_e_contagem(tmp_path):
    agenda = Agenda(tmp_path / "a.json", missa_horario="09:30")
    agenda.adicionar("Futebol", date(2026, 10, 28), "17:00", "esporte")
    dados = dados_laterais(agenda, hoje=date(2026, 10, 26))
    assert dados["data"] == "segunda-feira, 26 de outubro"
    assert dados["liturgia"]["tempo"] == "Tempo Comum" and dados["liturgia"]["cor"] == "verde"
    assert [p["titulo"] for p in dados["proximos"]][:2] == ["Futebol", "Dia do Senhor: Missa em família"]
    assert dados["proximos"][1]["hora"] == "09:30"
    assert dados["contagem"][0] == {"nome": "Natal", "dias": 60}


def test_ao_esperar_a_crianca_o_nucleo_volta_a_ficar_online():
    ponte = Ponte()
    tela = TelaWeb(ponte)
    tela.estado("pensando")
    fila = ponte.conectar()
    threading.Thread(target=lambda: tela.entrada("Digite", "principal")).start()
    for _ in range(200):
        eventos = list(fila.queue)
        pedido = next((e for e in eventos if e["tipo"] == "pedido"), None)
        if pedido:
            break
        time.sleep(0.01)
    estados = [e["nome"] for e in eventos if e["tipo"] == "estado"]
    assert estados[-1] == "ocioso"
    ponte.responder(pedido["id"], "oi")
