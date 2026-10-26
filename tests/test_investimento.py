"""Cofrinho de Investimento: juros compostos diários pagos pelo Banco da Família."""

from datetime import date, timedelta

import pytest

from jarvis.armazenamento import carregar
from jarvis.mesada import INVESTIMENTO, Mesada

HOJE = date.today()


def mesada_com_investimento(perfil, valor=5000, taxa=1.0):
    mesada = Mesada(perfil, taxa)
    mesada.definir_percentuais({"dizimo": 0, "poupar": 0, "investir": 100, "gastar": 0, "doar": 0})
    mesada.depositar(valor, "teste")
    return mesada


def test_perfil_novo_ja_tem_cofrinho_de_investimento(perfil):
    mesada = Mesada(perfil)
    assert mesada.investimento["id"] == INVESTIMENTO and mesada.investimento["percentual"] == 20
    assert sum(c["percentual"] for c in mesada.cofrinhos) == 100


def test_perfil_antigo_ganha_investimento_sem_mudar_o_plano(perfil):
    perfil.mesada["cofrinhos"] = [c for c in perfil.mesada["cofrinhos"] if c["id"] != INVESTIMENTO]
    perfil.mesada["cofrinhos"][1]["percentual"] = 40  # plano antigo: 10/40/40/10
    mesada = Mesada(perfil)
    assert mesada.investimento["percentual"] == 0
    assert sum(c["percentual"] for c in mesada.cofrinhos) == 100


def test_rende_um_por_cento_em_trinta_dias(perfil):
    mesada = mesada_com_investimento(perfil, 5000, 1.0)
    assert mesada.atualizar_rendimentos(HOJE + timedelta(days=30)) == 50
    assert mesada.investimento["saldo"] == 5050 and mesada.investimento["rendimento_total"] == 50
    assert mesada.extrato(1)[0]["tipo"] == "rendimento"


def test_rendimento_dia_a_dia_e_composto_e_nao_perde_centavos(perfil):
    mesada = mesada_com_investimento(perfil, 10_000, 2.0)
    total = sum(mesada.atualizar_rendimentos(HOJE + timedelta(days=d)) for d in range(1, 361))
    esperado = 10_000 * ((1.02) ** 12 - 1)  # um ano a 2% ao mês
    assert abs(total - esperado) <= 1


def test_mesmo_dia_ou_taxa_zero_nao_rende(perfil):
    mesada = mesada_com_investimento(perfil, 5000, 1.0)
    assert mesada.atualizar_rendimentos(HOJE) == 0
    sem_juros = Mesada(carregar(perfil.arquivo), 0.0)
    assert sem_juros.atualizar_rendimentos(HOJE + timedelta(days=60)) == 0


def test_aportes_e_resgates(perfil):
    mesada = mesada_com_investimento(perfil, 5000, 1.0)
    mesada.definir_percentuais({"dizimo": 0, "poupar": 0, "investir": 0, "gastar": 100, "doar": 0})
    mesada.depositar(3000, "mesada")
    mesada.transferir("gastar", INVESTIMENTO, 1000)
    assert mesada.investimento["aportado"] == 6000
    mesada.transferir(INVESTIMENTO, "gastar", 2500)
    assert mesada.investimento["aportado"] == 3500 and mesada.investimento["saldo"] == 3500


def test_relatorio_claro_para_a_crianca(perfil):
    mesada = mesada_com_investimento(perfil, 10_000, 1.0)
    mesada.atualizar_rendimentos(HOJE + timedelta(days=30))
    r = mesada.relatorio_investimento()
    assert (r.saldo, r.aportado, r.rendimento_total) == (10_100, 10_000, 100)
    assert r.rentabilidade_pct == pytest.approx(1.0)
    assert r.taxa_anual == pytest.approx(12.68, abs=0.01)
    assert r.rende_proximo_mes == 101 and r.projecao[12] == round(10_100 * 1.01 ** 12)
    assert r.anos_para_dobrar == pytest.approx(5.7, abs=0.1)


def test_taxa_limitada_a_cinco_por_cento(perfil):
    assert Mesada(perfil, 50).taxa_rendimento == 5.0
    assert Mesada(perfil, -3).taxa_rendimento == 0.0
