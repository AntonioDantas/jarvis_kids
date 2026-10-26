"""Terço guiado: mistérios do dia, meditações para crianças e contas que vão se acendendo."""

from __future__ import annotations

from datetime import date

from jarvis import ui
from jarvis.contexto import Contexto, carregar_dados
from jarvis.fe.oracoes import oracoes
from jarvis.gamificacao import PONTOS

ORDINAIS = ("Primeiro", "Segundo", "Terceiro", "Quarto", "Quinto")
MODOS = [
    ("⚡ Mini-terço: 1 Ave-Maria em cada mistério (uns 6 minutos)", 1),
    ("📿 Terço completo: 10 Ave-Marias em cada mistério (uns 20 minutos)", 10),
    ("🔹 Só uma dezena: o primeiro mistério de hoje", 10),
]


def misterios_do_dia(dia: date | None = None) -> str:
    dia = dia or date.today()
    return carregar_dados("terco.json")["dias"][str(dia.weekday())]


def _texto(oracao_id: str) -> str:
    return " ".join(next(o for o in oracoes() if o["id"] == oracao_id)["linhas"])


def _rezar(ctx: Contexto, texto: str, rotulo: str = "") -> None:
    ui.linha_oracao(f"{rotulo}: {texto}" if rotulo else texto)
    ctx.io.voz.falar(texto, ctx.io.voz.com(velocidade=0.92))


def executar(ctx: Contexto) -> None:
    dados = carregar_dados("terco.json")
    hoje = misterios_do_dia()
    conjuntos = list(dados["misterios"])
    opcoes = [f"{dados['misterios'][c]['emoji']} {dados['misterios'][c]['nome']}"
              + ("  [grey50](os de hoje)[/]" if c == hoje else "") for c in conjuntos]
    i = ctx.io.escolher(f"Vamos rezar o terço! Hoje a Igreja medita os {dados['misterios'][hoje]['nome']}. "
                        "Quais mistérios você quer rezar?", opcoes, titulo="📿 TERÇO GUIADO", cor=ui.CORES["fe"])
    if i is None:
        return
    conjunto = dados["misterios"][conjuntos[i]]
    m = ctx.io.escolher("Qual tamanho de terço?", [nome for nome, _ in MODOS], titulo="📿 Tamanho",
                        cor=ui.CORES["fe"])
    if m is None:
        return
    ave_marias = MODOS[m][1]
    misterios = conjunto["lista"][:1] if m == 2 else conjunto["lista"]

    ctx.io.dizer("Reze comigo, em voz alta ou no coração. Para parar a qualquer momento, aperte Ctrl+C.",
                 cor=ui.CORES["fe"])
    try:
        _rezar(ctx, _texto("sinal_cruz"))
        _rezar(ctx, dados["oracoes"]["oferecimento"], "Oferecimento")
        if m == 1:
            _rezar(ctx, _texto("credo"))
        _rezar(ctx, _texto("pai_nosso"))
        for intencao in ("fé", "esperança", "caridade"):
            _rezar(ctx, _texto("ave_maria"), f"Ave-Maria pela {intencao}")
        _rezar(ctx, _texto("gloria"))

        for n, misterio in enumerate(misterios):
            titulo = f"{ORDINAIS[n]} Mistério: {misterio['titulo']}"
            ui.painel(f"{conjunto['emoji']} {titulo}", misterio["meditacao"], ui.CORES["fe"],
                      subtitulo=misterio["referencia"], destaque=f"Fruto do mistério: {misterio['fruto']}")
            ctx.io.dizer(f"{titulo}. {misterio['meditacao']}", mostrar=False, voz=ctx.io.voz.com(velocidade=0.95))
            _rezar(ctx, _texto("pai_nosso"))
            for conta in range(1, ave_marias + 1):
                ui.contas(conta, ave_marias)
                ctx.io.voz.falar(_texto("ave_maria"), ctx.io.voz.com(velocidade=0.95))
            _rezar(ctx, _texto("gloria"))
            _rezar(ctx, dados["oracoes"]["fatima"])
        _rezar(ctx, dados["oracoes"]["salve_rainha"], "Salve-Rainha")
        _rezar(ctx, _texto("sinal_cruz"))
    except KeyboardInterrupt:
        ctx.io.voz.alto_falante.parar()
        ctx.io.dizer("Tudo bem! Cada Ave-Maria rezada é uma rosa para Nossa Senhora.", cor=ui.CORES["fe"])
        return

    ctx.io.dizer("Amém! Que lindo! Nossa Senhora recebeu cada Ave-Maria como uma rosa.", cor=ui.CORES["fe"])
    if ctx.jogo.dentro_do_limite("terco", 1):
        pontos = PONTOS["terco"] if len(misterios) == 5 and ave_marias == 10 else PONTOS["oracao"] * 2
        ctx.premiar(pontos, "terço rezado 📿", "tercos")
        ctx.processar_eventos(ctx.jogo.registrar("oracoes"))
    else:
        ctx.perfil.salvar()
