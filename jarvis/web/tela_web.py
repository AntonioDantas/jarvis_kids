"""
TelaWeb: implementa as mesmas funções de ``jarvis.ui`` transformando cada uma num evento
para a janela futurista. Os módulos (quiz, terço, mesada...) não mudam nada.
"""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from datetime import date, timedelta

import numpy as np

from jarvis.texto import data_por_extenso
from jarvis.ui import texto_simples
from jarvis.web.ponte import Ponte

QUADROS_POR_SEGUNDO_VOZ = 30


def _celula(valor) -> str | dict:
    """Células de tabela: barras de progresso do terminal ('███░░') viram barras de verdade na janela."""
    texto = texto_simples(valor)
    if texto and re.fullmatch(r"[█░]+", texto):
        return {"barra": round(texto.count("█") / len(texto), 3)}
    return texto


def envelope_da_voz(audio: np.ndarray, taxa: int, quadros_por_segundo: int = QUADROS_POR_SEGUNDO_VOZ) -> list[float]:
    """Volume da fala a cada quadro (0 a 1): a janela anima o núcleo do Jarvis no ritmo da voz."""
    if audio is None or taxa <= 0 or len(audio) == 0:
        return []
    passo = max(1, int(taxa / quadros_por_segundo))
    n = len(audio) // passo
    if n == 0:
        return [0.5]
    quadros = np.asarray(audio[: n * passo], dtype=np.float32).reshape(n, passo)
    rms = np.sqrt(np.mean(quadros**2, axis=1))
    pico = float(rms.max()) or 1.0
    return [round(float(v), 2) for v in np.clip(rms / pico, 0, 1)]


class FalaAoVivo:
    """Resposta da IA aparecendo frase a frase na janela."""

    def __init__(self, tela: TelaWeb, titulo: str, cor: str):
        tela._contador += 1
        self.tela, self.titulo, self.cor = tela, titulo, cor
        self.id, self.texto = f"fluxo-{tela._contador}", ""

    def _enviar(self, ativo: bool) -> None:
        self.tela.ponte.emitir("fala", texto=self.texto, titulo=self.titulo, cor=self.cor, ativo=ativo,
                               substitui=self.id)

    def __enter__(self) -> FalaAoVivo:
        self._enviar(True)
        return self

    def acrescentar(self, frase: str) -> None:
        self.texto = f"{self.texto} {frase}".strip()
        self._enviar(True)

    def __exit__(self, *exc) -> None:
        self._enviar(False)


class TelaWeb:
    def __init__(self, ponte: Ponte):
        self.ponte = ponte
        self.microfone = False
        self._menu: dict | None = None
        self._contador = 0
        self._ultimo_nivel = 0.0

    def _emitir(self, tipo: str, **dados) -> None:
        self.ponte.emitir(tipo, **dados)

    # ------------------------------------------------------------ configuração
    def configurar(self, microfone: bool, versao: str, categorias: dict, repeticoes: dict,
                   economia: bool = False) -> None:
        self.microfone = microfone
        self._emitir("config", microfone=microfone, versao=versao, economia=economia,
                     categorias={k: {"emoji": e, "nome": n} for k, (e, n) in categorias.items()},
                     repeticoes=repeticoes)

    def conectar_alto_falante(self, alto_falante) -> None:
        alto_falante.observador = self._ao_som

    def _ao_som(self, evento: str, audio=None, taxa: int = 0) -> None:
        if evento == "inicio":
            duracao = (len(audio) / taxa) if audio is not None and taxa else 0
            self._emitir("voz", fase="inicio", envelope=envelope_da_voz(audio, taxa), fps=QUADROS_POR_SEGUNDO_VOZ,
                         duracao=round(duracao, 2))
        else:
            self._emitir("voz", fase="fim")

    # ----------------------------------------------------------- abertura/boot
    def banner(self, versao: str) -> None:
        self._emitir("banner", versao=versao)

    def limpar(self) -> None:
        self._emitir("limpar")

    @contextmanager
    def carregando(self, texto: str):
        self._emitir("carregando", ativo=True, texto=texto_simples(texto))
        try:
            yield
        finally:
            self._emitir("carregando", ativo=False, texto="")

    def etapa(self, nome: str, ok: bool | None, detalhe: str = "") -> None:
        self._emitir("etapa", nome=nome, ok=ok, detalhe=texto_simples(detalhe))

    # ------------------------------------------------------------- painéis
    def hud(self, nome, nivel, pontos, dias, saldo, missoes, persona) -> None:
        indice, nome_nivel, emoji, minimo, proximo = nivel
        self._emitir("hud", nome=nome, nivel=nome_nivel, emoji=emoji, indice=indice, pontos=pontos, minimo=minimo,
                     proximo=proximo, dias=dias, saldo=saldo, persona=persona,
                     missoes=[{"descricao": m["descricao"], "progresso": m["progresso"], "meta": m["meta"],
                               "concluida": m["concluida"]} for m in missoes])

    def atualizar_lateral(self, dados: dict) -> None:
        self._emitir("lateral", **dados)

    def comandos_rapidos(self) -> None:
        pass  # na janela, os botões de comando estão sempre à vista

    # ------------------------------------------------------------- conversa
    def fala(self, texto: str, titulo: str, cor: str) -> None:
        self._emitir("fala", texto=texto, titulo=titulo, cor=cor, ativo=False)

    def painel_ao_vivo(self, titulo: str, cor: str) -> FalaAoVivo:
        return FalaAoVivo(self, titulo, cor)

    def crianca_disse(self, nome: str, texto: str) -> None:
        self._emitir("crianca", nome=nome, texto=texto)

    def evento(self, tipo: str, texto: str, detalhe: str = "") -> None:
        self._emitir("conquista", categoria=tipo, texto=texto, detalhe=detalhe)

    def menu(self, titulo: str, opcoes: list[str], cor: str, pergunta: str = "") -> None:
        self._menu = {"titulo": texto_simples(titulo), "opcoes": [texto_simples(o) for o in opcoes], "cor": cor,
                      "pergunta": texto_simples(pergunta)}

    def tabela(self, titulo: str, colunas: list[str], linhas: list[list], cor: str) -> None:
        self._emitir("tabela", titulo=texto_simples(titulo), colunas=[texto_simples(c) for c in colunas],
                     linhas=[[_celula(c) for c in linha] for linha in linhas], cor=cor)

    def painel(self, titulo: str, texto: str, cor: str, subtitulo: str = "", destaque: str = "") -> None:
        self._emitir("painel", titulo=texto_simples(titulo), texto=texto, cor=cor, subtitulo=texto_simples(subtitulo),
                     destaque=destaque)

    def _aviso(self, nivel: str, texto: str) -> None:
        self._emitir("aviso", nivel=nivel, texto=texto_simples(texto))

    def aviso(self, texto: str) -> None:
        self._aviso("aviso", texto)

    def erro(self, texto: str) -> None:
        self._aviso("erro", texto)

    def info(self, texto: str) -> None:
        self._aviso("info", texto)

    def sucesso(self, texto: str) -> None:
        self._aviso("sucesso", texto)

    # ------------------------------------------------------- fé, quiz, terço
    def linha_oracao(self, texto: str) -> None:
        self._emitir("oracao", texto=texto)

    def contas(self, atual: int, total: int) -> None:
        self._emitir("contas", atual=atual, total=total, substitui="contas")

    def pergunta_quiz(self, numero: int, total: int, pergunta: str, opcoes: list[str], rodape: str) -> None:
        self._emitir("quiz", numero=numero, total=total, pergunta=pergunta, opcoes=opcoes, rodape=texto_simples(rodape))

    def resultado(self, correto: bool, texto: str, detalhe: str = "") -> None:
        self._emitir("resultado", correto=correto, texto=texto_simples(texto), detalhe=texto_simples(detalhe))

    def agenda(self, itens: list, titulo: str) -> None:
        self._emitir("agenda", titulo=texto_simples(titulo), itens=[
            {"hora": i.hora, "titulo": i.titulo, "emoji": i.emoji, "data": i.data, "automatico": i.automatico}
            for i in itens])

    def abrir_planner(self) -> bool:
        self._emitir("abrir_planner")
        return True

    # ------------------------------------------------------------ animações
    def estado(self, nome: str) -> None:
        self._emitir("estado", nome=nome)

    def nivel_microfone(self, valor: float) -> None:
        agora = time.monotonic()
        if agora - self._ultimo_nivel >= 0.06:
            self._ultimo_nivel = agora
            self._emitir("nivel_mic", valor=round(float(valor), 2))

    def progresso(self, texto: str, feito: int, total: int) -> None:
        self._emitir("progresso", texto=texto_simples(texto), feito=feito, total=total)

    # ---------------------------------------------------------------- entrada
    def entrada(self, rotulo: str, tipo: str = "texto", opcoes: list[str] | None = None) -> str:
        pedido = {"controle": tipo, "rotulo": texto_simples(rotulo), "microfone": self.microfone,
                  "opcoes": [texto_simples(o) for o in opcoes] if opcoes else []}
        if tipo == "escolha":
            pedido["menu"] = self._menu or {"titulo": "Escolha", "opcoes": pedido["opcoes"], "cor": "#00d7ff",
                                            "pergunta": ""}
        self.estado("ocioso")  # esperando a criança: o núcleo volta a "ONLINE"
        return self.ponte.pedir(pedido)


# -----------------------------------------------------------------------------
#  Painel da direita: "Hoje na Igreja", agenda do dia e contagem regressiva
# -----------------------------------------------------------------------------
def dados_laterais(agenda=None, hoje: date | None = None) -> dict:
    from jarvis.fe.liturgia import dia_liturgico, proximas_grandes_festas

    hoje = hoje or date.today()
    info = dia_liturgico(hoje)

    def item(i) -> dict:
        return {"hora": i.hora, "titulo": i.titulo, "emoji": i.emoji, "categoria": i.categoria,
                "automatico": i.automatico, "data": i.data}

    proximos = []
    if agenda is not None:
        for n in range(1, 8):
            dia = hoje + timedelta(days=n)
            for i in agenda.do_dia(dia):
                if not i.automatico or i.categoria == "missa":
                    proximos.append({**item(i), "quando": "amanhã" if n == 1 else data_por_extenso(dia)})
    return {
        "data": data_por_extenso(hoje),
        "liturgia": {"tempo": info.tempo, "cor": info.cor, "significado": info.significado_cor,
                     "celebracao": info.celebracao, "ano": info.ano, "evangelista": info.evangelista},
        "hoje": [item(i) for i in agenda.do_dia(hoje)] if agenda is not None else [],
        "proximos": proximos[:6],
        "contagem": [{"nome": n, "dias": d} for n, d in proximas_grandes_festas(hoje)],
    }
