"""Leitura (com cache) dos arquivos de conteúdo em ``dados/``."""

from __future__ import annotations

import json
from functools import cache

from config import PASTA_DADOS


@cache
def carregar_dados(nome: str) -> dict:
    return json.loads((PASTA_DADOS / nome).read_text(encoding="utf-8"))
