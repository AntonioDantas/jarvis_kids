"""Quiz Desafio: perguntas revisadas (fé, Bíblia, santos, ciência, finanças, matemática)."""

from __future__ import annotations

import random

from jarvis import ui
from jarvis.contexto import Contexto, carregar_dados
from jarvis.gamificacao import PONTOS
from jarvis.interacao import interpretar_escolha

PERGUNTAS_POR_RODADA = 5
LETRAS = "ABCD"


def sortear(perguntas: list[dict], categoria: str | None, recentes: list[str], quantidade: int,
            gerador: random.Random | None = None) -> list[dict]:
    """Sorteia perguntas da categoria, evitando as que saíram recentemente."""
    gerador = gerador or random.Random()
    candidatas = [p for p in perguntas if categoria in (None, p["categoria"])]
    novas = [p for p in candidatas if p["pergunta"] not in recentes]
    if len(novas) < quantidade:
        novas = candidatas
    return gerador.sample(novas, min(quantidade, len(novas)))


def executar(ctx: Contexto) -> None:
    dados = carregar_dados("quiz.json")
    categorias = list(dados["categorias"].items())
    indice = ctx.io.escolher(
        "Modo Quiz ativado! Escolha a categoria do desafio.",
        ["🎲 Misturado (de tudo um pouco)"] + [nome for _, nome in categorias],
        titulo="🧠 QUIZ DESAFIO",
    )
    if indice is None:
        return
    categoria = None if indice == 0 else categorias[indice - 1][0]
    recentes = ctx.jogo.jogo.setdefault("quiz_recentes", [])
    rodada = sortear(dados["perguntas"], categoria, recentes, PERGUNTAS_POR_RODADA)
    vale_pontos = ctx.jogo.dentro_do_limite("quiz", 5)
    if not vale_pontos:
        ui.info("(Você já jogou bastante hoje: esta rodada é só para treinar!)")

    acertos, combo, pontos = 0, 0, 0
    for numero, p in enumerate(rodada, 1):
        ui.pergunta_quiz(numero, len(rodada), p["pergunta"], p["opcoes"],
                         f"{dados['categorias'][p['categoria']]} · {'★' * p['dificuldade']}")
        falado = " ".join(f"{letra}: {opcao}." for letra, opcao in zip(LETRAS, p["opcoes"], strict=False))
        ctx.io.dizer(f"{p['pergunta']} {falado}", mostrar=False)

        escolha = None
        for _ in range(3):
            resposta = ctx.io.ouvir("Sua resposta (A, B, C, D) — 0 para sair", tipo="quiz", opcoes=p["opcoes"])
            escolha = interpretar_escolha(resposta, p["opcoes"]) if resposta else None
            if escolha is not None:
                break
            ui.aviso("Responda com a letra (A, B, C ou D) ou o número.")
        if escolha in (None, 0):
            ui.info("Quiz encerrado.")
            break

        recentes.append(p["pergunta"])
        if escolha - 1 == p["correta"]:
            acertos += 1
            combo += 1
            ganho = PONTOS["quiz_acerto"] * p["dificuldade"] * (2 if combo >= 3 else 1)
            pontos += ganho
            ctx.io.efeitos.tocar("moeda")
            extra = f"  🔥 COMBO x{combo}!" if combo >= 3 else ""
            ui.resultado(True, f"CORRETO! +{ganho} pts{extra}", p["fonte"])
            ctx.io.dizer(f"Correto! {p['explicacao']}", mostrar=False)
        else:
            combo = 0
            ctx.io.efeitos.tocar("erro")
            certa = f"{LETRAS[p['correta']]}) {p['opcoes'][p['correta']]}"
            ui.resultado(False, f"Quase! A resposta certa é {certa}", p["fonte"])
            ctx.io.dizer(f"Quase! A resposta certa é {p['opcoes'][p['correta']]}. {p['explicacao']}", mostrar=False)
        ui.info(p["explicacao"])
    del recentes[:-30]

    total = len(rodada)
    if acertos == 0 and not pontos:
        ctx.io.dizer("Treino é treino! Cada erro é um dado novo para o seu cérebro. Bora tentar de novo depois?")
        ctx.perfil.salvar()
        return
    ctx.io.dizer(f"Fim da rodada! Você acertou {acertos} de {total}.")
    if not vale_pontos:
        ctx.perfil.salvar()
        return
    eventos = ctx.jogo.ganhar(pontos, f"quiz ({acertos}/{total})") + ctx.jogo.registrar("quiz_acertos", acertos)
    if acertos == total == PERGUNTAS_POR_RODADA:
        eventos += ctx.jogo.ganhar(PONTOS["quiz_perfeito"], "rodada perfeita 💯")
        eventos += ctx.jogo.registrar("quiz_perfeitos")
    ctx.processar_eventos(eventos)
