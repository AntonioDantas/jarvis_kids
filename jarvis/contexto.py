"""Contexto compartilhado entre o loop principal e os módulos (quiz, oração, mesada...)."""

from __future__ import annotations

from dataclasses import dataclass

from config import PlanoIA, Preferencias, montar_system_prompt
from jarvis.agenda import Agenda
from jarvis.armazenamento import Perfil
from jarvis.cerebro import Cerebro
from jarvis.dados import carregar_dados  # noqa: F401  (reexportado para os módulos)
from jarvis.fe.conhecimento import Biblioteca
from jarvis.gamificacao import Evento, Gamificacao
from jarvis.interacao import Interacao
from jarvis.mesada import Mesada
from jarvis.seguranca import Guardiao
from jarvis.texto import reais_por_extenso


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
    agenda: Agenda | None = None

    @property
    def voz_atual(self) -> dict | None:
        return self.persona["voz"] if self.persona else None

    def system_prompt(self) -> str:
        from jarvis.fe.liturgia import dia_liturgico

        hoje = dia_liturgico()
        resumo = f"{hoje.data.strftime('%d/%m/%Y')}, {hoje.tempo}, cor {hoje.cor}, ano {hoje.ano}"
        if hoje.celebracao:
            resumo += f"; celebração: {hoje.celebracao}"
        return montar_system_prompt(self.perfil.nome, self.perfil.idade, self.jogo.nome_nivel, self.persona, resumo)

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
