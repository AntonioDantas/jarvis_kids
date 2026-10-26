"""Oração guiada: o Jarvis reza linha por linha, devagar, para a criança rezar junto."""

from __future__ import annotations

from datetime import datetime

from rich.panel import Panel
from rich.text import Text

from jarvis import ui
from jarvis.contexto import Contexto, carregar_dados
from jarvis.gamificacao import PONTOS


def oracoes() -> list[dict]:
    return carregar_dados("oracoes.json")["oracoes"]


def _sugerida() -> str:
    hora = datetime.now().hour
    return "manha" if hora < 12 else "refeicao" if 12 <= hora < 14 else "noite" if hora >= 18 else "estudo"


def executar(ctx: Contexto, oracao_id: str | None = None) -> None:
    lista = oracoes()
    if oracao_id is None:
        sugestao = _sugerida()
        lista = sorted(lista, key=lambda o: o["id"] != sugestao)  # sugestão do horário em 1º lugar
        indice = ctx.io.escolher(
            "Vamos rezar juntos! Qual oração você escolhe?",
            [f"{o['emoji']} {o['titulo']}" + ("  [grey50](sugerida agora)[/]" if o["id"] == sugestao else "")
             for o in lista],
            titulo="🙏 ORAÇÃO GUIADA", cor=ui.CORES["fe"],
        )
        if indice is None:
            return
        oracao = lista[indice]
    else:
        oracao = next(o for o in lista if o["id"] == oracao_id)

    intencao = ""
    if ctx.io.confirmar("Quer rezar por alguma intenção especial? Por alguém doente, pela família, por um amigo?"):
        intencao = ctx.io.pedir_texto("Por quem ou pelo que vamos rezar?")
        analise = ctx.guardiao.analisar_entrada(intencao) if intencao else None
        if analise:
            ctx.io.dizer(analise.resposta, cor=ui.CORES["alerta"])
            if analise.alerta_pais and ctx.prefs.alertas_seguranca:
                ctx.perfil.registrar_alerta(analise.categoria, intencao)
            return

    ui.console.print(Panel(Text("\n".join(oracao["linhas"]), style="#e4d7ff"),
                           title=f"[bold {ui.CORES['fe']}]{oracao['emoji']} {oracao['titulo']}[/]",
                           subtitle=f"[grey50]{oracao['origem']}[/]", border_style=ui.CORES["fe"]))
    ctx.io.dizer("Vamos começar. Reze comigo, em voz alta ou no coração.", mostrar=False)
    if intencao:
        ctx.io.dizer(f"Senhor, colocamos em tuas mãos esta intenção especial: {intencao.rstrip('.')}.", cor=ui.CORES["fe"])
    try:
        for linha in oracao["linhas"]:
            ui.console.print(f"  [bold {ui.CORES['fe']}]✝[/] [italic]{linha}[/]")
            ctx.io.voz.falar(linha, {"velocidade": 0.9})
    except KeyboardInterrupt:
        ctx.io.voz.alto_falante.parar()
        return

    if not ctx.io.confirmar("Amém! Você rezou junto comigo?"):
        ctx.io.dizer("Tudo bem! Deus está sempre pronto para te ouvir, a qualquer hora.")
        return
    ctx.io.dizer("Que lindo! Cada oração é uma conexão direta com o Céu, sem precisar de wi-fi.")
    if not ctx.jogo.dentro_do_limite("oracao", 3):
        ui.info("(Hoje você já ganhou os pontos de oração. Mas rezar vale sempre!)")
        return
    if datetime.now().hour < 12:
        ctx.premiar(PONTOS["oracao_matinal"], "oração matinal 🌅", "oracoes")
        ctx.processar_eventos(ctx.jogo.registrar("oracoes_matinais"))
    else:
        ctx.premiar(PONTOS["oracao"], "oração", "oracoes")
