"""Oração guiada: o Jarvis reza linha por linha, devagar, para a criança rezar junto."""

from __future__ import annotations

from datetime import datetime

from jarvis import ui
from jarvis.contexto import Contexto, carregar_dados
from jarvis.fe.liturgia import dia_liturgico
from jarvis.gamificacao import PONTOS


def oracoes() -> list[dict]:
    return carregar_dados("oracoes.json")["oracoes"]


def _sugerida() -> str:
    hora = datetime.now().hour
    if hora < 11:
        return "manha"
    if hora < 13:  # meio-dia: Angelus, ou Rainha do Céu no Tempo Pascal
        return "regina_caeli" if dia_liturgico().tempo == "Tempo Pascal" else "angelus"
    return "estudo" if hora < 18 else "noite"


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
        if analise and analise.bloquear:
            ctx.io.dizer(analise.resposta, cor=ui.CORES["alerta"])
            if analise.alerta_pais and ctx.prefs.alertas_seguranca:
                ctx.perfil.registrar_alerta(analise.categoria, intencao)
            return

    ui.painel(f"{oracao['emoji']} {oracao['titulo']}", "\n".join(oracao["linhas"]), ui.CORES["fe"],
              subtitulo=oracao["origem"])
    ctx.io.dizer("Vamos começar. Reze comigo, em voz alta ou no coração.", mostrar=False)
    if intencao:
        ctx.io.dizer(f"Senhor, colocamos em tuas mãos esta intenção especial: {intencao.rstrip('.')}.", cor=ui.CORES["fe"])
    try:
        for linha in oracao["linhas"]:
            ui.linha_oracao(linha)
            ctx.io.voz.falar(linha, ctx.io.voz.com(velocidade=0.9))
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
