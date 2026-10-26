"""
Agenda do agente: compromissos da criança + santo do dia + Missa de domingo.

Na janela futurista, o comando abre o planner (calendário completo). No terminal, um
menu simples permite ver os próximos dias, marcar, apagar e definir o horário da Missa.
"""

from __future__ import annotations

from datetime import date, timedelta

from jarvis import ui
from jarvis.agenda import CATEGORIAS, descrever_quando, hora_falada, resumo_do_dia
from jarvis.texto import data_por_extenso, ler_data, ler_hora


def executar(ctx) -> None:
    hoje = date.today()
    itens = ctx.agenda.do_dia(hoje)
    ui.agenda(itens, f"📅 HOJE · {data_por_extenso(hoje).upper()}")
    ctx.io.dizer(resumo_do_dia(itens, hoje), mostrar=False)
    if ui.abrir_planner():
        ui.info("Planner aberto! Clique num dia para marcar um compromisso. "
                "Ou fale comigo: \"marca prova de matemática na sexta às 8h\".")
        return
    while True:
        i = ctx.io.escolher("O que vamos fazer na agenda?",
                            ["📆 Ver os próximos 7 dias", "➕ Marcar um compromisso", "🗑️ Apagar um compromisso",
                             "⛪ Horário da Missa de domingo"], titulo="📅 AGENDA DO AGENTE", falar=False)
        if i is None:
            return
        [proximos_dias, marcar, apagar, definir_missa][i](ctx)


def proximos_dias(ctx) -> None:
    hoje = date.today()
    linhas = []
    for n in range(7):
        dia = hoje + timedelta(days=n)
        for item in ctx.agenda.do_dia(dia):
            quando = "Hoje" if n == 0 else "Amanhã" if n == 1 else data_por_extenso(dia).capitalize()
            linhas.append([quando, item.hora or "—", f"{item.emoji} {item.titulo}"])
    ui.tabela("📆 PRÓXIMOS 7 DIAS", ["Dia", "Hora", "O quê"], linhas, "#ffd75f")


def salvar(ctx, titulo: str, dia: date, hora: str = "", categoria: str = "outro", repetir: str = "") -> bool:
    analise = ctx.guardiao.analisar_entrada(titulo)
    if analise and analise.bloquear:
        ctx.io.dizer("Hum, isso não pode ir para a agenda. Vamos marcar outra coisa?")
        return False
    try:
        ctx.agenda.adicionar(titulo, dia, hora, categoria, repetir)
    except ValueError as exc:
        ui.aviso(str(exc))
        return False
    ui.sucesso(f"{CATEGORIAS.get(categoria, CATEGORIAS['outro'])[0]} {titulo} — {descrever_quando(dia, hora)}")
    repete = {"semanal": " Vou lembrar toda semana.", "anual": " Vou lembrar todo ano."}.get(repetir, "")
    ctx.io.dizer(f"Anotado na agenda: {titulo}, {descrever_quando(dia, hora)}.{repete}", mostrar=False)
    if ctx.jogo.dentro_do_limite("agenda", 3):
        ctx.premiar(5, "Agente organizado: compromisso na agenda!", "compromissos")
    atualizar_tela(ctx)
    return True


def marcar(ctx) -> None:
    titulo = ctx.io.pedir_texto("Qual é o compromisso? Por exemplo: prova de matemática.")
    if not titulo:
        return
    dia = _perguntar_dia(ctx)
    if dia is None:
        return
    hora = ler_hora(ctx.io.pedir_texto("Que horas? Por exemplo: 8h, 3 da tarde. Ou diga 'sem hora'.", falar=False))
    opcoes = [f"{emoji} {nome}" for emoji, nome in CATEGORIAS.values()]
    i = ctx.io.escolher("Que tipo de compromisso é?", opcoes, titulo="🏷️ TIPO", falar=False)
    categoria = list(CATEGORIAS)[i] if i is not None else "outro"
    repetir = "semanal" if ctx.io.confirmar("Repete toda semana?", falar=False) else ""
    salvar(ctx, titulo, dia, hora, categoria, repetir)


def _perguntar_dia(ctx) -> date | None:
    for _ in range(2):
        dia = ler_data(ctx.io.pedir_texto("Para qual dia? Por exemplo: amanhã, sexta, 15/11.", falar=False))
        if dia:
            return dia
        ui.aviso("Não entendi o dia. Exemplos: amanhã · sexta · dia 20 · 15/11 · 2 de dezembro")
    return None


def apagar(ctx) -> None:
    hoje = date.today()
    itens = [i for i in ctx.agenda.intervalo(hoje, hoje + timedelta(days=60)) if not i.automatico]
    unicos = list({i.id: i for i in itens}.values())[:12]
    if not unicos:
        ui.info("Você ainda não marcou nenhum compromisso.")
        return
    opcoes = [f"{i.emoji} {i.titulo} — {descrever_quando(date.fromisoformat(i.data), i.hora)}" for i in unicos]
    i = ctx.io.escolher("Qual compromisso você quer apagar?", opcoes, titulo="🗑️ APAGAR", falar=False)
    if i is not None and ctx.io.confirmar(f"Apagar '{unicos[i].titulo}'?", falar=False):
        ctx.agenda.remover(unicos[i].id)
        ui.sucesso("Compromisso apagado.")
        atualizar_tela(ctx)


def definir_missa(ctx) -> None:
    atual = ctx.prefs.missa_horario
    if atual:
        local = f" — {ctx.prefs.missa_local}" if ctx.prefs.missa_local else ""
        ui.info(f"Horário atual: Missa às {hora_falada(atual)}{local}")
    hora = ler_hora(ctx.io.pedir_texto("Que horas é a Missa de domingo da sua família? Por exemplo: 9h, 10 e meia "
                                       "da manhã, 7 da noite."))
    if not hora:
        ui.aviso("Não entendi o horário. Exemplos: 9h · 10:30 · 7 da noite")
        return
    local = ctx.io.pedir_texto("Em qual igreja ou paróquia? (Pode pular dizendo 'voltar'.)", falar=False)
    ctx.prefs.missa_horario, ctx.prefs.missa_local = hora, local[:40]
    ctx.prefs.salvar()
    ctx.agenda.missa_horario, ctx.agenda.missa_local = ctx.prefs.missa_horario, ctx.prefs.missa_local
    ctx.io.dizer(f"Pronto! Todo domingo eu lembro você da Missa às {hora_falada(hora)}.")
    atualizar_tela(ctx)


def marcar_pelo_que_foi_dito(ctx, pedido: dict) -> None:
    """'Jarvis, marca prova na sexta às 8h' -> confirma e salva."""
    dia = pedido["data"] or _perguntar_dia(ctx)
    if dia is None:
        return
    if ctx.io.confirmar(f"Quer que eu marque '{pedido['titulo']}' {descrever_quando(dia, pedido['hora'])}?"):
        salvar(ctx, pedido["titulo"], dia, pedido["hora"], pedido["categoria"], pedido["repetir"])


def atualizar_tela(ctx) -> None:
    """Na janela futurista, atualiza o painel 'Hoje na Igreja / Agenda de hoje'."""
    if ui.web_ativa():
        from jarvis.web.tela_web import dados_laterais

        ui.lateral(dados_laterais(ctx.agenda))
