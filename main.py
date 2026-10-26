#!/usr/bin/env python3
"""
J.A.R.V.I.S. Kids — loop principal.

    Voz da criança ─► Silero VAD ─► faster-whisper ─► Guardião (entrada)
          ─► comandos (quiz, oração, exame, mesada...) ou
          ─► Biblioteca da Fé (RAG) ─► Ollama (streaming) ─► Guardião (saída)
          ─► Kokoro TTS (fala frase a frase) + Gamificação

Uso:
    python main.py                 # experiência completa com voz
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
import time
from datetime import datetime

# Privacidade: nada de telemetria das bibliotecas de IA.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from config import PASTA_USUARIO, VERSAO, Preferencias, detectar_hardware, montar_contexto_fontes, planejar  # noqa: E402

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
    p.add_argument("--redefinir-pin", action="store_true", help="apaga o PIN dos pais (esqueceu o PIN?)")
    return p.parse_args()


def configurar_terminal() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


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
def conversar(ctx, texto: str, pontuar: bool = True) -> None:
    from jarvis import ui
    from jarvis.cerebro import ErroCerebro

    if ctx.cerebro is None:
        ctx.io.dizer("Meu núcleo de IA está desligado agora, então não consigo conversar livremente. "
                     "Mas posso fazer quiz, orações, histórias da Bíblia, o exame de consciência e cuidar da sua mesada! "
                     "Peça para um adulto abrir o aplicativo Ollama.")
        return
    trechos = ctx.biblioteca.buscar(texto)
    fontes = montar_contexto_fontes(trechos, ctx.biblioteca.e_pergunta_de_fe(texto))
    if trechos:
        ui.info("📚 Fontes: " + " · ".join(f"{t.titulo} ({', '.join(t.referencias[:2]) or t.fonte})" for t in trechos))
    if ctx.persona:
        titulo, cor = f"{ctx.persona['emoji']} {ctx.persona['nome']}", ui.CORES["santo"]
    else:
        titulo, cor = "J.A.R.V.I.S.", ui.CORES["jarvis"]
    try:
        resposta, bloqueado = ctx.io.responder_em_fluxo(
            ctx.cerebro.responder(texto, ctx.system_prompt(), fontes), titulo, cor, ctx.voz_atual)
    except ErroCerebro as exc:
        ctx.io.efeitos.tocar("erro")
        ctx.io.dizer("Ops! Meu núcleo de IA teve uma falha. Vamos tentar de novo daqui a pouco?")
        ui.erro(str(exc))
        return
    if resposta and not bloqueado:
        ctx.cerebro.memorizar(texto, resposta)
    if pontuar:
        ctx.processar_eventos(ctx.jogo.pontuar_pergunta(texto))


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
        "  • \"quiz\"  •  \"vamos rezar\"  •  \"exame de consciência\"  •  \"conta uma história\"\n"
        "  • \"falar com Carlo Acutis\" (ou Dom Bosco, Santa Teresinha, São Francisco, São Tomás, Irmã Dulce)\n"
        "  • \"voltar ao normal\" (desliga o modo santo)\n"
        "  • \"mesada\"  •  \"quanto eu tenho?\"  •  \"eu arrumei a cama\" (registra a atividade!)\n"
        "  • \"conquistas\"  •  \"área dos pais\"  •  \"tchau\"",
        "AJUDA DO AGENTE")
    ctx.io.dizer("Esses são os meus comandos. Mas pode simplesmente conversar comigo!", mostrar=False)


def executar_comando(ctx, comando: str) -> None:
    from jarvis import area_pais, painel_mesada
    from jarvis.fe import inspectorum, oracoes, quiz, vozes

    if comando == "quiz":
        quiz.executar(ctx)
    elif comando == "oracao":
        oracoes.executar(ctx)
    elif comando == "exame":
        inspectorum.executar(ctx)
    elif comando == "vozes":
        reflexao = vozes.executar(ctx)
        if reflexao:
            conversar(ctx, reflexao, pontuar=False)
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


def processar(ctx, texto: str) -> bool:
    """Trata uma fala/digitação da criança. Retorna False para desligar."""
    from jarvis import ui
    from jarvis.comandos import detectar_atividade, identificar_comando, pede_santo
    from jarvis.fe import vozes
    from jarvis.painel_mesada import concluir_atividade

    # 1) Guardião: situações de risco e conteúdo impróprio têm resposta fixa e segura
    analise = ctx.guardiao.analisar_entrada(texto)
    if analise:
        cor = ui.CORES["alerta"] if analise.alerta_pais else ui.CORES["jarvis"]
        ctx.io.dizer(analise.resposta, cor=cor)
        if analise.alerta_pais and ctx.prefs.alertas_seguranca:
            ctx.perfil.registrar_alerta(analise.categoria, texto)
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

    # 4) "Eu arrumei a cama!" -> registrar atividade da mesada
    atividade = detectar_atividade(texto, ctx.mesada.atividades)
    if atividade and ctx.io.confirmar(f"Uau! Quer registrar a atividade '{atividade['nome']}' na sua mesada?"):
        concluir_atividade(ctx, atividade)
        return True

    # 5) Conversa livre com a IA (com RAG + travas)
    conversar(ctx, texto)
    return True


# =============================================================================
#  Loop principal
# =============================================================================
def saudacao(ctx) -> None:
    from jarvis.fe import vozes

    eventos = ctx.jogo.iniciar_dia()
    hora = datetime.now().hour
    periodo = "Bom dia" if 5 <= hora < 12 else "Boa tarde" if 12 <= hora < 18 else "Boa noite"
    partes = [f"{periodo}, agente {ctx.perfil.nome}! Todos os sistemas online."]
    santo = vozes.santo_do_dia()
    if santo:
        partes.append(f"Hoje a Igreja celebra: {santo}.")
    desafio = ctx.perfil.jogo.get("desafio_virtude")
    if desafio and desafio.get("data") != datetime.now().date().isoformat():
        partes.append(f"Lembre do seu desafio de virtude, {desafio['virtude']}: {desafio['desafio']}")
    pendentes = len(ctx.mesada.pendentes)
    if pendentes:
        partes.append(f"Você tem {pendentes} atividade{'s' if pendentes > 1 else ''} esperando a aprovação dos pais.")
    partes.append("Qual é a missão de hoje?")
    mostrar_painel(ctx)
    ctx.processar_eventos(eventos)
    ctx.io.dizer(" ".join(partes))


def mostrar_painel(ctx) -> None:
    from jarvis import ui
    from jarvis.texto import formatar_reais

    ui.hud(ctx.perfil.nome, ctx.jogo.nivel, ctx.jogo.pontos, ctx.jogo.jogo["dias_seguidos"],
           formatar_reais(ctx.mesada.saldo_total()), ctx.jogo.missoes_de_hoje(),
           ctx.persona["nome"] if ctx.persona else None)
    ui.comandos_rapidos()


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
        texto = ctx.io.ouvir()
        if not texto:
            continue
        if not processar(ctx, texto):
            return
        rodadas += 1
        ctx.perfil.salvar()
        if rodadas % 4 == 0:
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


def main() -> int:
    configurar_terminal()
    args = argumentos()
    if args.diagnostico:
        diagnostico()
        return 0
    if args.redefinir_pin:
        prefs = Preferencias.carregar()
        prefs.pin_pais_hash = prefs.pin_pais_sal = ""
        prefs.salvar()
        print("PIN dos pais apagado. Crie um novo na Área dos Pais.")
        return 0

    from jarvis.contexto import Contexto
    from jarvis.gamificacao import Gamificacao
    from jarvis.mesada import Mesada

    try:
        prefs, plano, cerebro, biblioteca, guardiao, io = inicializar(args)
        perfil = escolher_perfil(io, prefs, args)
    except (KeyboardInterrupt, EOFError):
        print("\nAté logo!")
        return 0
    io.nome_crianca = perfil.nome
    ctx = Contexto(io=io, perfil=perfil, prefs=prefs, plano=plano, jogo=Gamificacao(perfil),
                   mesada=Mesada(perfil), biblioteca=biblioteca, guardiao=guardiao, cerebro=cerebro)
    try:
        if tempo_esgotado(ctx, registrar_uso(ctx, 0)):
            io.dizer(f"Oi, {perfil.nome}! O tempo combinado com seus pais para hoje já acabou. Até amanhã!")
            return 0
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
