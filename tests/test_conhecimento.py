import pytest

from jarvis.fe.conhecimento import PASTA_CONHECIMENTO, Biblioteca

biblioteca = Biblioteca()


@pytest.mark.parametrize("pergunta, esperado", [
    ("O que é a Santíssima Trindade?", "trindade"),
    ("Quantos livros tem a Bíblia?", "biblia"),
    ("O padre pode contar o que eu falei na confissão?", "confissao"),
    ("O que é o dízimo?", "dizimo"),
    ("Qual é o 4º mandamento?", "mandamento-4"),
    ("Por que tenho que ir à missa no domingo?", "missa"),
    ("Horóscopo é verdade?", "supersticao"),
    ("Quem foi Dom Bosco?", "santo-dom_bosco"),
    ("Quem foi a irmã Dulce?", "santo-dulce_pobres"),
    ("Quem venceu o Golias?", "historia-davi_golias"),
    ("O que é o Big Bang?", "fe-e-ciencia"),
])
def test_busca_encontra_a_fonte_certa(pergunta, esperado):
    resultados = biblioteca.buscar(pergunta)
    assert resultados and resultados[0].id == esperado


@pytest.mark.parametrize("pergunta", ["Por que o céu é azul?", "Quanto é 7 vezes 8?", "Como funciona um foguete?"])
def test_perguntas_sem_fonte_nao_trazem_contexto_confuso(pergunta):
    assert biblioteca.buscar(pergunta) == []


def test_todas_as_fontes_tem_referencia():
    for trecho in biblioteca.trechos:
        assert trecho.texto and trecho.titulo
        assert trecho.referencias, f"{trecho.id} está sem referência"


def test_deteccao_de_pergunta_de_fe():
    assert biblioteca.e_pergunta_de_fe("Jesus tinha irmãos?")
    assert not biblioteca.e_pergunta_de_fe("Por que o céu é azul?")


def test_material_extra_da_familia(tmp_path):
    original = PASTA_CONHECIMENTO / "catecismo_kids.json"
    (tmp_path / original.name).write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "extra").mkdir()
    (tmp_path / "extra" / "catequese_paroquia.md").write_text(
        "Nossa paróquia celebra a festa da padroeira com uma grande procissão de barcos no rio.\n\n"
        "Curto.", encoding="utf-8")
    local = Biblioteca(pasta=tmp_path)
    assert [t.id for t in local.buscar("Como é a procissão de barcos da paróquia?")] == ["catequese_paroquia-0"]
