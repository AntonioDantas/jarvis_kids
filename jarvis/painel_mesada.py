"""Painel interativo da Mesada por Mérito e dos Cofrinhos (educação financeira + dízimo)."""

from __future__ import annotations

import random

from rich.text import Text

from jarvis import ui
from jarvis.contexto import Contexto, carregar_dados
from jarvis.fe import oracoes
from jarvis.gamificacao import PONTOS
from jarvis.mesada import CATEGORIAS, DICA_PEDAGOGICA, SUGESTOES_ATIVIDADES, ErroMesada, ResultadoDeposito, simular_poupanca
from jarvis.texto import formatar_reais, reais_por_extenso

COR = ui.CORES["dinheiro"]
EMOJIS_SONHO = ["🎯", "🚲", "🎮", "⚽", "📚", "🎸", "🛹", "🧸", "🔭", "🎁"]


def mostrar_cofrinhos(ctx: Contexto) -> None:
    linhas = []
    for c in ctx.mesada.cofrinhos:
        if c.get("meta"):
            meta = Text.assemble(ui.barra(c["saldo"], c["meta"], 12, COR), (f" {formatar_reais(c['meta'])}", "grey62"))
        else:
            meta = Text("—", style="grey50")
        saldo = Text(formatar_reais(c["saldo"]), style=f"bold {COR}")
        linhas.append([f"{c['emoji']} {c['nome']}", f"{c['percentual']}%", saldo, meta])
    linhas.append(["[bold]TOTAL[/]", "100%", Text(formatar_reais(ctx.mesada.saldo_total()), style="bold"), ""])
    ui.tabela("🐷 MEUS COFRINHOS", ["Cofrinho", "Parte", "Saldo", "Meta"], linhas, COR)
    if ctx.mesada.pendentes:
        total = sum(p["valor"] for p in ctx.mesada.pendentes)
        ui.info(f"⏳ {len(ctx.mesada.pendentes)} atividade(s) esperando aprovação dos pais ({formatar_reais(total)}).")


def _anunciar_deposito(ctx: Contexto, valor: int, resultado: ResultadoDeposito) -> None:
    nomes = {c["id"]: f"{c['emoji']} {c['nome']}" for c in ctx.mesada.cofrinhos}
    for cid, parte in resultado.distribuicao.items():
        ui.console.print(f"    [{COR}]+{formatar_reais(parte)}[/] → {nomes.get(cid, cid)}")
    ctx.io.efeitos.tocar("moeda")
    ctx.io.dizer(f"Missão cumprida! {reais_por_extenso(valor)} foram divididos entre os seus cofrinhos.",
                 cor=COR, mostrar=False)
    for nome in resultado.metas_atingidas:
        ctx.io.dizer(f"META ATINGIDA no cofrinho {nome}! Paciência de astronauta dá resultado!", cor=COR)
        ctx.processar_eventos(ctx.jogo.registrar("metas_atingidas"))


def concluir_atividade(ctx: Contexto, atividade: dict | None = None) -> None:
    mesada = ctx.mesada
    if atividade is None:
        if not mesada.atividades:
            ctx.io.dizer("Você ainda não cadastrou atividades. Vamos cadastrar a primeira?", cor=COR)
            cadastrar_atividade(ctx)
            if not mesada.atividades:
                return
        i = ctx.io.escolher("Qual atividade você concluiu?",
                            [f"{a['emoji']} {a['nome']} — {formatar_reais(a['valor']) if a['valor'] else 'só pontos'}"
                             for a in mesada.atividades], titulo="✅ CONCLUÍ UMA ATIVIDADE!", cor=COR)
        if i is None:
            return
        atividade = mesada.atividades[i]

    precisa_aprovacao = ctx.prefs.aprovacao_dos_pais and ctx.prefs.tem_pin
    status, resultado = mesada.concluir_atividade(atividade["id"], precisa_aprovacao)
    if status == "pendente":
        ctx.io.efeitos.tocar("missao")
        ctx.io.dizer(f"Registrado: {atividade['nome']}! Enviei para os seus pais aprovarem. Quando aprovarem, "
                     f"{reais_por_extenso(atividade['valor'])} vão direto para os seus cofrinhos.", cor=COR)
        return
    if status == "creditado" and resultado:
        _anunciar_deposito(ctx, atividade["valor"], resultado)
    else:
        ctx.io.dizer(f"Muito bem! '{atividade['nome']}' vale Pontos de Sabedoria.", cor=COR)
    if ctx.jogo.dentro_do_limite("tarefa", 8):
        ctx.premiar(PONTOS["tarefa"], f"atividade: {atividade['nome']}", "tarefas")


def cadastrar_atividade(ctx: Contexto) -> None:
    existentes = {a["nome"] for a in ctx.mesada.atividades}
    sugestoes = [s for s in SUGESTOES_ATIVIDADES if s[0] not in existentes]
    opcoes = ["✏️  Criar uma atividade do meu jeito"] + [f"{e} {n}  [grey50]{CATEGORIAS[c]}[/]" for n, c, e in sugestoes]
    i = ctx.io.escolher("Escolha uma sugestão ou crie a sua própria atividade.", opcoes,
                        titulo="📋 NOVA ATIVIDADE", cor=COR)
    if i is None:
        return
    if i == 0:
        nome = ctx.io.pedir_texto("Qual é o nome da atividade? Por exemplo: ajudar a lavar o carro.")
        if not nome:
            return
        categorias = list(CATEGORIAS.items())
        c = ctx.io.escolher("Em que categoria ela se encaixa?", [n for _, n in categorias], titulo="Categoria", cor=COR)
        categoria, emoji = (categorias[c][0] if c is not None else "outro"), "⭐"
    else:
        nome, categoria, emoji = sugestoes[i - 1]
    ui.info(DICA_PEDAGOGICA)
    valor = ctx.io.pedir_valor(
        f"Quanto vale '{nome}'? Você decide o valor, mas combine com seus pais! Diga zero se valer só pontos.",
        permitir_zero=True)
    if valor is None:
        return
    try:
        ctx.mesada.adicionar_atividade(nome, valor, categoria, emoji)
    except ErroMesada as exc:
        ctx.io.dizer(str(exc), cor=ui.CORES["alerta"])
        return
    ctx.io.dizer(f"Atividade cadastrada: {nome}, valendo {reais_por_extenso(valor) if valor else 'só pontos'}!", cor=COR)


def gerenciar_atividades(ctx: Contexto) -> None:
    while True:
        lista = ctx.mesada.atividades
        opcoes = ["➕ Cadastrar nova atividade"] + [
            f"{a['emoji']} {a['nome']} — {formatar_reais(a['valor']) if a['valor'] else 'só pontos'}" for a in lista]
        i = ctx.io.escolher("", opcoes, titulo="📋 MINHAS ATIVIDADES", falar=False, cor=COR)
        if i is None:
            return
        if i == 0:
            cadastrar_atividade(ctx)
            continue
        atividade = lista[i - 1]
        acao = ctx.io.escolher(f"O que fazer com '{atividade['nome']}'?",
                               ["💲 Mudar o valor", "🗑️ Apagar atividade"], titulo=atividade["nome"], cor=COR)
        try:
            if acao == 0:
                valor = ctx.io.pedir_valor("Qual é o novo valor?", permitir_zero=True)
                if valor is not None:
                    ctx.mesada.alterar_valor(atividade["id"], valor)
            elif acao == 1 and ctx.io.confirmar(f"Apagar a atividade '{atividade['nome']}'?"):
                ctx.mesada.remover_atividade(atividade["id"])
        except ErroMesada as exc:
            ctx.io.dizer(str(exc), cor=ui.CORES["alerta"])


def criar_cofrinho(ctx: Contexto) -> None:
    nome = ctx.io.pedir_texto("Qual é o seu sonho? Por exemplo: bicicleta nova, um livro, um jogo.")
    if not nome:
        return
    meta = ctx.io.pedir_valor(f"Quanto custa '{nome}'? Essa será a meta do cofrinho.")
    e = ctx.io.escolher("Escolha um ícone para o cofrinho.", EMOJIS_SONHO, titulo="Ícone", falar=False, cor=COR)
    try:
        ctx.mesada.criar_cofrinho(nome, EMOJIS_SONHO[e] if e is not None else "🎯", meta or 0)
    except ErroMesada as exc:
        ctx.io.dizer(str(exc), cor=ui.CORES["alerta"])
        return
    ctx.io.dizer(f"Cofrinho '{nome}' criado! Agora escolha quanto de cada mesada vai para ele.", cor=COR)
    ajustar_percentuais(ctx)


def ajustar_percentuais(ctx: Contexto) -> None:
    cofrinhos = ctx.mesada.cofrinhos
    livre = next(c for c in cofrinhos if c["id"] == "gastar")
    ctx.io.dizer("Vamos montar o seu plano! Para cada cofrinho, diga a porcentagem. "
                 "O que sobrar vai para Gastar com Sabedoria. Muitas famílias separam 10% para o dízimo.", cor=COR)
    novos, soma = {}, 0
    for c in cofrinhos:
        if c is livre:
            continue
        ui.info(f"Usado até agora: {soma}% · disponível: {100 - soma}%")
        pct = ctx.io.pedir_numero(f"{c['emoji']} {c['nome']}: quantos por cento? Agora é {c['percentual']}.", falar=False)
        if pct is None:
            ui.info("Ajuste cancelado.")
            return
        novos[c["id"]] = pct
        soma += pct
    if soma > 100:
        ctx.io.dizer(f"Ops! Deu {soma}%, passou de 100. Vamos tentar de novo depois.", cor=ui.CORES["alerta"])
        return
    novos[livre["id"]] = 100 - soma
    try:
        ctx.mesada.definir_percentuais(novos)
    except ErroMesada as exc:
        ctx.io.dizer(str(exc), cor=ui.CORES["alerta"])
        return
    ctx.io.dizer(f"Plano salvo! {100 - soma}% vai para Gastar com Sabedoria.", cor=COR)


def _escolher_cofrinho(ctx: Contexto, pergunta: str, filtro=lambda c: True) -> dict | None:
    lista = [c for c in ctx.mesada.cofrinhos if filtro(c)]
    if not lista:
        ctx.io.dizer("Nenhum cofrinho disponível para isso agora.", cor=COR)
        return None
    i = ctx.io.escolher(pergunta, [f"{c['emoji']} {c['nome']} — {formatar_reais(c['saldo'])}" for c in lista],
                        titulo="🐷 Cofrinho", cor=COR)
    return lista[i] if i is not None else None


def gastar(ctx: Contexto) -> None:
    cofrinho = _escolher_cofrinho(ctx, "De qual cofrinho sai o dinheiro?",
                                  lambda c: c["saldo"] > 0 and c["tipo"] not in ("dizimo", "doacao"))
    if not cofrinho:
        return
    if cofrinho["tipo"] in ("poupanca", "meta") and not ctx.io.confirmar(
            "Esse é um cofrinho de sonho. Gastar agora vai adiar a sua meta. Tem certeza?"):
        return
    valor = ctx.io.pedir_valor("Quanto você vai gastar?")
    if not valor:
        return
    motivo = ctx.io.pedir_texto("Com o que você vai gastar?", falar=False)
    try:
        ctx.mesada.retirar(cofrinho["id"], valor, motivo)
    except ErroMesada as exc:
        ctx.io.dizer(str(exc), cor=ui.CORES["alerta"])
        return
    ctx.io.dizer(f"Anotado! Saíram {reais_por_extenso(valor)} de {cofrinho['nome']}. "
                 "Agente esperto anota tudo o que gasta!", cor=COR)


def transferir(ctx: Contexto) -> None:
    origem = _escolher_cofrinho(ctx, "De qual cofrinho vai sair?", lambda c: c["saldo"] > 0)
    if not origem:
        return
    destino = _escolher_cofrinho(ctx, "Para qual cofrinho vai?", lambda c: c["id"] != origem["id"])
    if not destino:
        return
    valor = ctx.io.pedir_valor("Quanto você quer transferir?")
    if not valor:
        return
    try:
        metas = ctx.mesada.transferir(origem["id"], destino["id"], valor)
    except ErroMesada as exc:
        ctx.io.dizer(str(exc), cor=ui.CORES["alerta"])
        return
    ctx.io.dizer(f"Transferência concluída: {reais_por_extenso(valor)} de {origem['nome']} para {destino['nome']}.", cor=COR)
    for nome in metas:
        ctx.io.dizer(f"META ATINGIDA no cofrinho {nome}!", cor=COR)
        ctx.processar_eventos(ctx.jogo.registrar("metas_atingidas"))


def entregar(ctx: Contexto) -> None:
    cofrinho = _escolher_cofrinho(ctx, "Você vai entregar o dízimo ou uma doação?",
                                  lambda c: c["tipo"] in ("dizimo", "doacao") and c["saldo"] > 0)
    if not cofrinho:
        return
    valor = cofrinho["saldo"]
    if not ctx.io.confirmar(f"Entregar todo o cofrinho {cofrinho['nome']}, {reais_por_extenso(valor)}?"):
        valor = ctx.io.pedir_valor("Quanto você vai entregar?")
        if not valor:
            return
    destino = ctx.io.pedir_texto("Para onde vai? Por exemplo: paróquia, campanha do agasalho, um vizinho.",
                                 falar=False) or cofrinho["nome"]
    try:
        ctx.mesada.entregar(cofrinho["id"], valor, destino)
    except ErroMesada as exc:
        ctx.io.dizer(str(exc), cor=ui.CORES["alerta"])
        return
    ctx.io.efeitos.tocar("medalha")
    if cofrinho["tipo"] == "dizimo":
        ctx.io.dizer("Que coração generoso! Deus ama quem dá com alegria, como diz São Paulo. "
                     "Quer rezar a Oração da Partilha comigo?", cor=COR)
        estatistica = "dizimos_entregues"
    else:
        ctx.io.dizer("Você acabou de fazer uma obra de misericórdia! Como o menino dos cinco pães, "
                     "o pouco partilhado vira muito.", cor=COR)
        estatistica = "doacoes_entregues"
    eventos = ctx.jogo.registrar(estatistica)
    if ctx.jogo.dentro_do_limite("entrega", 1):
        eventos = ctx.jogo.ganhar(10, "coração generoso ❤️") + eventos
    ctx.processar_eventos(eventos)
    if cofrinho["tipo"] == "dizimo" and ctx.io.confirmar("Vamos rezar a Oração da Partilha?", falar=False):
        oracoes.executar(ctx, "dizimo")


def simulador(ctx: Contexto) -> None:
    semanal = ctx.io.pedir_valor("Simulador de poupança! Quanto você conseguiria guardar por semana?")
    if not semanal:
        return
    juros = 1.0 if ctx.io.confirmar("Quer ver também com juros de 1% ao mês, como num investimento?", falar=False) else 0.0
    sem_juros = simular_poupanca(semanal, 52)
    com_juros = simular_poupanca(semanal, 52, juros) if juros else sem_juros
    linhas = [[f"{s} semanas", formatar_reais(sem_juros[s - 1]), formatar_reais(com_juros[s - 1])]
              for s in (4, 12, 26, 52)]
    ui.tabela("📈 SIMULADOR DE POUPANÇA", ["Tempo", "Guardando", "Com juros" if juros else "—"], linhas, COR)
    fala = f"Guardando {reais_por_extenso(semanal)} por semana, em um ano você terá {reais_por_extenso(sem_juros[-1])}!"
    if juros:
        fala += f" Com juros, seriam {reais_por_extenso(com_juros[-1])}. Os juros são o dinheiro trabalhando para você."
    ctx.io.dizer(fala, cor=COR)


def extrato(ctx: Contexto) -> None:
    nomes = {c["id"]: c["nome"] for c in ctx.mesada.cofrinhos}
    rotulos = {"deposito": "➕ Entrada", "retirada": "🛒 Gasto", "transferencia": "🔁 Transferência",
               "dizimo_entregue": "🙏 Dízimo entregue", "doacao_entregue": "❤️ Doação"}
    linhas = []
    for e in ctx.mesada.extrato(12):
        descricao = e["descricao"]
        if e["tipo"] == "retirada" and e.get("cofrinho") in nomes:
            descricao += f" ({nomes[e['cofrinho']]})"
        quando = e["data"][:16].replace("T", " ")
        linhas.append([quando, rotulos.get(e["tipo"], e["tipo"]), formatar_reais(e["valor"]), descricao])
    if not linhas:
        ctx.io.dizer("Seu extrato ainda está vazio. Conclua uma atividade para começar!", cor=COR)
        return
    ui.tabela("🧾 EXTRATO (últimas movimentações)", ["Quando", "Tipo", "Valor", "Descrição"], linhas, COR)


def executar(ctx: Contexto) -> None:
    acoes = [
        ("✅ Concluí uma atividade!", concluir_atividade),
        ("📋 Minhas atividades e valores", gerenciar_atividades),
        ("🎯 Criar cofrinho de sonho (meta)", criar_cofrinho),
        ("⚖️  Ajustar as porcentagens dos cofrinhos", ajustar_percentuais),
        ("🛒 Gastar dinheiro", gastar),
        ("🔁 Transferir entre cofrinhos", transferir),
        ("🙏 Entregar dízimo ou doação", entregar),
        ("📈 Simulador de poupança", simulador),
        ("🧾 Ver extrato", extrato),
    ]
    dica = random.choice(carregar_dados("dicas_financeiras.json")["dicas"])
    primeira = True
    while True:
        mostrar_cofrinhos(ctx)
        if primeira:
            ui.info(f"💡 {dica}")
        i = ctx.io.escolher(f"Central financeira aberta! {dica}" if primeira else "",
                            [nome for nome, _ in acoes], titulo="💰 MESADA & COFRINHOS", cor=COR, falar=primeira)
        primeira = False
        if i is None:
            return
        acoes[i][1](ctx)
