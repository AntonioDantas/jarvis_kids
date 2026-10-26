#!/usr/bin/env python3
"""
J.A.R.V.I.S. Kids — loop principal.

    Voz da criança ─► Silero VAD ─► faster-whisper ─► Guardião (entrada)
          ─► comandos (quiz, oração, exame, mesada...) ou
          ─► Biblioteca da Fé (RAG) ─► Ollama (streaming) ─► Guardião (saída)
          ─► Kokoro TTS (fala frase a frase) + Gamificação

Uso:
    python main.py                 # experiência completa: janela futurista + voz
    python main.py --terminal      # usa o terminal em vez da janela
    python main.py --texto         # sem microfone (só teclado)
    python main.py --mudo          # sem voz (só texto na tela)
    python main.py --maos-livres   # escuta contínua, sem apertar ENTER
    python main.py --diagnostico   # confere hardware, Ollama, áudio e modelos
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from datetime import datetime

# Privacidade: nada de telemetria das bibliotecas de IA.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from config import (  # noqa: E402
    PASTA_USUARIO,
    TEMPERATURA_FE,
    VERSAO,
    Preferencias,
    detectar_hardware,
    montar_contexto_fontes,
    planejar,
)

ARQUIVO_MODELOS = PASTA_USUARIO / "modelos_baixados.json"


def _modelos_baixados() -> dict:
    try:
        return json.loads(ARQUIVO_MODELOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"whisper": [], "kokoro": False}


def _marcar_modelos(whisper: str | None, kokoro: bool) -> None:
    dados = _modelos_baixados()
    if whisper and whisper not in dados["whisper"]:
        dados["whisper"].append(whisper)
    dados["kokoro"] = dados["kokoro"] or kokoro
    ARQUIVO_MODELOS.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_MODELOS.write_text(json.dumps(dados), encoding="utf-8")


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="J.A.R.V.I.S. Kids — assistente de voz local, católico e gamificado")
    p.add_argument("--texto", action="store_true", help="não usa o microfone (só teclado)")
    p.add_argument("--mudo", action="store_true", help="não fala (só texto na tela)")
    p.add_argument("--maos-livres", action="store_true", help="escuta contínua: não precisa apertar ENTER")
    p.add_argument("--modelo", help="força um modelo do Ollama (ex.: qwen2.5:7b)")
    p.add_argument("--perfil", help="nome da criança (pula a tela de escolha)")
    p.add_argument("--sem-efeitos", action="store_true", help="desliga os efeitos sonoros")
    p.add_argument("--diagnostico", action="store_true", help="mostra um raio-X do sistema e sai")
    p.add_argument("--preparar", action="store_true",
                   help="baixa de uma vez todos os modelos de IA (cérebro, ouvido e voz) e sai")
    p.add_argument("--redefinir-pin", action="store_true", help="apaga o PIN dos pais (esqueceu o PIN?)")
    p.add_argument("--terminal", action="store_true", help="usa o terminal em vez da janela futurista")
    p.add_argument("--tela-cheia", action="store_true", help="abre a janela do Jarvis em tela cheia")
    p.add_argument("--sem-janela", action="store_true",
                   help="liga a interface, mas não abre a janela (abra no navegador o endereço mostrado)")
    p.add_argument("--porta", type=int, default=8765, help="porta local da janela (padrão: 8765)")
    return p.parse_args()


def configurar_terminal() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


# =============================================================================
#  Janela futurista (servidor local + navegador em modo aplicativo)
# =============================================================================
class Interface:
    def __init__(self, servidor, janela, tela, ponte):
        self.servidor, self.janela, self.tela, self.ponte = servidor, janela, tela, ponte

    def encerrar(self) -> None:
        self.ponte.emitir("desligado")
        if self.ponte.tem_janela:
            time.sleep(1.5)  # dá tempo de a janela mostrar a despedida
        self.janela.fechar()
        self.servidor.desligar()


def iniciar_interface(args: argparse.Namespace) -> Interface | None:
    """Liga a janela do Jarvis. Se não for possível, volta para o terminal."""
    if args.terminal:
        return None
    from jarvis import ui
    from jarvis.web.janela import Janela
    from jarvis.web.ponte import Ponte
    from jarvis.web.servidor import iniciar_servidor
    from jarvis.web.tela_web import TelaWeb

    ponte = Ponte()
    try:
        servidor = iniciar_servidor(ponte, args.porta)
    except OSError as exc:
        ui.aviso(f"Não consegui ligar a janela do Jarvis ({exc}). Usando o terminal.")
        return None
    janela = Janela()
    if not args.sem_janela:
        if not janela.abrir(servidor.endereco, PASTA_USUARIO / "janela", args.tela_cheia):
            servidor.desligar()
            ui.aviso("Não encontrei um navegador para abrir a janela. Usando o terminal.")
            return None
        ponte.janela_viva = janela.viva
    tela = TelaWeb(ponte)
    ui.usar_tela(tela)
    ui.console.print(f"[bold #00d7ff]🚀 J.A.R.V.I.S. Kids ligado na janela futurista.[/]\n"
                     f"   Se a janela não abrir, copie no navegador: [underline]{servidor.endereco}[/]\n"
                     "   Para desligar: feche a janela, diga \"tchau\" ou aperte Ctrl+C aqui.", soft_wrap=True)
    return Interface(servidor, janela, tela, ponte)


def conectar_interface(interface: Interface | None, io, prefs, plano) -> None:
    """Depois do boot: a janela fica sabendo se há microfone e passa a 'ver' a voz do Jarvis."""
    if interface is None:
        return
    from jarvis.agenda import CATEGORIAS, REPETICOES

    # Sem placa de vídeo dedicada, a IA usa a CPU: a janela economiza animações para não roubar desempenho.
    leve = prefs.animacoes == "leves" or (prefs.animacoes == "auto" and plano.nivel.startswith("Econômico"))
    interface.tela.configurar(io.escuta_ativa, VERSAO, CATEGORIAS, REPETICOES, economia=leve)
    interface.tela.conectar_alto_falante(io.voz.alto_falante)
    interface.ponte.ao_acao = lambda acao: io.voz.silenciar() if acao == "silenciar" else None


def ligar_agenda(ctx, interface: Interface | None) -> None:
    from jarvis.agenda import Agenda
    from jarvis.painel_agenda import atualizar_tela

    ctx.agenda = Agenda(PASTA_USUARIO / "agendas" / f"{ctx.perfil.arquivo.stem}.json", ctx.prefs.missa_horario,
                        ctx.prefs.missa_local)
    if interface is None:
        return

    def verificar_texto(texto: str) -> str | None:
        analise = ctx.guardiao.analisar_entrada(texto)
        if analise and analise.bloquear:
            if analise.alerta_pais and ctx.prefs.alertas_seguranca:
                ctx.perfil.registrar_alerta(analise.categoria, texto)
            return "Esse texto não pode ir para a agenda. Que tal escrever de outro jeito?"
        return None

    interface.ponte.agenda = ctx.agenda
    interface.ponte.verificar_texto = verificar_texto
    interface.ponte.ao_mudar_agenda = lambda: atualizar_tela(ctx)
    atualizar_tela(ctx)


# =============================================================================
#  Inicialização ("boot" com visual de nave)
# =============================================================================
def inicializar(args: argparse.Namespace):
    from jarvis import ui
    from jarvis.audio.efeitos import AltoFalante, Efeitos
    from jarvis.audio.voz import Voz
    from jarvis.cerebro import Cerebro, ErroCerebro
    from jarvis.fe.conhecimento import Biblioteca
    from jarvis.interacao import Interacao
    from jarvis.seguranca import Guardiao

    ui.limpar()
    ui.banner(VERSAO)
    prefs = Preferencias.carregar()
    if args.maos_livres:
        prefs.modo_escuta = "maos_livres"

    hw = detectar_hardware()
    plano = planejar(hw, prefs)
    if args.modelo:
        plano.modelo_llm = args.modelo
    ui.etapa("Escaneando hardware", True, f"{hw.descricao} → modo {plano.nivel}")

    # Depois do 1º download, os modelos de voz carregam sem tocar a internet.
    baixados = _modelos_baixados()
    if baixados["kokoro"] and plano.modelo_whisper in baixados["whisper"]:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

    # ---- Cérebro (Ollama)
    cerebro: Cerebro | None = Cerebro(plano, prefs.ollama_host, prefs.turnos_memoria)
    try:
        with ui.carregando("Conectando ao núcleo de IA (Ollama)…"):
            instalado = cerebro.modelo_instalado()
        if not instalado:
            _baixar_modelo(cerebro)
        with ui.carregando(f"Carregando o cérebro '{plano.modelo_llm}' na memória…"):
            cerebro.aquecer()
        ui.etapa("Núcleo de IA (Ollama)", True, plano.modelo_llm)
    except ErroCerebro as exc:
        ui.etapa("Núcleo de IA (Ollama)", False, "desligado")
        ui.fala(str(exc), "ATENÇÃO, FAMÍLIA", ui.CORES["alerta"])
        ui.info("Sem a IA, o Jarvis ainda faz quiz, orações, exame, histórias e mesada.")
        cerebro = None

    # ---- Boca e efeitos
    alto_falante = AltoFalante()
    efeitos = Efeitos(alto_falante, prefs.efeitos_sonoros and not args.sem_efeitos)
    efeitos.tocar("inicializar")
    ui.info("Ativando sintetizador de voz… (na 1ª vez baixa a voz neural, ~330 MB)")
    voz = Voz("mudo" if args.mudo else prefs.motor_voz, prefs.voz_kokoro, prefs.voz_edge,
              prefs.velocidade_voz, alto_falante)
    ok_voz = (True if not voz.avisos else None) if voz.ativa else (None if args.mudo else False)
    ui.etapa("Voz do Jarvis (TTS)", ok_voz, voz.descricao + (f" · {voz.avisos[0]}" if voz.avisos else ""))

    # ---- Ouvidos
    microfone = transcritor = None
    if not args.texto:
        try:
            from jarvis.audio.ouvido import Microfone, Transcritor
            from jarvis.audio.vad import SensorVoz

            with ui.carregando("Calibrando sensor de voz (VAD)…"):
                sensor = SensorVoz()
                microfone = Microfone(sensor)
            ui.etapa("Sensor de voz (VAD)", True if sensor.motor == "Silero VAD" else None,
                     f"{sensor.motor} · 🎙️ {microfone.nome[:40]}")
            ui.info(f"Carregando ouvidos (Whisper '{plano.modelo_whisper}')… na 1ª vez faz o download")
            transcritor = Transcritor(plano.modelo_whisper, plano.whisper_dispositivo, plano.whisper_precisao)
            ui.etapa("Ouvidos (Speech-to-Text)", True, transcritor.descricao)
            _marcar_modelos(plano.modelo_whisper, kokoro=voz.motor.nome.startswith("Kokoro"))
        except Exception as exc:
            microfone = transcritor = None
            ui.etapa("Microfone", None, f"modo teclado ({str(exc)[:70]})")
    elif voz.motor.nome.startswith("Kokoro"):
        _marcar_modelos(None, kokoro=True)

    # ---- Fé e segurança
    with ui.carregando("Carregando a Biblioteca da Fé…"):
        biblioteca = Biblioteca()
        guardiao = Guardiao()
    ui.etapa("Biblioteca da Fé (RAG local)", True, f"{len(biblioteca.trechos)} fontes verificadas")
    ui.etapa("Guardião de segurança", True, "travas doutrinárias e de proteção infantil ativas")

    io = Interacao(voz, efeitos, guardiao, microfone, transcritor, prefs.modo_escuta, prefs.silencio_fim_ms,
                   prefs.palavra_ativacao)
    return prefs, plano, cerebro, biblioteca, guardiao, io


def _baixar_modelo(cerebro) -> None:
    from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TransferSpeedColumn

    from jarvis import ui

    ui.info(f"Primeira vez! Baixando o cérebro '{cerebro.modelo}' (só acontece uma vez)…")
    if ui.web_ativa():
        def mostrar(status: str, feito: int, total: int) -> None:
            mb = f" · {feito / 1e6:,.0f} de {total / 1e6:,.0f} MB".replace(",", ".") if total else ""
            ui.progresso(f"🧠 Baixando o cérebro: {status}{mb}", feito, total)

        try:
            cerebro.baixar_modelo(mostrar)
        finally:
            ui.progresso("", 1, 1)
        return
    with Progress(TextColumn("  [#00d7ff]{task.description}"), BarColumn(), DownloadColumn(),
                  TransferSpeedColumn(), console=ui.console) as progresso:
        tarefa = progresso.add_task("baixando", total=None)

        def atualizar(status: str, feito: int, total: int) -> None:
            progresso.update(tarefa, description=status[:30], completed=feito, total=total or None)

        cerebro.baixar_modelo(atualizar)


# =============================================================================
#  Perfil da criança
# =============================================================================
def extrair_nome(texto: str) -> str:
    t = re.sub(r"^(meu nome (é|e)|eu sou (o|a)|eu sou|sou (o|a)|me chamo|pode me chamar de|é|e)\s+", "",
               texto.strip(), flags=re.IGNORECASE)
    t = re.sub(r"[^\wÀ-ÿ\s'-]", "", t).strip()
    return " ".join(t.split()[:3])[:30].title()


def escolher_perfil(io, prefs, args):
    from jarvis import ui
    from jarvis.area_pais import criar_pin_interativo
    from jarvis.armazenamento import criar_perfil, identificador, listar_perfis
    from jarvis.gamificacao import nivel_de

    perfis = listar_perfis()
    if args.perfil:
        alvo = identificador(args.perfil)
        for p in perfis:
            if identificador(p.nome) == alvo:
                return p
    if perfis:  # sempre pergunta: assim irmãos podem criar o próprio perfil
        opcoes = [f"{nivel_de(p.jogo['pontos'])[2]} {p.nome}  [grey50]{nivel_de(p.jogo['pontos'])[1]}[/]" for p in perfis]
        i = io.escolher("Identifique-se, agente! Quem está no comando hoje?", opcoes + ["➕ Novo agente"],
                        titulo="🛰️ IDENTIFICAÇÃO DO AGENTE")
        if i is not None and i < len(perfis):
            return perfis[i]
        if i is None:
            return perfis[0]

    io.dizer("Olá! Eu sou o Jarvis, seu assistente de missões, estudos e fé. "
             "Para começar, qual é o seu nome?")
    nome = ""
    while not nome:
        nome = extrair_nome(args.perfil or io.ouvir("Seu nome"))
        args.perfil = None
    idade = io.pedir_numero(f"Muito prazer, {nome}! Quantos anos você tem?") or 10
    perfil = criar_perfil(nome, max(5, min(idade, 17)))
    if not prefs.tem_pin:
        ui.fala("Pai, mãe ou responsável: vocês podem criar um PIN para a Área dos Pais. Com ele, as atividades "
                "da mesada só viram dinheiro depois da sua aprovação. (Se preferir, deixe para depois.)",
                "PARA OS PAIS", "#ff87d7")
        if io.confirmar("Criar o PIN dos pais agora?", falar=False):
            criar_pin_interativo(prefs)
    io.dizer(f"Perfil criado! Bem-vindo à tripulação, agente {perfil.nome}!")
    return perfil


# =============================================================================
#  Conversa e comandos
# =============================================================================
def conversar(ctx, texto: str, pontuar: bool = True, orientacao: str = "") -> None:
    from jarvis import ui
    from jarvis.cerebro import ErroCerebro

    if ctx.cerebro is None:
        ctx.io.dizer("Meu núcleo de IA está desligado agora, então não consigo conversar livremente. "
                     "Mas posso fazer quiz, orações, histórias da Bíblia, o exame de consciência e cuidar da sua mesada! "
                     "Peça para um adulto abrir o aplicativo Ollama.")
        return
    trechos = ctx.biblioteca.buscar(texto)
    de_fe = ctx.biblioteca.e_pergunta_de_fe(texto) or bool(trechos) or ctx.persona is not None
    fontes = montar_contexto_fontes(trechos, ctx.biblioteca.e_pergunta_de_fe(texto))
    if orientacao:  # assunto delicado: a IA recebe instrução extra de acolhimento
        fontes = f"{fontes}\n\n{orientacao}" if fontes else orientacao
    if trechos:
        ui.info("📚 Fontes: " + " · ".join(f"{t.titulo} ({', '.join(t.referencias[:2]) or t.fonte})" for t in trechos))
    if ctx.persona:
        titulo, cor = f"{ctx.persona['emoji']} {ctx.persona['nome']}", ui.CORES["santo"]
    else:
        titulo, cor = "J.A.R.V.I.S.", ui.CORES["jarvis"]
    try:
        resposta, bloqueado = ctx.io.responder_em_fluxo(
            ctx.cerebro.responder(texto, ctx.system_prompt(), fontes, TEMPERATURA_FE if de_fe else None),
            titulo, cor, ctx.voz_atual, autorizados=(fontes or "") + " " + citacoes_da_persona(ctx.persona))
    except ErroCerebro as exc:
        ctx.io.efeitos.tocar("erro")
        ctx.io.dizer("Ops! Meu núcleo de IA teve uma falha. Vamos tentar de novo daqui a pouco?")
        ui.erro(str(exc))
        return
    if bloqueado and ctx.io.ultimo_bloqueio == "doutrina" and ctx.prefs.alertas_seguranca:
        ctx.perfil.registrar_alerta("ia_bloqueada", texto)  # os pais podem revisar a pergunta depois
    if resposta and not bloqueado:
        ctx.cerebro.memorizar(texto, resposta)
    if pontuar:
        ctx.processar_eventos(ctx.jogo.pontuar_pergunta(texto))


def citacoes_da_persona(persona: dict | None) -> str:
    return " ".join(c["texto"] for c in persona.get("citacoes", [])) if persona else ""


def mostrar_conquistas(ctx) -> None:
    from jarvis import ui
    from jarvis.gamificacao import MEDALHAS

    linhas = [[m.emoji if m.id in ctx.jogo.jogo["medalhas"] else "🔒",
               f"[bold]{m.nome}[/]" if m.id in ctx.jogo.jogo["medalhas"] else f"[grey50]{m.nome}[/]",
               m.descricao] for m in MEDALHAS]
    ui.tabela("🏆 MEDALHAS", ["", "Medalha", "Como conquistar"], linhas, "#ffd700")
    missoes = ctx.jogo.missoes_de_hoje()
    ui.tabela("🎯 MISSÕES DE HOJE", ["", "Missão", "Progresso"],
              [["✅" if m["concluida"] else "◻️", m["descricao"],
                ui.barra(m["progresso"], m["meta"], 10)] for m in missoes], "#5fffaf")
    _i, nome, emoji, _min, proximo = ctx.jogo.nivel
    conquistadas = len(ctx.jogo.jogo["medalhas"])
    medalhas = f"{conquistadas} medalha{'s' if conquistadas != 1 else ''}"
    falta = f" Faltam {proximo - ctx.jogo.pontos} pontos para o próximo nível." if proximo else ""
    ctx.io.dizer(f"Você é {nome}, com {ctx.jogo.pontos} Pontos de Sabedoria e {medalhas}.{falta}")


def mostrar_ajuda(ctx) -> None:
    from jarvis import ui

    ui.fala(
        "Você pode me perguntar QUALQUER coisa: ciência, fé, Bíblia, santos, lição de casa (eu dou dicas!).\n\n"
        "Comandos rápidos (fale ou digite):\n"
        "  • \"quiz\"  •  \"vamos rezar\"  •  \"terço\"  •  \"exame de consciência\"  •  \"conta uma história\"\n"
        "  • \"calendário\" (tempo litúrgico, cor do dia e quanto falta para o Natal)  •  \"mudar a voz\"\n"
        "  • \"agenda\" (planner com o santo do dia e a Missa de domingo)\n"
        "  • \"marca prova de matemática na sexta às 8h\" (anota direto na agenda!)\n"
        "  • \"falar com Carlo Acutis\" (ou Dom Bosco, Santa Teresinha, São Francisco, São Tomás, Irmã Dulce)\n"
        "  • \"voltar ao normal\" (desliga o modo santo)\n"
        "  • \"mesada\"  •  \"quanto eu tenho?\"  •  \"eu arrumei a cama\" (registra a atividade!)\n"
        "  • \"conquistas\"  •  \"área dos pais\"  •  \"tchau\"",
        "AJUDA DO AGENTE")
    ctx.io.dizer("Esses são os meus comandos. Mas pode simplesmente conversar comigo!", mostrar=False)


def executar_comando(ctx, comando: str) -> None:
    from jarvis import area_pais, painel_agenda, painel_mesada, personalizar
    from jarvis.fe import calendario, inspectorum, oracoes, quiz, terco, vozes

    if comando == "quiz":
        quiz.executar(ctx)
    elif comando == "terco":
        terco.executar(ctx)
    elif comando == "calendario":
        calendario.executar(ctx)
    elif comando == "agenda":
        painel_agenda.executar(ctx)
    elif comando == "voz":
        personalizar.escolher_voz(ctx)
    elif comando == "oracao":
        oracoes.executar(ctx)
    elif comando == "exame":
        inspectorum.executar(ctx)
    elif comando == "vozes":
        reflexao = vozes.executar(ctx)
        if reflexao:
            responder_com_seguranca(ctx, reflexao, pontuar=False)
    elif comando == "mesada":
        painel_mesada.executar(ctx)
    elif comando == "saldo":
        painel_mesada.mostrar_cofrinhos(ctx)
        ctx.io.dizer(ctx.mesada.resumo_falado(), mostrar=False)
    elif comando == "conquistas":
        mostrar_conquistas(ctx)
    elif comando == "pais":
        area_pais.executar(ctx)
    elif comando == "normal":
        vozes.desativar_santo(ctx)
    elif comando == "ajuda":
        mostrar_ajuda(ctx)


def guardiao_respondeu(ctx, texto: str) -> tuple[bool, str]:
    """
    Passa o texto da criança pelo Guardião. Retorna (já_respondido, orientação_extra).
    Situações de risco e conteúdo impróprio recebem resposta fixa e segura (sem IA).
    """
    from jarvis import ui

    analise = ctx.guardiao.analisar_entrada(texto)
    if not analise:
        return False, ""
    if analise.alerta_pais and ctx.prefs.alertas_seguranca:
        ctx.perfil.registrar_alerta(analise.categoria, texto)
    if analise.bloquear:
        ctx.io.dizer(analise.resposta, cor=ui.CORES["alerta"] if analise.alerta_pais else ui.CORES["jarvis"])
        return True, ""
    return False, analise.orientacao  # assunto delicado: conversa com acolhimento extra


def responder_com_seguranca(ctx, texto: str, pontuar: bool = True) -> None:
    respondido, orientacao = guardiao_respondeu(ctx, texto)
    if not respondido:
        conversar(ctx, texto, pontuar=pontuar, orientacao=orientacao)


def processar(ctx, texto: str) -> bool:
    """Trata uma fala/digitação da criança. Retorna False para desligar."""
    from jarvis.comandos import detectar_atividade, identificar_comando, pede_santo
    from jarvis.fe import vozes
    from jarvis.painel_mesada import concluir_atividade

    # 1) Guardião primeiro, sempre
    respondido, orientacao = guardiao_respondeu(ctx, texto)
    if respondido:
        return True
    if orientacao:
        conversar(ctx, texto, orientacao=orientacao)
        return True

    # 2) Comandos
    comando = identificar_comando(texto)
    if comando == "sair":
        return False
    if comando:
        executar_comando(ctx, comando)
        return True

    # 3) "Quero falar com o Carlo Acutis"
    if pede_santo(texto):
        santo = vozes.encontrar_santo(texto)
        if santo:
            vozes.ativar_santo(ctx, santo)
            return True

    # 4) "Marca prova de matemática na sexta às 8h" -> agenda
    from jarvis.agenda import interpretar_compromisso
    from jarvis.painel_agenda import marcar_pelo_que_foi_dito

    compromisso = interpretar_compromisso(texto)
    if compromisso and ctx.agenda is not None:
        marcar_pelo_que_foi_dito(ctx, compromisso)
        return True

    # 5) "Eu arrumei a cama!" -> registrar atividade da mesada
    atividade = detectar_atividade(texto, ctx.mesada.atividades)
    if atividade and ctx.io.confirmar(f"Uau! Quer registrar a atividade '{atividade['nome']}' na sua mesada?"):
        concluir_atividade(ctx, atividade)
        return True

    # 6) Conversa livre com a IA (com RAG + travas)
    conversar(ctx, texto)
    return True


# =============================================================================
#  Loop principal
# =============================================================================
def saudacao(ctx) -> None:
    from jarvis.fe.liturgia import dia_liturgico, resumo_falado

    eventos = ctx.jogo.iniciar_dia()
    hora = datetime.now().hour
    periodo = "Bom dia" if 5 <= hora < 12 else "Boa tarde" if 12 <= hora < 18 else "Boa noite"
    partes = [f"{periodo}, agente {ctx.perfil.nome}! Todos os sistemas online.", resumo_falado(dia_liturgico())]
    rendeu = ctx.mesada.atualizar_rendimentos()
    if rendeu:
        from jarvis.texto import reais_por_extenso

        partes.append(f"Boa notícia: seu investimento rendeu {reais_por_extenso(rendeu)} desde a última visita!")
        eventos += ctx.jogo.registrar("rendimento_centavos", rendeu)
    desafio = ctx.perfil.jogo.get("desafio_virtude")
    if desafio and desafio.get("data") != datetime.now().date().isoformat():
        partes.append(f"Lembre do seu desafio de virtude, {desafio['virtude']}: {desafio['desafio']}")
    if ctx.agenda is not None:
        from jarvis.agenda import resumo_do_dia

        hoje = ctx.agenda.do_dia()
        if any(not i.automatico or i.categoria == "missa" for i in hoje):
            partes.append(resumo_do_dia(hoje))
    pendentes = len(ctx.mesada.pendentes)
    if pendentes:
        partes.append(f"Você tem {pendentes} atividade{'s' if pendentes > 1 else ''} esperando a aprovação dos pais.")
    partes.append("Qual é a missão de hoje?")
    mostrar_painel(ctx)
    ctx.processar_eventos(eventos)
    ctx.io.dizer(" ".join(partes))


def mostrar_painel(ctx) -> None:
    from jarvis import ui
    from jarvis.painel_agenda import atualizar_tela
    from jarvis.texto import formatar_reais

    ui.hud(ctx.perfil.nome, ctx.jogo.nivel, ctx.jogo.pontos, ctx.jogo.jogo["dias_seguidos"],
           formatar_reais(ctx.mesada.saldo_total()), ctx.jogo.missoes_de_hoje(),
           ctx.persona["nome"] if ctx.persona else None)
    ui.comandos_rapidos()
    atualizar_tela(ctx)


def registrar_uso(ctx, segundos: float) -> int:
    uso = ctx.perfil.dados["uso"]
    dia = datetime.now().date().isoformat()
    if uso.get("data") != dia:
        uso.update({"data": dia, "segundos": 0})
    uso["segundos"] += int(segundos)
    return uso["segundos"]


def tempo_esgotado(ctx, segundos_hoje: int) -> bool:
    limite = ctx.prefs.limite_minutos_diarios
    return bool(limite) and segundos_hoje >= limite * 60


def loop(ctx) -> None:
    from jarvis import ui

    ultimo = time.monotonic()
    rodadas = 0
    while True:
        agora = time.monotonic()
        if tempo_esgotado(ctx, registrar_uso(ctx, agora - ultimo)):
            ctx.io.dizer("Seu tempo com o Jarvis por hoje acabou! Hora de descansar os olhos, brincar e ficar com a "
                         "família. Até amanhã, agente!")
            return
        ultimo = agora
        texto = ctx.io.ouvir(tipo="principal")
        if not texto:
            continue
        if not processar(ctx, texto):
            return
        rodadas += 1
        ctx.perfil.salvar()
        if rodadas % 4 == 0 or ui.web_ativa():  # na janela, o painel do agente fica sempre atualizado
            mostrar_painel(ctx)
        else:
            ui.comandos_rapidos()


def despedir(ctx) -> None:
    ctx.io.efeitos.tocar("desligar")
    ctx.io.dizer(f"Desligando sistemas. Foi uma ótima missão, agente {ctx.perfil.nome}! "
                 "Que Deus te abençoe. Até a próxima!")


def diagnostico() -> None:
    from importlib import metadata

    from jarvis import ui

    ui.banner(VERSAO)
    prefs = Preferencias.carregar()
    hw = detectar_hardware()
    plano = planejar(hw, prefs)
    ui.tabela("🩺 DIAGNÓSTICO", ["Item", "Resultado"], [
        ["Sistema", f"{hw.sistema} {hw.arquitetura} · Python {sys.version.split()[0]}"],
        ["Hardware", hw.descricao],
        ["Perfil de desempenho", plano.nivel],
        ["Modelo de IA", plano.modelo_llm],
        ["Whisper", f"{plano.modelo_whisper} ({plano.whisper_dispositivo}, {plano.whisper_precisao})"],
        ["Opções do Ollama", str(plano.opcoes_ollama)],
        ["Pasta de dados", str(PASTA_USUARIO)],
    ])
    linhas = []
    for pacote in ("ollama", "rich", "numpy", "sounddevice", "soundfile", "faster-whisper", "torch",
                   "silero-vad", "kokoro", "pyttsx3", "edge-tts"):
        try:
            linhas.append([pacote, f"[green]{metadata.version(pacote)}[/]"])
        except metadata.PackageNotFoundError:
            linhas.append([pacote, "[yellow]não instalado[/]"])
    ui.tabela("📦 Componentes", ["Pacote", "Versão"], linhas)
    try:
        from jarvis.cerebro import Cerebro

        modelos = Cerebro(plano, prefs.ollama_host).modelos_instalados()
        ui.etapa("Ollama", True, ", ".join(modelos) or "nenhum modelo baixado ainda")
    except Exception as exc:
        ui.etapa("Ollama", False, str(exc)[:90])
    try:
        import sounddevice as sd

        ui.etapa("Microfone", True, sd.query_devices(kind="input")["name"])
        ui.etapa("Alto-falante", True, sd.query_devices(kind="output")["name"])
    except Exception as exc:
        ui.etapa("Áudio", False, str(exc)[:90])


def preparar() -> int:
    """Baixa tudo o que o Jarvis precisa, para o primeiro uso da criança já ser rápido."""
    from jarvis import ui
    from jarvis.cerebro import Cerebro, ErroCerebro

    ui.banner(VERSAO)
    prefs = Preferencias.carregar()
    hw = detectar_hardware()
    plano = planejar(hw, prefs)
    ui.etapa("Hardware", True, f"{hw.descricao} → {plano.nivel}")
    tudo_ok = True
    try:
        cerebro = Cerebro(plano, prefs.ollama_host)
        if cerebro.modelo_instalado():
            ui.etapa(f"Cérebro ({plano.modelo_llm})", True, "já estava baixado")
        else:
            _baixar_modelo(cerebro)
            ui.etapa(f"Cérebro ({plano.modelo_llm})", True, "baixado")
    except ErroCerebro as exc:
        ui.etapa("Cérebro (Ollama)", False, str(exc)[:90])
        tudo_ok = False
    whisper = None
    try:
        from jarvis.audio.ouvido import Transcritor

        ui.info(f"Baixando o ouvido (Whisper '{plano.modelo_whisper}')…")
        Transcritor(plano.modelo_whisper, plano.whisper_dispositivo, plano.whisper_precisao)
        whisper = plano.modelo_whisper
        ui.etapa("Ouvido (Whisper)", True, plano.modelo_whisper)
    except Exception as exc:
        ui.etapa("Ouvido (Whisper)", False, str(exc)[:90])
        tudo_ok = False
    kokoro = False
    try:
        from jarvis.audio.voz import VozKokoro

        ui.info("Baixando a voz neural (Kokoro-82M, ~330 MB)…")
        VozKokoro("pm_alex", 1.0)
        kokoro = True
        ui.etapa("Voz neural (Kokoro)", True, "3 vozes em português do Brasil")
    except Exception as exc:
        ui.etapa("Voz neural (Kokoro)", None, f"o Jarvis usará a voz do sistema ({str(exc)[:60]})")
    _marcar_modelos(whisper, kokoro)
    ui.info("Pronto! Agora o Jarvis funciona sem internet." if tudo_ok else
            "Algumas partes não foram baixadas; o Jarvis tenta de novo quando for ligado.")
    return 0 if tudo_ok else 1


def main() -> int:
    configurar_terminal()
    args = argumentos()
    if args.diagnostico:
        diagnostico()
        return 0
    if args.preparar:
        return preparar()
    if args.redefinir_pin:
        prefs = Preferencias.carregar()
        prefs.pin_pais_hash = prefs.pin_pais_sal = ""
        prefs.salvar()
        print("PIN dos pais apagado. Crie um novo na Área dos Pais.")
        return 0

    interface = iniciar_interface(args)
    try:
        return _executar(args, interface)
    finally:
        if interface:
            interface.encerrar()


def _executar(args: argparse.Namespace, interface: Interface | None) -> int:
    from jarvis import personalizar
    from jarvis.contexto import Contexto
    from jarvis.gamificacao import Gamificacao
    from jarvis.mesada import Mesada

    try:
        prefs, plano, cerebro, biblioteca, guardiao, io = inicializar(args)
        conectar_interface(interface, io, prefs, plano)
        perfil = escolher_perfil(io, prefs, args)
    except (KeyboardInterrupt, EOFError):
        print("\nAté logo!")
        return 0
    io.nome_crianca = perfil.nome
    ctx = Contexto(io=io, perfil=perfil, prefs=prefs, plano=plano, jogo=Gamificacao(perfil),
                   mesada=Mesada(perfil, prefs.rendimento_mensal_pct), biblioteca=biblioteca, guardiao=guardiao,
                   cerebro=cerebro)
    ligar_agenda(ctx, interface)
    personalizar.aplicar_voz(ctx)
    try:
        if tempo_esgotado(ctx, registrar_uso(ctx, 0)):
            io.dizer(f"Oi, {perfil.nome}! O tempo combinado com seus pais para hoje já acabou. Até amanhã!")
            return 0
        if cerebro is not None:  # processa as regras do Jarvis enquanto ele dá bom-dia
            threading.Thread(target=cerebro.aquecer, args=(ctx.system_prompt(),), daemon=True).start()
        if not perfil.dados.get("voz_escolhida") and io.voz.ativa:
            personalizar.escolher_voz(ctx)  # na primeira vez, a criança escolhe a voz do Jarvis
        saudacao(ctx)
        loop(ctx)
        despedir(ctx)
    except (KeyboardInterrupt, EOFError):
        io.voz.alto_falante.parar()
        print("\nSistemas desligados. Até logo!")
    finally:
        perfil.salvar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
