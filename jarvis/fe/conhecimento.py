"""
Biblioteca da Fé — RAG (Retrieval-Augmented Generation) 100% local.

Arquitetura no estilo "ccc-ai": antes de cada resposta, o Jarvis procura na
biblioteca local os trechos mais relevantes (resumos infantis do Catecismo,
da Bíblia, da Suma Teológica e da vida dos santos, sempre com referência) e
os entrega à IA como FONTES VERIFICADAS. Assim a IA responde apoiada em
fontes, em vez de "inventar".

Fontes plugáveis:
  * ``dados/conhecimento/*.json``        — biblioteca oficial do projeto
  * ``dados/conhecimento/extra/*.json``  — mesma estrutura, material da família/paróquia
  * ``dados/conhecimento/extra/*.md|txt`` — textos livres (um trecho por parágrafo)

A busca usa BM25 com radicais em português: rápida, sem GPU e sem baixar nada.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from config import PASTA_DADOS
from jarvis.texto import radicais as _radicais
from jarvis.texto import radical

PASTA_CONHECIMENTO = PASTA_DADOS / "conhecimento"

# Palavras que indicam que a pergunta é sobre fé (para ativar a "trava" sem fonte)
_TEMAS_DE_FE = {radical(p) for p in (
    "deus jesus cristo espirito trindade maria senhora santo santa santos anjo anjos igreja papa "
    "padre biblia evangelho rezar reza oracao missa pecado pecados confissao confessar eucaristia "
    "comunhao batismo batizado crisma inferno purgatorio alma fe mandamento mandamentos "
    "sacramento religiao catecismo catolico milagre demonio diabo apostolo profeta vocacao dizimo "
    "quaresma pascoa natal advento terco rosario cruz salvacao salvador virgem ressurreicao "
    "paraiso paroquia freira frei bispo cardeal santissima"
).split()}


def radicais(texto: str) -> list[str]:
    """Radicais para busca; números pequenos ("7", "10") são ignorados por serem ambíguos."""
    return [r for r in _radicais(texto) if not (r.isdigit() and len(r) < 3)]


@dataclass
class Trecho:
    id: str
    titulo: str
    texto: str
    referencias: list[str] = field(default_factory=list)
    palavras_chave: list[str] = field(default_factory=list)
    fonte: str = "Biblioteca do J.A.R.V.I.S. Kids"


class Biblioteca:
    def __init__(self, pasta: Path = PASTA_CONHECIMENTO, k1: float = 1.4, b: float = 0.7):
        self.k1, self.b = k1, b
        self.trechos: list[Trecho] = []
        self._carregar(pasta)
        self._indexar()

    # ------------------------------------------------------------ carregamento
    def _carregar(self, pasta: Path) -> None:
        for arquivo in sorted(pasta.glob("*.json")) + sorted((pasta / "extra").glob("*.json")):
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            itens = dados["trechos"] if isinstance(dados, dict) else dados
            fonte_padrao = dados.get("fonte", arquivo.stem) if isinstance(dados, dict) else arquivo.stem
            for item in itens:
                self.trechos.append(Trecho(
                    id=item["id"], titulo=item["titulo"], texto=item["texto"],
                    referencias=item.get("referencias", []), palavras_chave=item.get("palavras_chave", []),
                    fonte=item.get("fonte", fonte_padrao),
                ))
        self._carregar_santos_e_historias(pasta.parent)
        for arquivo in sorted((pasta / "extra").glob("*.md")) + sorted((pasta / "extra").glob("*.txt")):
            if arquivo.name.upper().startswith("LEIA"):
                continue
            paragrafos = [p.strip() for p in arquivo.read_text(encoding="utf-8").split("\n\n") if len(p.strip()) > 40]
            for i, paragrafo in enumerate(paragrafos):
                self.trechos.append(Trecho(f"{arquivo.stem}-{i}", arquivo.stem.replace("_", " ").title(),
                                           paragrafo, fonte=f"Material da família: {arquivo.name}"))

    def _carregar_santos_e_historias(self, pasta_dados: Path) -> None:
        """A vida dos santos e as histórias bíblicas também viram fontes verificadas."""
        santos = pasta_dados / "santos.json"
        if santos.exists():
            for s in json.loads(santos.read_text(encoding="utf-8"))["santos"]:
                self.trechos.append(Trecho(
                    f"santo-{s['id']}", f"{s['nome']} ({s['anos']})", " ".join(s["fatos"]),
                    [f"Festa: {s['festa']}"], s.get("palavras_chave", []) + [s["apelido"]],
                    "Vidas dos santos — J.A.R.V.I.S. Kids",
                ))
        historias = pasta_dados / "historias_biblicas.json"
        if historias.exists():
            for h in json.loads(historias.read_text(encoding="utf-8"))["historias"]:
                self.trechos.append(Trecho(
                    f"historia-{h['id']}", h["titulo"], h["texto"], [h["referencia"]],
                    h.get("palavras_chave", []), "Histórias da Bíblia recontadas",
                ))

    def _indexar(self) -> None:
        self._docs: list[Counter] = []
        for t in self.trechos:
            # título e palavras-chave pesam mais que o corpo do texto
            termos = radicais(t.titulo) * 3 + radicais(" ".join(t.palavras_chave)) * 3 + radicais(t.texto)
            self._docs.append(Counter(termos))
        self._tamanho_medio = sum(sum(d.values()) for d in self._docs) / max(1, len(self._docs))
        frequencia: Counter = Counter()
        for doc in self._docs:
            frequencia.update(doc.keys())
        n = len(self._docs)
        self._idf = {termo: math.log(1 + (n - f + 0.5) / (f + 0.5)) for termo, f in frequencia.items()}

    # ------------------------------------------------------------------ busca
    def pontuar(self, pergunta: str) -> list[tuple[float, Trecho]]:
        termos = set(radicais(pergunta))
        resultados = []
        for doc, trecho in zip(self._docs, self.trechos, strict=False):
            tamanho = sum(doc.values())
            nota = 0.0
            for termo in termos:
                tf = doc.get(termo, 0)
                if tf:
                    nota += self._idf.get(termo, 0) * tf * (self.k1 + 1) / (
                        tf + self.k1 * (1 - self.b + self.b * tamanho / self._tamanho_medio))
            if nota > 0:
                resultados.append((nota, trecho))
        return sorted(resultados, key=lambda r: r[0], reverse=True)

    def buscar(self, pergunta: str, limite: int = 2, nota_minima: float = 5.0) -> list[Trecho]:
        resultados = self.pontuar(pergunta)
        if not resultados or resultados[0][0] < nota_minima:
            return []
        melhor = resultados[0][0]
        # só traz trechos razoavelmente próximos do melhor (evita contexto confuso)
        return [t for nota, t in resultados[:limite] if nota >= max(nota_minima, melhor * 0.6)]

    @staticmethod
    def e_pergunta_de_fe(pergunta: str) -> bool:
        return any(r in _TEMAS_DE_FE for r in radicais(pergunta))
