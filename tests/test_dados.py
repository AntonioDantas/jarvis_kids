"""Integridade do conteúdo: perguntas do quiz, santos, histórias, orações e exame."""

import json
from datetime import date
from pathlib import Path

import pytest

DADOS = Path(__file__).resolve().parents[1] / "dados"


def carregar(nome):
    return json.loads((DADOS / nome).read_text(encoding="utf-8"))


def test_todos_os_json_sao_validos():
    for arquivo in DADOS.rglob("*.json"):
        json.loads(arquivo.read_text(encoding="utf-8"))


def test_quiz():
    dados = carregar("quiz.json")
    perguntas = dados["perguntas"]
    assert len(perguntas) >= 50
    assert len({p["pergunta"] for p in perguntas}) == len(perguntas), "pergunta repetida"
    for p in perguntas:
        assert p["categoria"] in dados["categorias"]
        assert len(p["opcoes"]) == 4 and len(set(p["opcoes"])) == 4
        assert 0 <= p["correta"] < 4 and p["dificuldade"] in (1, 2, 3)
        assert p["explicacao"] and p["fonte"]
    for categoria in dados["categorias"]:
        assert sum(p["categoria"] == categoria for p in perguntas) >= 5


def test_santos():
    for s in carregar("santos.json")["santos"]:
        for campo in ("id", "nome", "apelido", "emoji", "anos", "festa", "estilo", "saudacao"):
            assert s[campo], f"{s['id']} sem {campo}"
        assert len(s["fatos"]) >= 8
        assert {"kokoro", "edge", "velocidade"} <= set(s["voz"])
        assert s["voz"]["kokoro"] in {"pm_alex", "pm_santa", "pf_dora"}
        for c in s["citacoes"]:
            assert c["texto"] and c["fonte"]


def test_historias_biblicas():
    historias = carregar("historias_biblicas.json")["historias"]
    assert len(historias) >= 12
    for h in historias:
        assert all(h[c] for c in ("id", "titulo", "referencia", "texto", "licao", "pergunta"))


def test_oracoes():
    ids = set()
    for o in carregar("oracoes.json")["oracoes"]:
        assert o["linhas"] and all(linha.strip() for linha in o["linhas"])
        ids.add(o["id"])
    assert {"manha", "noite", "pai_nosso", "ave_maria", "ato_contricao", "dizimo"} <= ids


def test_exame_de_consciencia_tem_os_dez_mandamentos():
    exame = carregar("exame_consciencia.json")
    assert [m["numero"] for m in exame["mandamentos"]] == list(range(1, 11))
    for m in exame["mandamentos"]:
        assert m["perguntas"] and m["virtude"] and m["desafio"]


def test_calendario_tem_datas_validas():
    for chave in carregar("calendario_santos.json")["dias"]:
        mes, dia = map(int, chave.split("-"))
        date(2028, mes, dia)  # 2028 é bissexto: aceita 29/02


@pytest.mark.parametrize("nome", ["dicas_financeiras.json", "seguranca.json", "conhecimento/catecismo_kids.json"])
def test_arquivos_nao_vazios(nome):
    assert carregar(nome)
