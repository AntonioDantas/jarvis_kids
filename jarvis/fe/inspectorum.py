"""
Inspectorum — Exame de Consciência infantil baseado nos Dez Mandamentos.

Princípios: foco em crescimento e virtudes (não em medo ou culpa), e
PRIVACIDADE TOTAL: as respostas da criança nunca são gravadas nem enviadas
à IA. O Jarvis só registra que o exame foi feito (para os pontos) e o
"desafio de virtude" escolhido.
"""

from __future__ import annotations

import random

from jarvis import ui
from jarvis.armazenamento import hoje
from jarvis.contexto import Contexto, carregar_dados
from jarvis.fe import oracoes
from jarvis.gamificacao import PONTOS


def executar(ctx: Contexto) -> None:
    dados = carregar_dados("exame_consciencia.json")
    modo = ctx.io.escolher(
        "Inspectorum pronto. Você quer o escaneamento rápido, com três mandamentos, ou o completo, com os dez?",
        ["⚡ Rápido (3 mandamentos, uns 2 minutos)", "🔬 Completo (10 mandamentos)"],
        titulo="🔍 INSPECTORUM · Exame de Consciência", cor=ui.CORES["fe"],
    )
    if modo is None:
        return
    mandamentos = dados["mandamentos"]
    if modo == 0:
        mandamentos = sorted(random.sample(mandamentos, 3), key=lambda m: m["numero"])

    for frase in dados["abertura"]:
        ctx.io.dizer(frase, titulo="INSPECTORUM", cor=ui.CORES["fe"])

    try:
        for m in mandamentos:
            perguntas = "\n".join(f"◇ {pergunta}" for pergunta in m["perguntas"])
            ui.painel(f"{m['numero']}º · {m['titulo']}", f"{m['explicacao']}\n\n{perguntas}", ui.CORES["fe"],
                      destaque=f"Virtude: {m['virtude']}")
            ctx.io.dizer(f"{m['numero']}º mandamento: {m['titulo']}. {m['explicacao']} " + " ".join(m["perguntas"]),
                         mostrar=False)
            ui.info("Pense em silêncio. Sua resposta fica só entre você e Deus.")
            if ctx.io.maos_livres:
                ctx.io.ouvir("Diga “próximo” para continuar", tipo="continuar")
            else:
                ui.entrada("Aperte ENTER para continuar", tipo="continuar")
    except (KeyboardInterrupt, EOFError):
        ui.info("Exame interrompido. Tudo bem, você pode voltar quando quiser.")
        return

    escolhido = ctx.io.escolher(
        "Muito bem! Agora escolha um desafio de virtude para treinar amanhã.",
        [f"{m['virtude']}: {m['desafio']}" for m in mandamentos],
        titulo="🎯 DESAFIO DE VIRTUDE", cor=ui.CORES["fe"],
    )
    if escolhido is not None:
        desafio = mandamentos[escolhido]
        ctx.perfil.jogo["desafio_virtude"] = {"data": hoje(), "virtude": desafio["virtude"],
                                              "desafio": desafio["desafio"]}
        ctx.io.dizer(f"Missão aceita! Treino de {desafio['virtude']}: {desafio['desafio']}")

    ctx.io.dizer("Agora vamos rezar juntos o Ato de Contrição.", cor=ui.CORES["fe"])
    for linha in next(o for o in oracoes.oracoes() if o["id"] == "ato_contricao")["linhas"]:
        ui.linha_oracao(linha)
        ctx.io.voz.falar(linha, ctx.io.voz.com(velocidade=0.9))
    for frase in dados["encerramento"]:
        ctx.io.dizer(frase, titulo="INSPECTORUM", cor=ui.CORES["fe"])

    if ctx.jogo.dentro_do_limite("exame", 1):
        ctx.premiar(PONTOS["exame"], "Exame de Consciência 💎", "exames")
    else:
        ctx.perfil.salvar()
