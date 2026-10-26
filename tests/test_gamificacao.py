from datetime import date, timedelta

from jarvis.gamificacao import MISSOES, Gamificacao, avaliar_pergunta, nivel_de


def test_niveis():
    assert nivel_de(0)[1] == "Recruta Digital"
    assert nivel_de(99)[1] == "Recruta Digital"
    assert nivel_de(100)[1] == "Cadete Estelar"
    assert nivel_de(99999)[4] is None  # nível máximo


def test_subir_de_nivel_gera_evento(perfil):
    jogo = Gamificacao(perfil)
    eventos = jogo.ganhar(120, "teste")
    assert [e.tipo for e in eventos] == ["pontos", "nivel"]
    assert jogo.ganhar(0, "nada") == []


def test_sequencia_de_dias(perfil):
    jogo = Gamificacao(perfil)
    jogo.jogo["ultimo_dia"] = (date.today() - timedelta(days=1)).isoformat()
    jogo.jogo["dias_seguidos"] = 6
    eventos = jogo.iniciar_dia()
    assert jogo.jogo["dias_seguidos"] == 7
    assert any(e.tipo == "medalha" and "Combo de 7 Dias" in e.texto for e in eventos)
    assert jogo.iniciar_dia() == []  # no mesmo dia não conta de novo
    jogo.jogo["ultimo_dia"] = (date.today() - timedelta(days=3)).isoformat()
    jogo.iniciar_dia()
    assert jogo.jogo["dias_seguidos"] == 1


def test_missoes_do_dia(perfil):
    jogo = Gamificacao(perfil)
    missoes = jogo.missoes_de_hoje()
    assert len(missoes) == 4 and missoes[0]["id"] == "oracao"
    eventos = []
    for m in missoes:
        eventos += jogo.registrar(MISSOES[m["id"]][1], m["meta"])
    assert all(m["concluida"] for m in jogo.missoes_de_hoje())
    assert sum(1 for e in eventos if e.tipo == "missoes") == 1
    assert not any(e.tipo == "missoes" for e in jogo.registrar("oracoes"))  # bônus só uma vez


def test_medalhas(perfil):
    jogo = Gamificacao(perfil)
    assert any(e.tipo == "medalha" for e in jogo.registrar("perguntas"))
    for santo in ("dom_bosco", "carlo_acutis", "teresinha"):
        eventos = jogo.registrar_santo(santo)
    assert any("Amigo dos Santos" in e.texto for e in eventos)


def test_avaliar_pergunta():
    assert avaliar_pergunta("legal") == (0, "")
    pontos_simples, _ = avaliar_pergunta("O que é um planeta?")
    pontos_profundos, rotulo = avaliar_pergunta("Por que Deus criou o universo tão grande se só vivemos aqui?")
    assert 0 < pontos_simples < pontos_profundos <= 10
    assert rotulo == "Pergunta de Filósofo"


def test_perguntas_repetidas_nao_rendem_pontos(perfil):
    jogo = Gamificacao(perfil)
    assert jogo.pontuar_pergunta("Como funciona um foguete no espaço?")
    antes = jogo.pontos
    jogo.pontuar_pergunta("Como funciona um foguete no espaço?")
    assert jogo.pontos == antes


def test_limite_diario(perfil):
    jogo = Gamificacao(perfil)
    assert [jogo.dentro_do_limite("oracao", 3) for _ in range(4)] == [True, True, True, False]
    assert jogo.dentro_do_limite("quiz", 1)
