"""Contexto compartilhado entre o loop principal e os módulos (quiz, oração, mesada...)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache

from config import PASTA_DADOS, PlanoIA, Preferencias, montar_system_prompt
from jarvis.armazenamento import Perfil
from jarvis.cerebro import Cerebro
from jarvis.fe.conhecimento import Biblioteca
from jarvis.gamificacao import Evento, Gamificacao
from jarvis.interacao import Interacao
from jarvis.mesada import Mesada
from jarvis.seguranca import Guardiao
from jarvis.texto import reais_por_extenso


@cache
def carregar_dados(nome: str) -> dict:
    return json.loads((PASTA_DADOS / nome).read_text(encoding="utf-8"))


@dataclass
class Contexto:
    io: Interacao
    perfil: Perfil
    prefs: Preferencias
    plano: PlanoIA
    jogo: Gamificacao
    mesada: Mesada
    biblioteca: Biblioteca
    guardiao: Guardiao
    cerebro: Cerebro | None
    persona: dict | None = None

    @property
    def voz_atual(self) -> dict | None:
        return self.persona["voz"] if self.persona else None

    def system_prompt(self) -> str:
        return montar_system_prompt(self.perfil.nome, self.perfil.idade, self.jogo.nome_nivel, self.persona)

    def premiar(self, pontos: int, motivo: str, estatistica: str | None = None, quantidade: int = 1) -> None:
        eventos = self.jogo.ganhar(pontos, motivo)
        if estatistica:
            eventos += self.jogo.registrar(estatistica, quantidade)
        self.processar_eventos(eventos)

    def processar_eventos(self, eventos: list[Evento]) -> None:
        bonus = self.prefs.bonus_nivel_centavos
        for e in list(eventos):
            if e.tipo == "nivel" and bonus > 0:
                self.mesada.depositar(bonus, f"Bônus de nível: {e.dados['nome']}")
                eventos.append(Evento("pontos", f"Bônus de mesada por subir de nível: {reais_por_extenso(bonus)}!",
                                      som="moeda"))
        self.perfil.salvar()
        if eventos:
            self.io.celebrar(eventos)
