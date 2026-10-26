"""Tela do calendário litúrgico: tempo, cor, ano A/B/C, festas e contagem regressiva."""

from __future__ import annotations

from datetime import date, timedelta

from jarvis import ui
from jarvis.contexto import Contexto
from jarvis.fe.liturgia import dia_liturgico, proximas_grandes_festas, resumo_falado

CORES_TELA = {"verde": "green", "roxo": "#af5fff", "branco": "white", "vermelho": "red", "rosa": "#ff87d7"}


def executar(ctx: Contexto) -> None:
    hoje = dia_liturgico()
    linhas = [["Tempo litúrgico", hoje.tempo],
              ["Cor do dia", f"● {hoje.cor} — {hoje.significado_cor}"],
              ["Celebração", hoje.celebracao or "dia de semana"],
              ["Ano litúrgico", f"Ano {hoje.ano}: nos domingos lemos o Evangelho de {hoje.evangelista}"]]
    linhas += [[f"Faltam para {nome}", f"{dias} dia{'s' if dias != 1 else ''}"] for nome, dias in proximas_grandes_festas()]
    proximos = []
    for n in range(1, 15):
        dia = dia_liturgico(date.today() + timedelta(days=n))
        if dia.celebracao:
            proximos.append(f"{dia.data.strftime('%d/%m')}: {dia.celebracao}")
        if len(proximos) == 3:
            break
    if proximos:
        linhas.append(["Próximas festas", "\n".join(proximos)])
    ui.tabela(f"📅 CALENDÁRIO DA IGREJA — {hoje.data.strftime('%d/%m/%Y')}", ["", ""], linhas, CORES_TELA[hoje.cor]
              if hoje.cor != "branco" else ui.CORES["fe"])
    natal = dict(proximas_grandes_festas())["Natal"]
    ctx.io.dizer(f"{resumo_falado(hoje)} E faltam {natal} dias para o Natal!", mostrar=False)
