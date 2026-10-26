"""
Vozes das Escrituras: conversar com "hologramas educativos" de santos (com voz
própria e baseados só em fatos verificados) e ouvir histórias da Bíblia.
"""

from __future__ import annotations

import random
from datetime import date

from jarvis import ui
from jarvis.contexto import Contexto, carregar_dados
from jarvis.gamificacao import PONTOS
from jarvis.texto import contem_frase, normalizar


def santos() -> list[dict]:
    return carregar_dados("santos.json")["santos"]


def historias() -> list[dict]:
    return carregar_dados("historias_biblicas.json")["historias"]


def santo_do_dia(dia: date | None = None) -> str | None:
    dia = dia or date.today()
    return carregar_dados("calendario_santos.json")["dias"].get(dia.strftime("%m-%d"))


def encontrar_santo(texto: str) -> dict | None:
    """'quero falar com o carlo acutis' -> persona do Carlo Acutis."""
    t = normalizar(texto)
    for santo in santos():
        nomes = [santo["nome"], santo["apelido"]] + santo.get("palavras_chave", [])[:2]
        if any(contem_frase(t, n) for n in nomes):
            return santo
    return None


def ativar_santo(ctx: Contexto, santo: dict) -> None:
    ctx.persona = santo
    if ctx.cerebro:
        ctx.cerebro.esquecer()  # conversa nova com o santo
    cor = ui.CORES["santo"]
    ui.painel("◢ HOLOGRAMA EDUCATIVO ATIVADO ◣",
              f"{santo['emoji']}  {santo['nome']}  ({santo['anos']})\n"
              f"Festa: {santo['festa']} · Padroeiro {santo['padroeiro']}",
              cor, subtitulo="baseado em fatos verificados · diga 'voltar ao normal' para sair")
    ctx.io.efeitos.tocar("inicializar")
    ctx.io.dizer(santo["saudacao"], titulo=santo["nome"], cor=cor, voz=santo["voz"])
    if ctx.jogo.dentro_do_limite(f"santo_{santo['id']}", 1):
        ctx.processar_eventos(ctx.jogo.ganhar(PONTOS["conversa_santo"], f"visita a {santo['apelido']}")
                              + ctx.jogo.registrar_santo(santo["id"]))


def desativar_santo(ctx: Contexto) -> None:
    if ctx.persona:
        ctx.io.dizer(f"Holograma de {ctx.persona['apelido']} desligado. O Jarvis está de volta!")
        ctx.persona = None
        if ctx.cerebro:
            ctx.cerebro.esquecer()


def contar_historia(ctx: Contexto, historia: dict) -> None:
    cor = ui.CORES["fe"]
    ui.painel(f"{historia['emoji']} {historia['titulo']}", historia["texto"], cor,
              subtitulo=f"{historia['referencia']} — leia também na sua Bíblia!")
    try:
        ctx.io.voz.falar(f"{historia['titulo']}. {historia['texto']}", ctx.io.voz.com(velocidade=1.0))
    except KeyboardInterrupt:
        ctx.io.voz.alto_falante.parar()
    ctx.io.dizer(f"Lição da missão: {historia['licao']}", cor=cor)
    if ctx.jogo.dentro_do_limite("historia", 3):
        ctx.premiar(PONTOS["historia"], "história da Bíblia 📜", "historias")
    ctx.io.dizer(historia["pergunta"])


def executar(ctx: Contexto) -> str | None:
    """Retorna a resposta da criança à pergunta de reflexão (para o Jarvis comentar), se houver."""
    opcoes = ["😇 Conversar com um santo", "📜 Ouvir uma história da Bíblia", "🎲 História surpresa"]
    hoje_santo = santo_do_dia()
    if hoje_santo:
        ui.info(f"📅 Hoje a Igreja celebra: {hoje_santo}")
    escolha = ctx.io.escolher("Bem-vindo às Vozes das Escrituras! O que vamos fazer?", opcoes,
                              titulo="📖 VOZES DAS ESCRITURAS", cor=ui.CORES["fe"])
    if escolha is None:
        return None
    if escolha == 0:
        lista = santos()
        i = ctx.io.escolher("Com qual santo você quer conversar?",
                            [f"{s['emoji']} {s['nome']} — {s['anos']}" for s in lista],
                            titulo="😇 ESCOLHA O SANTO", cor=ui.CORES["santo"])
        if i is not None:
            ativar_santo(ctx, lista[i])
        return None
    lista = historias()
    if escolha == 1:
        i = ctx.io.escolher("Qual história você quer ouvir?",
                            [f"{h['emoji']} {h['titulo']}  [grey50]({h['referencia']})[/]" for h in lista],
                            titulo="📜 HISTÓRIAS DA BÍBLIA", cor=ui.CORES["fe"])
        if i is None:
            return None
        historia = lista[i]
    else:
        historia = random.choice(lista)
    contar_historia(ctx, historia)
    resposta = ctx.io.ouvir("Sua resposta (ou ENTER para pular)")
    if not resposta or normalizar(resposta).strip(" .!") in {"pular", "pula", "passar", "voltar", "sair", "nada"}:
        return None
    return f"Sobre a história '{historia['titulo']}' ({historia['referencia']}), eu respondo: {resposta}"
