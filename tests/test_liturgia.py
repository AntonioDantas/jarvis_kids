from datetime import date

import pytest

from jarvis.fe.liturgia import (
    ano_liturgico,
    batismo_do_senhor,
    dia_liturgico,
    epifania,
    inicio_advento,
    pascoa,
    proximas_grandes_festas,
    sagrada_familia,
)


@pytest.mark.parametrize("ano, data", [(2008, "2008-03-23"), (2019, "2019-04-21"), (2024, "2024-03-31"),
                                       (2025, "2025-04-20"), (2026, "2026-04-05"), (2027, "2027-03-28"),
                                       (2030, "2030-04-21"), (2038, "2038-04-25")])
def test_pascoa(ano, data):
    assert pascoa(ano).isoformat() == data


def test_advento_epifania_e_batismo_no_brasil():
    assert inicio_advento(2025) == date(2025, 11, 30)
    assert inicio_advento(2026) == date(2026, 11, 29)
    assert epifania(2026) == date(2026, 1, 4) and batismo_do_senhor(2026) == date(2026, 1, 11)
    assert epifania(2024) == date(2024, 1, 7) and batismo_do_senhor(2024) == date(2024, 1, 8)  # caso especial
    assert sagrada_familia(2026) == date(2026, 12, 27) and sagrada_familia(2022) == date(2022, 12, 30)


@pytest.mark.parametrize("dia, tempo, cor", [
    ("2026-10-26", "Tempo Comum", "verde"), ("2026-12-01", "Advento", "roxo"), ("2026-12-13", "Advento", "rosa"),
    ("2026-12-25", "Natal", "branco"), ("2026-01-11", "Natal", "branco"), ("2026-01-12", "Tempo Comum", "verde"),
    ("2026-02-18", "Quaresma", "roxo"), ("2026-03-15", "Quaresma", "rosa"), ("2026-03-29", "Quaresma", "vermelho"),
    ("2026-04-02", "Tríduo Pascal", "branco"), ("2026-04-03", "Tríduo Pascal", "vermelho"),
    ("2026-04-05", "Tempo Pascal", "branco"), ("2026-05-24", "Tempo Pascal", "vermelho"),
    ("2026-06-04", "Tempo Comum", "branco"), ("2026-10-12", "Tempo Comum", "branco"),
])
def test_tempo_e_cor(dia, tempo, cor):
    info = dia_liturgico(date.fromisoformat(dia))
    assert (info.tempo, info.cor) == (tempo, cor)


def test_celebracoes():
    assert "Corpus Christi" in dia_liturgico(date(2026, 6, 4)).celebracao  # quinta-feira no Brasil
    assert "Aparecida" in dia_liturgico(date(2026, 10, 12)).celebracao
    assert "Ascensão" in dia_liturgico(date(2026, 5, 17)).celebracao  # domingo no Brasil


def test_ano_a_b_c():
    assert ano_liturgico(date(2026, 10, 26)) == "A"   # Mateus
    assert ano_liturgico(date(2026, 11, 29)) == "B"   # começa o ano B no Advento
    assert ano_liturgico(date(2027, 12, 25)) == "C"
    assert dia_liturgico(date(2026, 10, 26)).evangelista == "Mateus"


def test_contagem_regressiva():
    contagem = dict(proximas_grandes_festas(date(2026, 10, 26)))
    assert contagem == {"Natal": 60, "Páscoa": 153, "Pentecostes": 202}


def test_solenidades_transferidas_para_o_domingo_no_brasil():
    assert dia_liturgico(date(2026, 6, 28)).celebracao == "São Pedro e São Paulo, apóstolos"  # 29/06 é segunda
    assert dia_liturgico(date(2026, 6, 28)).cor == "vermelho"
    assert dia_liturgico(date(2024, 8, 18)).celebracao == "Assunção de Nossa Senhora ao Céu"  # 15/08 foi quinta
    assert dia_liturgico(date(2026, 11, 1)).celebracao == "Todos os Santos"
    assert "Finados" in dia_liturgico(date(2025, 11, 2)).celebracao  # domingo 2/11: Finados permanece
