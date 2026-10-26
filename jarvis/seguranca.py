"""
Guardião: camada de proteção que roda ANTES e DEPOIS da IA.

* Entrada: detecta situações de risco (inclusive aliciamento online),
  conteúdo impróprio, apostas, desafios perigosos, tentativas de "hackear"
  as regras, dados pessoais e palavrões (mesmo disfarçados, como "m3rd4").
  Nesses casos o Jarvis responde com uma mensagem FIXA: a IA nem é consultada.
  Assuntos delicados (luto, medo, tristeza) NÃO são bloqueados: a IA recebe
  uma orientação extra para acolher com cuidado.
* Saída: cada frase gerada pela IA é limpa (sem links) e conferida contra
  palavras proibidas e afirmações contrárias à fé católica ANTES de ser
  mostrada ou falada.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from config import PASTA_DADOS
from jarvis.texto import contem_frase, normalizar, palavras

_ASPAS = re.compile(r"[“\"«]([^”\"»]{12,})[”\"»]")
_NEGACAO = re.compile(r"\b(nao|nunca|jamais|nem|ninguem)\b")

# "(CIC 1037)", "(Catecismo, n. 1849)", "(CIC 456-469)"
_REFERENCIA_CIC = re.compile(
    r"\s*\((?:CIC|Catecismo(?: da Igreja Cat[óo]lica)?)\s*[,:]?\s*(?:n\.?|n[ºo°]|§)?\s*\d{1,4}"
    r"(?:\s*(?:[-–,]|e)\s*\d{1,4})*\s*\)", re.IGNORECASE)

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_CATEGORIAS_DESOFUSCADAS = {"risco", "palavrao", "improprio"}


@dataclass
class Analise:
    categoria: str
    resposta: str            # resposta fixa ('' quando a categoria não bloqueia)
    alerta_pais: bool
    bloquear: bool = True
    orientacao: str = ""     # instrução extra para a IA (categorias que não bloqueiam)


def desofuscar(texto: str) -> str:
    """'M3RD4', 'm.e.r.d.a' e 'merdaaaa' viram 'merda' (só para a checagem de palavrões)."""
    t = normalizar(texto).translate(_LEET)
    t = re.sub(r"\b(?:[a-z][\s.\-_*]){2,}[a-z]\b", lambda m: re.sub(r"[\s.\-_*]", "", m.group(0)), t)
    return re.sub(r"([a-z])\1{2,}", r"\1", t)


class Guardiao:
    def __init__(self, arquivo: Path = PASTA_DADOS / "seguranca.json"):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        self.categorias = dados["categorias"]
        for categoria in self.categorias:
            categoria["_padroes"] = [re.compile(p) for p in categoria.get("padroes", [])]
        self._inofensivas = [re.compile(p) for p in dados.get("expressoes_inofensivas", [])]
        self.proibidas_saida = [normalizar(p) for p in dados["proibidas_na_saida"]]
        self.resposta_saida_bloqueada = dados["resposta_saida_bloqueada"]
        self._doutrina = [(re.compile(r["padrao"]), [normalizar(x) for x in r.get("ressalvas", [])],
                           [normalizar(x) for x in r.get("contexto", [])]) for r in dados.get("saida_doutrina", [])]
        self._ressalvas = [normalizar(x) for x in dados.get("saida_ressalvas", [])]
        self._remover = [re.compile(p) for p in dados.get("saida_remover", [])]
        self.resposta_citacao = dados.get("resposta_citacao", self.resposta_saida_bloqueada)
        self._atribuicao = [normalizar(x) for x in dados.get("citacao_atribuicao", [])]
        self._textos_autenticos = _so_palavras(" ".join(_textos_autenticos()))

    # ----------------------------------------------------------------- entrada
    def analisar_entrada(self, texto: str) -> Analise | None:
        t = normalizar(texto)
        for padrao in self._inofensivas:  # "morri de rir" não é pedido de ajuda
            t = padrao.sub(" ", t)
        t_desofuscado = desofuscar(texto)
        for padrao in self._inofensivas:  # "m0rr1 de rir" também
            t_desofuscado = padrao.sub(" ", t_desofuscado)
        for categoria in self.categorias:  # a ordem do JSON define a prioridade
            textos = [t, t_desofuscado] if categoria["id"] in _CATEGORIAS_DESOFUSCADAS else [t]
            achou = any(contem_frase(x, frase) for x in textos for frase in categoria["frases"])
            achou = achou or any(p.search(x) for x in (*textos, texto) for p in categoria["_padroes"])
            if achou:
                return Analise(categoria["id"], categoria.get("resposta", ""), categoria.get("alerta_pais", False),
                               categoria.get("bloquear", True), categoria.get("orientacao", ""))
        return None

    # ------------------------------------------------------------------- saída
    def limpar_saida(self, frase: str, autorizados: str = "") -> str:
        """
        Remove links e e-mails (a criança não deve ser levada a sites desconhecidos) e números do
        Catecismo que não estão nas fontes verificadas: modelos pequenos costumam inventar "(CIC 2559)".
        """
        for padrao in self._remover:
            frase = padrao.sub("", frase)

        def conferir(m: re.Match) -> str:
            numeros = re.findall(r"\d{2,4}", m.group(0))
            return m.group(0) if all(re.search(rf"(?<!\d){n}(?!\d)", autorizados) for n in numeros) else ""

        frase = _REFERENCIA_CIC.sub(conferir, frase)
        frase = re.sub(r"\s+([.,;:!?])", r"\1", frase)
        return re.sub(r"\s{2,}", " ", frase).strip()

    def revisar_frase(self, frase: str, autorizados: str = "") -> tuple[str, str | None]:
        """
        Limpa e confere uma frase da IA. Retorna (frase_limpa, motivo). Com motivo 'citacao' só essa
        frase é descartada; com 'linguagem' ou 'doutrina' a resposta inteira é interrompida.
        """
        frase = self.limpar_saida(frase, autorizados)
        return (frase, self.verificar_saida(frase, autorizados)) if frase else ("", None)

    def verificar_saida(self, frase: str, autorizados: str = "") -> str | None:
        """
        Retorna o motivo do bloqueio ou None se a frase é segura:
        'linguagem' (palavra imprópria), 'doutrina' (erro de fé) ou 'citacao' (frase entre aspas atribuída a
        santo, papa, Catecismo... que não aparece em nenhuma fonte verificada — ou seja, inventada).
        """
        t = normalizar(frase)
        if any(contem_frase(t, p) for p in self.proibidas_saida):
            return "linguagem"
        for padrao, ressalvas, contexto in self._doutrina:
            if contexto and not any(c in t for c in contexto):
                continue
            m = padrao.search(t)
            if not m or any(r in t for r in self._ressalvas + ressalvas):
                continue
            # "não é correto dizer que Maria é uma deusa": negação na mesma oração, antes do trecho
            oracao = re.split(r"[,:;.!?]", t[max(0, m.start() - 40):m.start()])[-1]
            if _NEGACAO.search(oracao):
                continue
            return "doutrina"
        if self._citacao_inventada(frase, t, autorizados):
            return "citacao"
        return None

    def _citacao_inventada(self, frase: str, t: str, autorizados: str) -> bool:
        if not any(a in t for a in self._atribuicao):
            return False
        referencia = self._textos_autenticos + " " + _so_palavras(autorizados)
        for citacao in _ASPAS.findall(frase):
            trecho = _so_palavras(citacao)
            if len(trecho.split()) >= 4 and trecho not in referencia:
                return True
        return False

    def saida_segura(self, frase: str) -> bool:
        return self.verificar_saida(frase) is None


def _so_palavras(texto: str) -> str:
    return " ".join(palavras(texto))


def _textos_autenticos() -> list[str]:
    """Orações, citações dos santos e textos do terço: podem ser citados entre aspas."""
    textos = []
    for nome, extrair in (
        ("oracoes.json", lambda d: [linha for o in d["oracoes"] for linha in o["linhas"]]),
        ("santos.json", lambda d: [c["texto"] for s in d["santos"] for c in s.get("citacoes", [])]),
        ("terco.json", lambda d: list(d["oracoes"].values())),
    ):
        arquivo = PASTA_DADOS / nome
        if arquivo.exists():
            textos += extrair(json.loads(arquivo.read_text(encoding="utf-8")))
    return textos
