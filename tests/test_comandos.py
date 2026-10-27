import pytest

from jarvis.comandos import detectar_atividade, identificar_comando, pede_santo
from jarvis.fe.vozes import encontrar_santo
from jarvis.interacao import interpretar_escolha, interpretar_sim


@pytest.mark.parametrize("texto, comando", [
    ("quiz", "quiz"), ("Jarvis, vamos rezar!", "oracao"), ("me conta uma história", "vozes"),
    ("abrir a mesada", "mesada"), ("5", "mesada"), ("quero ver meus pontos", "conquistas"),
    ("quanto eu tenho no cofrinho?", "saldo"), ("volta ao normal", "normal"), ("Tchau!", "sair"),
    ("modo pais", "pais"), ("Jarvis, abre o quiz por favor", "quiz"),
    ("O que é a oração?", None), ("como faço para rezar melhor?", None), ("Por que o céu é azul?", None),
])
def test_identificar_comando(texto, comando):
    assert identificar_comando(texto) == comando


def test_pedir_para_falar_com_santo():
    assert pede_santo("quero falar com o Carlo Acutis")
    assert encontrar_santo("quero falar com o Carlo Acutis")["id"] == "carlo_acutis"
    assert encontrar_santo("chama a Santa Teresinha")["id"] == "teresinha"
    assert not pede_santo("Quem foi Dom Bosco?")  # pergunta normal: o Jarvis responde, sem trocar de persona


ATIVIDADES = [{"nome": n} for n in ["Arrumar a cama", "Lavar ou secar a louça", "Regar as plantas",
                                    "Fazer a lição de casa sem reclamar", "Ajudar um irmão ou colega"]]


@pytest.mark.parametrize("texto, esperado", [
    ("Jarvis, eu arrumei a minha cama!", "Arrumar a cama"),
    ("reguei as plantas", "Regar as plantas"),
    ("eu fiz a lição de casa", "Fazer a lição de casa sem reclamar"),
    ("ajudei meu irmão", "Ajudar um irmão ou colega"),
    ("cheguei em casa", None),
    ("o que é a cama elástica?", None),
])
def test_detectar_atividade_concluida(texto, esperado):
    atividade = detectar_atividade(texto, ATIVIDADES)
    assert (atividade["nome"] if atividade else None) == esperado


@pytest.mark.parametrize("resposta, indice", [
    ("2", 2), ("b", 2), ("Letra C.", 3), ("a segunda", 2), ("voltar", 0), ("0", 0), ("9", None),
    ("sete pães", 3), ("cinco pães e dois peixes", None),  # empate entre opções com as mesmas palavras
    ("banana", None),
])
def test_interpretar_escolha(resposta, indice):
    opcoes = ["Dois pães e cinco peixes", "Cinco pães e dois peixes", "Sete pães", "Doze pães e doze peixes"]
    assert interpretar_escolha(resposta, opcoes) == indice


@pytest.mark.parametrize("resposta, sim", [("sim", True), ("Claro!", True), ("rezei sim", True),
                                           ("não", False), ("não sei", False), ("", False), ("talvez", False)])
def test_interpretar_sim(resposta, sim):
    assert interpretar_sim(resposta) is sim


@pytest.mark.parametrize("texto, esperado", [
    ("Jarvis, por que o céu é azul?", "por que o céu é azul?"),
    ("Jarbas qual é a capital do Brasil", "qual é a capital do Brasil"),
    ("ei Jarvis!", ""),  # só chamou: o Jarvis dá o bip e espera o pedido
    ("Ok, Jarvis. Abre o quiz", "Abre o quiz"),
    ("a gente vai na praia amanhã", None),
    ("eu acho que o Jarvis é muito legal", None),  # falou DO Jarvis, não COM o Jarvis
])
def test_palavra_de_ativacao(texto, esperado):
    from jarvis.interacao import VARIANTES_ATIVACAO, remover_ativacao

    assert remover_ativacao(texto, set(VARIANTES_ATIVACAO)) == esperado
