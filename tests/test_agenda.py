"""Agenda/planner: compromissos da criança, santo do dia, Missa de domingo e "marca prova na sexta às 8h"."""

import json
from datetime import date

import pytest

from config import PASTA_DADOS
from jarvis.agenda import Agenda, adivinhar_categoria, dias_santos_de_guarda, interpretar_compromisso, resumo_do_dia
from jarvis.comandos import identificar_comando
from jarvis.texto import data_por_extenso

SEGUNDA = date(2026, 10, 26)


@pytest.mark.parametrize("frase, titulo, dia, hora, categoria, repetir", [
    ("Jarvis, marca prova de matemática na sexta às 8h", "Prova de matemática", date(2026, 10, 30), "08:00", "escola", ""),
    ("anota aniversário da vovó dia 15 de novembro", "Aniversário da vovó", date(2026, 11, 15), "", "aniversario",
     "anual"),
    ("me lembra de levar o trabalho de ciências amanhã", "Levar o trabalho de ciências", date(2026, 10, 27), "", "escola",
     ""),
    ("marca futebol toda terça às 17h30", "Futebol", date(2026, 10, 27), "17:30", "esporte", "semanal"),
    ("coloca na agenda: dentista 03/11 às 3 da tarde", "Dentista", date(2026, 11, 3), "15:00", "saude", ""),
    ("marca catequese no sábado às 9", "Catequese", date(2026, 10, 31), "09:00", "fe", ""),
    ("põe na minha agenda que eu tenho apresentação de piano no dia 20 às 19h", "Apresentação de piano",
     date(2026, 11, 20), "19:00", "esporte", ""),
])
def test_entende_compromissos_falados(frase, titulo, dia, hora, categoria, repetir):
    pedido = interpretar_compromisso(frase, SEGUNDA)
    assert pedido == {"titulo": titulo, "data": dia, "hora": hora, "categoria": categoria, "repetir": repetir}


@pytest.mark.parametrize("frase", ["marca um gol!", "que horas são?", "conta uma história", "o que é a Trindade?"])
def test_nao_confunde_conversa_com_agenda(frase):
    assert interpretar_compromisso(frase, SEGUNDA) is None


def test_pedido_de_agenda_sem_data_pergunta_o_dia():
    assert interpretar_compromisso("anota na agenda prova de história", SEGUNDA)["data"] is None


def test_categorias_mais_especificas_ganham():
    assert adivinhar_categoria("Apresentação de piano") == "esporte"
    assert adivinhar_categoria("Trabalho de ciências") == "escola"
    assert adivinhar_categoria("Missa da crisma do primo") == "fe"
    assert adivinhar_categoria("Dentista") == "saude"


def test_domingo_tem_missa_e_santo_do_dia(tmp_path):
    agenda = Agenda(tmp_path / "a.json", missa_horario="09:30", missa_local="Paróquia São José")
    domingo = agenda.do_dia(date(2026, 11, 1))
    assert any(i.categoria == "missa" and i.hora == "09:30" and "Paróquia São José" in i.titulo for i in domingo)
    assert any("Todos os Santos" in i.titulo for i in domingo)


def test_dias_santos_de_guarda_do_brasil():
    dias = dias_santos_de_guarda(2026)
    assert dias[date(2026, 6, 4)] == "Corpus Christi"  # Páscoa 2026: 5 de abril
    assert date(2026, 12, 8) in dias and date(2026, 12, 25) in dias and date(2026, 1, 1) in dias


def test_compromissos_que_repetem(tmp_path):
    agenda = Agenda(tmp_path / "a.json")
    agenda.adicionar("Futebol", date(2026, 10, 27), "17:00", "esporte", "semanal")
    agenda.adicionar("Aniversário da vovó", date(2026, 11, 15), "", "aniversario", "anual")
    assert [i.titulo for i in agenda.do_dia(date(2026, 11, 3)) if not i.automatico] == ["Futebol"]
    assert [i.titulo for i in agenda.do_dia(date(2027, 11, 15)) if not i.automatico] == ["Aniversário da vovó"]
    assert not [i for i in agenda.do_dia(date(2026, 10, 20)) if not i.automatico]  # antes de começar


def test_agenda_grava_e_recarrega(tmp_path):
    arquivo = tmp_path / "agendas" / "lucas.json"
    evento = Agenda(arquivo).adicionar("Prova", date(2026, 10, 30), "08:00", "escola")
    recarregada = Agenda(arquivo)
    assert [i.titulo for i in recarregada.do_dia(date(2026, 10, 30)) if not i.automatico] == ["Prova"]
    assert recarregada.remover(evento["id"]) and not Agenda(arquivo).remover(evento["id"])


def test_titulo_vazio_ou_longo(tmp_path):
    agenda = Agenda(tmp_path / "a.json")
    with pytest.raises(ValueError):
        agenda.adicionar("   ", date(2026, 10, 30))
    assert len(agenda.adicionar("x" * 200, date(2026, 10, 30))["titulo"]) == 60


def test_resumo_falado_do_dia(tmp_path):
    agenda = Agenda(tmp_path / "a.json")
    assert resumo_do_dia(agenda.do_dia(SEGUNDA)) == "Você não tem compromissos marcados para hoje."
    agenda.adicionar("Prova de matemática", SEGUNDA, "08:00", "escola")
    agenda.adicionar("Futebol", SEGUNDA, "17:30", "esporte")
    assert resumo_do_dia(agenda.do_dia(SEGUNDA)) == "Na sua agenda de hoje: Prova de matemática às 8h e Futebol às 17h30."


def test_comando_agenda():
    for frase in ("agenda", "abre o planner", "o que eu tenho hoje", "Jarvis, minha agenda"):
        assert identificar_comando(frase) == "agenda", frase


def test_data_por_extenso():
    assert data_por_extenso(SEGUNDA) == "segunda-feira, 26 de outubro"
    assert data_por_extenso(date(2026, 3, 1), com_dia_semana=False) == "1 de março"


def test_santo_do_dia_cobre_o_ano_inteiro():
    dias = json.loads((PASTA_DADOS / "calendario_santos.json").read_text(encoding="utf-8"))["dias"]
    assert len(dias) >= 200
    for chave in dias:
        date.fromisoformat(f"2024-{chave}")  # todas as datas existem (2024 é bissexto)
    # santos do Brasil
    assert "Anchieta" in dias["06-09"] and "Galvão" in dias["10-25"] and "Paulina" in dias["07-09"]
    assert "Cunhaú" in dias["10-03"] and "Dulce" in dias["08-13"]


def test_horarios_sao_falados_por_extenso():
    from jarvis.texto import preparar_para_fala

    assert preparar_para_fala("Prova às 8h, futebol às 17h30 e Missa à 1h.") == \
        "Prova às 8 horas, futebol às 17 e 30 e Missa à 1 hora."
