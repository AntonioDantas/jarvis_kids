import pytest

from jarvis.texto import (
    formatar_reais,
    ler_valor,
    normalizar,
    preparar_para_fala,
    radical,
    reais_por_extenso,
    separar_frases,
)


@pytest.mark.parametrize("entrada, centavos", [
    ("2", 200), ("2,50", 250), ("R$ 2.50", 250), ("1.000", 100000), ("R$ 1.234,56", 123456), ("0,50", 50),
    ("2 reais e 50 centavos", 250), ("dois reais e cinquenta", 250), ("cinquenta centavos", 50),
    ("um real e vinte e cinco centavos", 125), ("dez", 1000), ("3 reais", 300), ("abc", None), ("", None),
])
def test_ler_valor(entrada, centavos):
    assert ler_valor(entrada) == centavos


def test_formatacao_de_dinheiro():
    assert formatar_reais(123456) == "R$ 1.234,56"
    assert formatar_reais(5) == "R$ 0,05"
    assert reais_por_extenso(101) == "1 real e 1 centavo"
    assert reais_por_extenso(1250) == "12 reais e 50 centavos"
    assert reais_por_extenso(0) == "zero reais"


def test_separar_frases_em_streaming():
    texto = "Olá, agente! Hoje vamos falar de S. João Bosco. Ele nasceu em 1815. O valor é 3.5 e pronto."
    frases, resto = [], ""
    for i in range(0, len(texto), 4):  # simula tokens chegando aos poucos
        prontas, resto = separar_frases(resto + texto[i:i + 4])
        frases += prontas
    frases += separar_frases(resto, final=True)[0]
    assert frases == ["Olá, agente!", "Hoje vamos falar de S. João Bosco.", "Ele nasceu em 1815.",
                      "O valor é 3.5 e pronto."]


def test_preparar_para_fala():
    falado = preparar_para_fala("**Uau!** 🚀 O CIC 2559 diz... Leia Mt 6,9-13 e Lc 2. Tens R$ 12,50 e 10% é 1º.")
    assert "*" not in falado and "🚀" not in falado
    assert "Catecismo, número 2559" in falado
    assert "Mateus, capítulo 6, versículos 9 a 13" in falado
    assert "Lucas, capítulo 2" in falado
    assert "12 reais e 50 centavos" in falado
    assert "10 por cento" in falado and "primeiro" in falado


def test_os_2_peixes_nao_vira_livro_da_biblia():
    assert "Oseias" not in preparar_para_fala("Os 2 peixes e os 5 pães.")


@pytest.mark.parametrize("a, b", [("arrumei", "arrumar"), ("reguei", "regar"), ("brinquei", "brincar"),
                                  ("lavei", "lavar"), ("anjos", "anjo"), ("mandamentos", "mandamento")])
def test_radicais_equivalentes(a, b):
    assert radical(a) == radical(b)


def test_normalizar_ordinais():
    assert normalizar("Qual é o 4º Mandamento?") == "qual e o quarto mandamento?"
