"""
Perfis das crianças (um arquivo JSON por criança em ``meus_dados/perfis``).

Tudo fica no computador da família. As gravações são atômicas e mantêm uma
cópia ``.bak`` para que pontos e cofrinhos nunca se percam se a luz cair.
"""

from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime
from pathlib import Path

from config import PASTA_USUARIO
from jarvis.texto import normalizar

VERSAO_ESQUEMA = 1
PASTA_PERFIS = PASTA_USUARIO / "perfis"


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hoje() -> str:
    return datetime.now().date().isoformat()


def perfil_padrao(nome: str, idade: int) -> dict:
    return {
        "versao": VERSAO_ESQUEMA,
        "nome": nome,
        "idade": idade,
        "criado_em": agora(),
        "jogo": {
            "pontos": 0,
            "dias_seguidos": 0,
            "ultimo_dia": "",
            "medalhas": [],
            "missoes": {"data": "", "lista": [], "bonus_pago": False},
            "perguntas_hoje": {"data": "", "pontos": 0, "vistas": []},
            "santos_visitados": [],
            "estatisticas": {},
        },
        "uso": {"data": "", "segundos": 0},
        "voz_jarvis": "robo_amigo",
        "voz_escolhida": False,
        "mesada": {
            "cofrinhos": [
                {"id": "dizimo", "nome": "Dízimo", "emoji": "🙏", "percentual": 10, "saldo": 0,
                 "meta": 0, "tipo": "dizimo", "fixo": True},
                {"id": "poupar", "nome": "Poupança dos Sonhos", "emoji": "🐷", "percentual": 20,
                 "saldo": 0, "meta": 0, "tipo": "poupanca", "fixo": True},
                {"id": "investir", "nome": "Investimento", "emoji": "📈", "percentual": 20, "saldo": 0,
                 "meta": 0, "tipo": "investimento", "fixo": True, "aportado": 0, "rendimento_total": 0,
                 "rendimento_fracao": 0.0, "ultimo_rendimento": ""},
                {"id": "gastar", "nome": "Gastar com Sabedoria", "emoji": "🛒", "percentual": 40,
                 "saldo": 0, "meta": 0, "tipo": "gasto", "fixo": True},
                {"id": "doar", "nome": "Ajudar o Próximo", "emoji": "❤️", "percentual": 10,
                 "saldo": 0, "meta": 0, "tipo": "doacao", "fixo": True},
            ],
            "atividades": [],
            "pendentes": [],
            "extrato": [],
        },
        "alertas": [],
    }


def _completar(dados: dict, padrao: dict) -> dict:
    """Acrescenta chaves novas (de versões futuras) sem apagar o que já existe."""
    for chave, valor in padrao.items():
        if chave not in dados:
            dados[chave] = copy.deepcopy(valor)
        elif isinstance(valor, dict) and isinstance(dados[chave], dict):
            _completar(dados[chave], valor)
    return dados


def identificador(nome: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalizar(nome)).strip("_") or "crianca"


class Perfil:
    """Envelope fino sobre o dicionário do perfil, com gravação segura."""

    def __init__(self, dados: dict, arquivo: Path):
        self.dados = dados
        self.arquivo = arquivo

    @property
    def nome(self) -> str:
        return self.dados["nome"]

    @property
    def idade(self) -> int:
        return int(self.dados.get("idade", 10))

    @property
    def jogo(self) -> dict:
        return self.dados["jogo"]

    @property
    def mesada(self) -> dict:
        return self.dados["mesada"]

    def salvar(self) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        if self.arquivo.exists():
            backup = self.arquivo.with_suffix(".bak")
            try:
                backup.write_bytes(self.arquivo.read_bytes())
            except OSError:
                pass
        temporario = self.arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps(self.dados, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporario, self.arquivo)

    def registrar_alerta(self, categoria: str, texto: str) -> None:
        self.dados["alertas"].append(
            {"data": agora(), "categoria": categoria, "texto": texto[:300], "lido": False}
        )
        self.salvar()


def listar_perfis(pasta: Path = PASTA_PERFIS) -> list[Perfil]:
    perfis = []
    for arquivo in sorted(pasta.glob("*.json")):
        perfil = carregar(arquivo)
        if perfil:
            perfis.append(perfil)
    return perfis


def carregar(arquivo: Path) -> Perfil | None:
    for candidato in (arquivo, arquivo.with_suffix(".bak")):
        try:
            dados = json.loads(candidato.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        padrao = perfil_padrao(dados.get("nome", "Agente"), int(dados.get("idade", 10)))
        return Perfil(_completar(dados, padrao), arquivo)
    return None


def criar_perfil(nome: str, idade: int, pasta: Path = PASTA_PERFIS) -> Perfil:
    base = identificador(nome)
    arquivo = pasta / f"{base}.json"
    n = 2
    while arquivo.exists():
        arquivo = pasta / f"{base}_{n}.json"
        n += 1
    perfil = Perfil(perfil_padrao(nome.strip().title(), idade), arquivo)
    perfil.salvar()
    return perfil
