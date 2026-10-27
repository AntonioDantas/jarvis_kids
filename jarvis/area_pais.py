"""
Área dos Pais (protegida por PIN): aprovar atividades, relatório, alertas de
segurança, bônus de mesada e configurações do Jarvis.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from config import MODELOS_SUGERIDOS, Preferencias
from jarvis import ui
from jarvis.contexto import Contexto
from jarvis.gamificacao import MEDALHAS, PONTOS
from jarvis.mesada import ErroMesada
from jarvis.texto import formatar_reais, reais_por_extenso

COR = "#ff87d7"
ROTULOS_ESTATISTICAS = {
    "perguntas": "Perguntas feitas", "quiz_acertos": "Acertos no quiz", "oracoes": "Orações",
    "oracoes_matinais": "Orações matinais", "exames": "Exames de consciência", "historias": "Histórias bíblicas",
    "tarefas": "Atividades concluídas", "dizimos_entregues": "Dízimos entregues", "doacoes_entregues": "Doações",
    "metas_atingidas": "Metas atingidas", "conversas_santos": "Conversas com santos",
    "maior_sequencia": "Maior sequência (dias)",
}


def ler_percentual(texto: str) -> float | None:
    """'1', '0,8', '1.5%' -> número entre 0 e 5 (trava contra erros de digitação)."""
    m = re.search(r"\d+(?:[.,]\d+)?", texto or "")
    if not m:
        return None
    return max(0.0, min(5.0, float(m.group(0).replace(",", "."))))


def hash_pin(pin: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), sal.encode(), 120_000).hex()


def definir_pin(prefs: Preferencias, pin: str) -> None:
    prefs.pin_pais_sal = secrets.token_hex(8)
    prefs.pin_pais_hash = hash_pin(pin, prefs.pin_pais_sal)
    prefs.salvar()


def pin_correto(prefs: Preferencias, pin: str) -> bool:
    return bool(prefs.pin_pais_hash) and hmac.compare_digest(hash_pin(pin, prefs.pin_pais_sal), prefs.pin_pais_hash)


def _ler_pin(rotulo: str) -> str:
    try:
        return ui.entrada(rotulo, tipo="pin").strip()
    except EOFError:
        return ""


def criar_pin_interativo(prefs: Preferencias) -> bool:
    ui.info("O PIN protege a Área dos Pais e liga a aprovação das atividades da mesada.")
    pin = _ler_pin("Novo PIN (4 a 8 números)")
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        ui.aviso("PIN inválido: use de 4 a 8 números.")
        return False
    if _ler_pin("Repita o PIN") != pin:
        ui.aviso("Os PINs não conferem.")
        return False
    definir_pin(prefs, pin)
    ui.sucesso("PIN definido!")
    return True


def verificar_acesso(ctx: Contexto) -> bool:
    if not ctx.prefs.tem_pin:
        ui.fala("Ainda não há PIN dos pais. Vamos criar um agora? (somente um adulto)", "ÁREA DOS PAIS", COR)
        return criar_pin_interativo(ctx.prefs)
    for tentativa in range(3):
        if pin_correto(ctx.prefs, _ler_pin("PIN dos pais")):
            return True
        ui.aviso(f"PIN incorreto ({tentativa + 1}/3).")
    ctx.io.efeitos.tocar("erro")
    return False


def aprovar_atividades(ctx: Contexto) -> None:
    if not ctx.mesada.pendentes:
        ui.info("Nenhuma atividade esperando aprovação. 👍")
        return
    for pendente in list(ctx.mesada.pendentes):
        quando = pendente["data"][:16].replace("T", " ")
        ui.fala(f"{pendente['nome']} — {formatar_reais(pendente['valor'])}  (registrada em {quando})", "Aprovar?", COR)
        acao = ctx.io.escolher("", ["✅ Aprovar", "✏️ Aprovar com outro valor", "❌ Não aprovar", "⏭️ Decidir depois"],
                               titulo="Decisão", falar=False, cor=COR)
        try:
            if acao == 0:
                resultado = ctx.mesada.aprovar(pendente["id"])
            elif acao == 1:
                valor = ctx.io.pedir_valor("Qual valor você aprova?", falar=False)
                if not valor:
                    continue
                resultado = ctx.mesada.aprovar(pendente["id"], valor)
            elif acao == 2:
                ctx.mesada.recusar(pendente["id"])
                ui.info("Atividade não aprovada. Que tal conversar sobre ela com a criança?")
                continue
            else:
                continue
        except ErroMesada as exc:
            ui.erro(str(exc))
            continue
        total = reais_por_extenso(sum(resultado.distribuicao.values()))
        ui.sucesso(f"Aprovado! {total} nos cofrinhos.")
        eventos = ctx.jogo.ganhar(PONTOS["tarefa"], f"atividade aprovada: {pendente['nome']}")
        eventos += ctx.jogo.registrar("tarefas")
        for _ in resultado.metas_atingidas:
            eventos += ctx.jogo.registrar("metas_atingidas")
        ctx.processar_eventos(eventos)


def relatorio(ctx: Contexto) -> None:
    jogo = ctx.jogo
    _i, nivel, emoji, *_ = jogo.nivel
    est = jogo.estatisticas
    linhas = [["Nível", f"{emoji} {nivel} ({jogo.pontos} pontos)"],
              ["Sequência atual", f"{jogo.jogo['dias_seguidos']} dia(s)"],
              ["Medalhas", f"{len(jogo.jogo['medalhas'])} de {len(MEDALHAS)}"],
              ["Uso hoje", f"{ctx.perfil.dados['uso']['segundos'] // 60} min"]]
    linhas += [[rotulo, str(est.get(chave, 0))] for chave, rotulo in ROTULOS_ESTATISTICAS.items()]
    desafio = jogo.jogo.get("desafio_virtude")
    if desafio:
        linhas.append(["Desafio de virtude", f"{desafio['virtude']}: {desafio['desafio']} ({desafio['data']})"])
    ui.tabela(f"📊 RELATÓRIO DE {ctx.perfil.nome.upper()}", ["Item", "Valor"], linhas, COR)
    ui.tabela("🐷 Cofrinhos", ["Cofrinho", "%", "Saldo", "Meta"],
              [[f"{c['emoji']} {c['nome']}", f"{c['percentual']}%", formatar_reais(c["saldo"]),
                formatar_reais(c["meta"]) if c.get("meta") else "—"] for c in ctx.mesada.cofrinhos], COR)
    investido = ctx.mesada.investimento
    ui.info(f"📈 Rendimentos pagos pelo Banco da Família até hoje: {formatar_reais(investido['rendimento_total'])} "
            f"(taxa atual: {ctx.prefs.rendimento_mensal_pct:g}% ao mês)".replace(".", ","))
    ui.info("Privacidade: o Exame de Consciência nunca grava as respostas da criança.")


def alertas(ctx: Contexto) -> None:
    lista = ctx.perfil.dados["alertas"]
    if not lista:
        ui.info("Nenhum alerta de segurança registrado. 🛡️")
        return
    nomes = {"risco": "🚨 Risco / pedido de ajuda", "perigoso": "⚠️ Desafio perigoso", "apostas": "🎰 Apostas",
             "ia_bloqueada": "🤖 Resposta da IA barrada pela trava doutrinária (revise a pergunta)"}
    ui.tabela("🚨 ALERTAS DE SEGURANÇA", ["Quando", "Tipo", "O que a criança disse", "Novo?"],
              [[a["data"][:16].replace("T", " "), nomes.get(a["categoria"], a["categoria"]), a["texto"],
                "●" if not a["lido"] else ""] for a in lista[-20:]], "#ff5f5f")
    ui.info("Nos alertas de risco, o Jarvis respondeu com uma mensagem fixa de acolhimento e orientou procurar um "
            "adulto. Converse com a criança com calma. Em caso de risco: CVV 188 · Disque 100 · Polícia 190.")
    for a in lista:
        a["lido"] = True
    ctx.perfil.salvar()


def bonus(ctx: Contexto) -> None:
    valor = ctx.io.pedir_valor("Valor do bônus ou ajuste de mesada:", falar=False)
    if not valor:
        return
    motivo = ctx.io.pedir_texto("Motivo (a criança verá no extrato):", falar=False) or "Bônus dos pais"
    resultado = ctx.mesada.depositar(valor, motivo)
    ui.sucesso(f"{formatar_reais(valor)} distribuídos nos cofrinhos.")
    for _ in resultado.metas_atingidas:
        ctx.processar_eventos(ctx.jogo.registrar("metas_atingidas"))


ANIMACOES = {"auto": "automáticas (leves em PC sem placa de vídeo)", "completas": "completas", "leves": "leves"}


def configuracoes(ctx: Contexto) -> None:
    p = ctx.prefs
    while True:
        opcoes = [
            f"🧠 Modelo de IA: {p.modelo_llm or 'automático (' + ctx.plano.modelo_llm + ')'}",
            f"🔊 Motor de voz: {p.motor_voz}",
            f"🗣️ Voz do Jarvis (Kokoro): {p.voz_kokoro}",
            f"🎙️ Modo de escuta: {'mãos-livres' if p.modo_escuta == 'maos_livres' else 'apertar ENTER'}",
            f"✅ Aprovação das atividades: {'ligada' if p.aprovacao_dos_pais else 'desligada'}",
            f"⏱️ Limite diário de uso: {f'{p.limite_minutos_diarios} min' if p.limite_minutos_diarios else 'sem limite'}",
            f"🎁 Bônus de mesada por nível: {formatar_reais(p.bonus_nivel_centavos)}",
            f"📈 Rendimento do Investimento (Banco da Família): {p.rendimento_mensal_pct:g}% ao mês".replace(".", ","),
            f"🎵 Efeitos sonoros: {'ligados' if p.efeitos_sonoros else 'desligados'}",
            f"🛡️ Registrar alertas de segurança: {'sim' if p.alertas_seguranca else 'não'}",
            f"⛪ Missa de domingo: {p.missa_horario or 'sem horário'}" + (f" — {p.missa_local}" if p.missa_local else ""),
            f"✨ Animações da janela: {ANIMACOES.get(p.animacoes, p.animacoes)}",
        ]
        i = ctx.io.escolher("", opcoes, titulo="⚙️ CONFIGURAÇÕES (valem ao religar o Jarvis)", falar=False, cor=COR)
        if i is None:
            p.salvar()
            return
        if i == 0:
            modelos = list(MODELOS_SUGERIDOS)
            j = ctx.io.escolher("", ["Automático (recomendado)"] + [f"{m} — {d}" for m, d in MODELOS_SUGERIDOS.items()],
                                titulo="Modelo", falar=False, cor=COR)
            if j is not None:
                p.modelo_llm = "" if j == 0 else modelos[j - 1]
        elif i == 1:
            motores = ["auto", "kokoro", "sistema", "edge", "mudo"]
            j = ctx.io.escolher("", ["Automático", "Kokoro (neural, local)", "Voz do sistema (offline)",
                                     "Edge-TTS (online — envia o texto à Microsoft)", "Mudo (só texto)"],
                                titulo="Voz", falar=False, cor=COR)
            if j is not None:
                if motores[j] == "edge":
                    ui.aviso("Edge-TTS precisa de internet e envia as frases do Jarvis aos servidores da Microsoft.")
                p.motor_voz = motores[j]
        elif i == 2:
            vozes = ["pm_alex", "pm_santa", "pf_dora"]
            j = ctx.io.escolher("", ["pm_alex (masculina, jovem)", "pm_santa (masculina, grave)", "pf_dora (feminina)"],
                                titulo="Voz do Jarvis", falar=False, cor=COR)
            if j is not None:
                p.voz_kokoro = vozes[j]
        elif i == 3:
            p.modo_escuta = "apertar_enter" if p.modo_escuta == "maos_livres" else "maos_livres"
            ctx.io.maos_livres = p.modo_escuta == "maos_livres" and ctx.io.escuta_ativa  # vale na hora
            ui.modo_escuta(ctx.io.maos_livres)
            if p.modo_escuta == "maos_livres" and not ctx.io.escuta_ativa:
                ui.aviso("Sem microfone funcionando, o mãos-livres fica guardado para quando houver um.")
        elif i == 4:
            p.aprovacao_dos_pais = not p.aprovacao_dos_pais
        elif i == 5:
            minutos = ctx.io.pedir_numero("Minutos por dia (0 = sem limite):", falar=False)
            if minutos is not None:
                p.limite_minutos_diarios = max(0, minutos)
        elif i == 6:
            valor = ctx.io.pedir_valor("Bônus por nível (0 = sem bônus):", falar=False, permitir_zero=True)
            if valor is not None:
                p.bonus_nivel_centavos = valor
        elif i == 7:
            ui.info("Vocês são o 'Banco da Família': o rendimento é dinheiro de verdade que vocês acrescentam. "
                    "Referência: 1% ao mês fica perto da poupança/CDI; mais que isso incentiva a criança a investir.")
            taxa = ler_percentual(ctx.io.ouvir("Rendimento ao mês em % (ex.: 1 ou 0,8; 0 desliga)"))
            if taxa is not None:
                p.rendimento_mensal_pct = taxa
                ctx.mesada.taxa_rendimento = taxa
        elif i == 8:
            p.efeitos_sonoros = not p.efeitos_sonoros
        elif i == 9:
            p.alertas_seguranca = not p.alertas_seguranca
        elif i == 10 and ctx.agenda is not None:
            from jarvis.painel_agenda import definir_missa

            definir_missa(ctx)
        elif i == 11:
            ordem = list(ANIMACOES)
            atual = ordem.index(p.animacoes) if p.animacoes in ordem else -1
            p.animacoes = ordem[(atual + 1) % len(ordem)]
        p.salvar()


def executar(ctx: Contexto) -> None:
    if not verificar_acesso(ctx):
        return
    while True:
        novos = sum(1 for a in ctx.perfil.dados["alertas"] if not a["lido"])
        i = ctx.io.escolher("", [
            f"✅ Aprovar atividades ({len(ctx.mesada.pendentes)} pendente(s))",
            f"📊 Relatório de {ctx.perfil.nome}",
            f"🚨 Alertas de segurança ({novos} novo(s))",
            "🎁 Dar bônus / ajuste de mesada",
            "⚙️ Configurações do Jarvis",
            "🔑 Trocar PIN",
        ], titulo="👨‍👩‍👧 ÁREA DOS PAIS", falar=False, cor=COR)
        if i is None:
            return
        [aprovar_atividades, relatorio, alertas, bonus, configuracoes,
         lambda c: criar_pin_interativo(c.prefs)][i](ctx)
