import random

import pytest

from jarvis.armazenamento import carregar
from jarvis.mesada import ErroMesada, Mesada, distribuir, simular_poupanca


def test_distribuir_soma_sempre_exata():
    gerador = random.Random(42)
    for _ in range(500):
        valor = gerador.randint(1, 100_000)
        pcts = [("a", gerador.randint(0, 50)), ("b", gerador.randint(0, 50)), ("c", gerador.randint(1, 50))]
        partes = distribuir(valor, pcts)
        assert sum(partes.values()) == valor
        assert all(v >= 0 for v in partes.values())


def test_distribuir_pelos_maiores_restos():
    assert distribuir(250, [("dizimo", 10), ("poupar", 30), ("gastar", 50), ("doar", 10)]) == {
        "dizimo": 25, "poupar": 75, "gastar": 125, "doar": 25}
    assert distribuir(1, [("a", 50), ("b", 50)]) in ({"a": 1, "b": 0}, {"a": 0, "b": 1})
    with pytest.raises(ErroMesada):
        distribuir(100, [("a", 0)])


def test_deposito_divide_nos_cofrinhos_e_registra_extrato(perfil):
    mesada = Mesada(perfil)
    resultado = mesada.depositar(1000, "teste")
    assert resultado.distribuicao == {"dizimo": 100, "poupar": 300, "gastar": 500, "doar": 100}
    assert mesada.saldo_total() == 1000
    assert mesada.extrato(1)[0]["tipo"] == "deposito"


def test_atividade_sem_aprovacao_credita_na_hora(perfil):
    mesada = Mesada(perfil)
    atividade = mesada.adicionar_atividade("Arrumar a cama", 200)
    status, resultado = mesada.concluir_atividade(atividade["id"], precisa_aprovacao=False)
    assert status == "creditado" and sum(resultado.distribuicao.values()) == 200


def test_atividade_com_aprovacao_fica_pendente_ate_os_pais_aprovarem(perfil):
    mesada = Mesada(perfil)
    atividade = mesada.adicionar_atividade("Lavar a louça", 300)
    status, _ = mesada.concluir_atividade(atividade["id"], precisa_aprovacao=True)
    assert status == "pendente" and mesada.saldo_total() == 0
    pendente = mesada.pendentes[0]
    mesada.aprovar(pendente["id"], valor=250)  # os pais negociaram outro valor
    assert mesada.saldo_total() == 250 and not mesada.pendentes


def test_recusar_e_atividade_so_de_pontos(perfil):
    mesada = Mesada(perfil)
    a = mesada.adicionar_atividade("Ler um livro", 100)
    mesada.concluir_atividade(a["id"], precisa_aprovacao=True)
    mesada.recusar(mesada.pendentes[0]["id"])
    assert mesada.saldo_total() == 0
    so_pontos = mesada.adicionar_atividade("Rezar o terço", 0)
    assert mesada.concluir_atividade(so_pontos["id"], True) == ("sem_valor", None)


def test_valores_invalidos(perfil):
    mesada = Mesada(perfil)
    with pytest.raises(ErroMesada):
        mesada.adicionar_atividade("Exagero", 100_01)
    with pytest.raises(ErroMesada):
        mesada.adicionar_atividade("   ", 100)
    with pytest.raises(ErroMesada):
        mesada.depositar(0, "nada")


def test_gastar_transferir_e_saldo_insuficiente(perfil):
    mesada = Mesada(perfil)
    mesada.depositar(1000, "mesada")
    mesada.retirar("gastar", 200, "lanche")
    assert mesada.cofrinho("gastar")["saldo"] == 300
    with pytest.raises(ErroMesada):
        mesada.retirar("gastar", 301, "videogame")
    mesada.transferir("gastar", "poupar", 300)
    assert mesada.cofrinho("poupar")["saldo"] == 600 and mesada.cofrinho("gastar")["saldo"] == 0
    with pytest.raises(ErroMesada):
        mesada.transferir("poupar", "poupar", 10)


def test_entregar_dizimo(perfil):
    mesada = Mesada(perfil)
    mesada.depositar(2000, "mesada")
    assert mesada.entregar("dizimo", destino="Paróquia São José") == 200
    assert mesada.cofrinho("dizimo")["saldo"] == 0
    assert mesada.extrato(1)[0]["tipo"] == "dizimo_entregue"


def test_percentuais_precisam_somar_100(perfil):
    mesada = Mesada(perfil)
    with pytest.raises(ErroMesada):
        mesada.definir_percentuais({"dizimo": 10, "poupar": 10, "gastar": 10, "doar": 10})
    mesada.definir_percentuais({"dizimo": 10, "poupar": 40, "gastar": 40, "doar": 10})
    assert mesada.cofrinho("poupar")["percentual"] == 40


def test_cofrinho_de_sonho_com_meta(perfil):
    mesada = Mesada(perfil)
    sonho = mesada.criar_cofrinho("Bicicleta", "🚲", meta=1000)
    mesada.definir_percentuais({"dizimo": 10, "poupar": 0, "gastar": 0, "doar": 0, sonho["id"]: 90})
    assert mesada.depositar(1000, "a").metas_atingidas == []
    assert mesada.depositar(200, "b").metas_atingidas == ["Bicicleta"]
    mesada.remover_cofrinho(sonho["id"])  # saldo e percentual voltam para a poupança
    assert mesada.cofrinho("poupar")["saldo"] == 1080 and mesada.cofrinho("poupar")["percentual"] == 90
    with pytest.raises(ErroMesada):
        mesada.remover_cofrinho("dizimo")


def test_mesada_persiste_no_disco(perfil):
    Mesada(perfil).depositar(777, "persistência")
    recarregado = carregar(perfil.arquivo)
    assert Mesada(recarregado).saldo_total() == 777


def test_simulador_de_poupanca():
    assert simular_poupanca(500, 52)[-1] == 26000
    com_juros = simular_poupanca(500, 52, juros_mensal_pct=1)
    assert com_juros[-1] > 26000 and com_juros[3] == round(2000 * 1.01)
