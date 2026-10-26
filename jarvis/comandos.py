"""
Entende comandos de voz ou digitados ("quiz", "vamos rezar", "falar com Dom
Bosco", "eu arrumei a cama"...). Tudo o que não for comando vira conversa.
"""

from __future__ import annotations

import re

from jarvis.texto import STOPWORDS, contem_frase, normalizar, palavras, radicais

COMANDOS: dict[str, list[str]] = {
    "quiz": ["1", "quiz", "o quiz", "desafio", "quiz desafio", "jogo de perguntas", "me testa", "jogar"],
    "oracao": ["2", "rezar", "oracao", "orar", "reza comigo", "rezar comigo", "oracao guiada", "oracao da manha",
               "oracao da noite"],
    "exame": ["3", "exame", "exame de consciencia", "inspectorum", "fazer o exame"],
    "vozes": ["4", "vozes", "vozes das escrituras", "santos", "historia", "historias", "historia da biblia",
              "conta uma historia", "contar uma historia", "uma historia"],
    "mesada": ["5", "mesada", "cofrinho", "cofrinhos", "dinheiro", "meu dinheiro", "tarefas", "atividades",
               "minhas tarefas", "minhas atividades", "dizimo"],
    "conquistas": ["6", "conquistas", "medalhas", "minhas medalhas", "meu nivel", "meus pontos", "missoes",
                   "minhas missoes", "missoes do dia", "status", "pontos", "nivel"],
    "pais": ["7", "area dos pais", "pais", "modo pais", "painel dos pais"],
    "sair": ["0", "sair", "tchau", "desligar", "ate logo", "ate mais", "boa noite", "fui", "encerrar", "tchau tchau"],
    "ajuda": ["ajuda", "comandos", "o que voce sabe fazer", "o que voce faz", "menu", "opcoes", "help"],
}
# Estas frases valem em qualquer parte da fala
EM_QUALQUER_LUGAR: dict[str, list[str]] = {
    "conquistas": ["qual o meu nivel", "qual e o meu nivel", "quantos pontos eu tenho", "minhas conquistas"],
    "saldo": ["quanto eu tenho", "meu saldo", "quanto tenho no cofrinho", "quanto dinheiro eu tenho",
              "quanto tem no meu cofrinho", "quanto tem nos meus cofrinhos"],
    "normal": ["voltar ao normal", "volta ao normal", "modo jarvis", "sair do modo santo", "desligar holograma",
               "desliga o holograma", "volta jarvis", "voltar para o jarvis"],
}
_ENFEITES = r"^(?:(?:ei|oi|ola|ok|jarvis|por favor|eu|quero|queria|vamos|vamo|bora|abrir|abre|abra|ir para|ir pro|" \
            r"ir pra|me mostra|mostra|mostrar|ver|modo|fazer|faz|o|a|os|as|um|uma|meu|minha|meus|minhas|no|na|de|" \
            r"da|do|agora|entrar|entra|em|me|conta|contar|joga|jogar|comecar|comeca|iniciar)\s+)+"
_GATILHOS_SANTO = ("falar com", "conversar com", "chama o", "chama a", "chamar o", "chamar a", "chama",
                   "holograma", "modo santo", "modo", "quero o", "quero a", "trazer o", "traz o", "traz a")
_VERBOS_FEITO = re.compile(r"\b(\w{3,}ei|fiz|terminei|acabei|consegui|ajudei|li|limpei|guardei)\b")


def limpar_enfeites(texto: str) -> str:
    t = re.sub(r"[,;:!?.…]", " ", normalizar(texto))
    t = re.sub(r"\b(por favor|jarvis)\b", " ", t)
    return re.sub(_ENFEITES, "", re.sub(r"\s+", " ", t).strip()).strip()


def identificar_comando(texto: str) -> str | None:
    t = re.sub(r"\s+", " ", re.sub(r"[,;:!?.…]", " ", normalizar(texto))).strip()
    for comando, frases in EM_QUALQUER_LUGAR.items():
        if any(contem_frase(t, f) for f in frases):
            return comando
    limpo = limpar_enfeites(texto)
    for comando, frases in COMANDOS.items():
        if t in frases or limpo in frases:
            return comando
    return None


def pede_santo(texto: str) -> bool:
    t = normalizar(texto)
    return any(contem_frase(t, g) for g in _GATILHOS_SANTO)


def detectar_atividade(texto: str, atividades: list[dict]) -> dict | None:
    """'Jarvis, eu arrumei a minha cama!' -> atividade 'Arrumar a cama'."""
    t = normalizar(texto)
    if not _VERBOS_FEITO.search(t) or "?" in texto:
        return None
    falado = set(radicais(t))
    melhor, melhor_nota = None, 0
    for atividade in atividades:
        nome = radicais(atividade["nome"])
        nota = len(falado & set(nome))
        # uma palavra em comum só vale se for o verbo da atividade ("reguei" ~ "Regar as plantas")
        if nota == 1 and nome and nome[0] not in falado:
            nota = 0
        if nota > melhor_nota:
            melhor, melhor_nota = atividade, nota
    return melhor


def palavras_relevantes(texto: str) -> list[str]:
    return [p for p in palavras(texto) if p not in STOPWORDS]
