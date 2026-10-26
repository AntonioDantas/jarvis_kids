"""Personalização: a criança escolhe a voz do Jarvis ouvindo uma amostra de cada uma."""

from __future__ import annotations

from jarvis import ui
from jarvis.audio.voz import PERFIS_VOZ, VOZ_PADRAO
from jarvis.contexto import Contexto


def perfil_de_voz(ctx: Contexto) -> dict:
    return PERFIS_VOZ.get(ctx.perfil.dados.get("voz_jarvis", VOZ_PADRAO), PERFIS_VOZ[VOZ_PADRAO])


def aplicar_voz(ctx: Contexto) -> None:
    ctx.io.voz.definir_padrao(perfil_de_voz(ctx))


def escolher_voz(ctx: Contexto) -> None:
    if not ctx.io.voz.ativa:
        ui.info("A voz está desligada neste computador (modo texto).")
        return
    ids = list(PERFIS_VOZ)
    ctx.io.dizer(f"Vou te mostrar as minhas vozes, {ctx.perfil.nome}! Escute e escolha a que você mais gostar.")
    try:
        for n, voz_id in enumerate(ids, 1):
            voz = PERFIS_VOZ[voz_id]
            ui.info(f"[{n}] {voz['nome']} — {voz['descricao']}")
            ctx.io.voz.falar(f"Opção {n}. Oi, {ctx.perfil.nome}! Eu sou o Jarvis com a voz {voz['nome'][2:]}.", voz)
    except KeyboardInterrupt:
        ctx.io.voz.alto_falante.parar()
    escolha = ctx.io.escolher("Qual voz você escolhe?", [f"{v['nome']} — {v['descricao']}" for v in PERFIS_VOZ.values()],
                              titulo="🎙️ ESCOLHA A MINHA VOZ")
    ctx.perfil.dados["voz_escolhida"] = True
    if escolha is not None:
        ctx.perfil.dados["voz_jarvis"] = ids[escolha]
        aplicar_voz(ctx)
        ctx.io.dizer("Pronto! A partir de agora eu falo assim. Para trocar, é só dizer: mudar a voz.")
    ctx.perfil.salvar()
