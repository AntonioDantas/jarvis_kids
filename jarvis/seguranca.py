"""
Guardião: camada de proteção que roda ANTES e DEPOIS da IA.

* Entrada: detecta situações de risco, conteúdo impróprio, apostas, desafios
  perigosos, tentativas de "hackear" as regras e dados pessoais. Nesses casos
  o Jarvis responde com uma mensagem FIXA (a IA nem é consultada).
* Saída: confere cada frase gerada pela IA antes de ela ser falada.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from config import PASTA_DADOS
from jarvis.texto import contem_frase, normalizar


@dataclass
class Analise:
    categoria: str
    resposta: str
    alerta_pais: bool


class Guardiao:
    def __init__(self, arquivo: Path = PASTA_DADOS / "seguranca.json"):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        self.categorias = dados["categorias"]
        for categoria in self.categorias:
            categoria["_padroes"] = [re.compile(p) for p in categoria.get("padroes", [])]
        self.proibidas_saida = [normalizar(p) for p in dados["proibidas_na_saida"]]
        self.resposta_saida_bloqueada = dados["resposta_saida_bloqueada"]

    def analisar_entrada(self, texto: str) -> Analise | None:
        t = normalizar(texto)
        for categoria in self.categorias:  # a ordem do JSON define a prioridade
            if any(contem_frase(t, frase) for frase in categoria["frases"]) or any(
                p.search(texto) for p in categoria["_padroes"]
            ):
                return Analise(categoria["id"], categoria["resposta"], categoria.get("alerta_pais", False))
        return None

    def saida_segura(self, frase: str) -> bool:
        t = normalizar(frase)
        return not any(contem_frase(t, p) for p in self.proibidas_saida)
