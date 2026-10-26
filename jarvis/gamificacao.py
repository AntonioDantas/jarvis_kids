"""
Gamificação: Pontos de Sabedoria, níveis, sequência de dias, missões diárias
e medalhas. Tudo é calculado localmente e salvo no perfil da criança.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from jarvis.armazenamento import Perfil, hoje
from jarvis.texto import normalizar

# (pontos mínimos, nome do nível, emoji)
NIVEIS = [
    (0, "Recruta Digital", "🛰️"),
    (100, "Cadete Estelar", "🚀"),
    (250, "Explorador Quântico", "🔭"),
    (500, "Engenheiro da Luz", "💡"),
    (900, "Guardião da Sabedoria", "🛡️"),
    (1400, "Cavaleiro da Fé", "⚔️"),
    (2100, "Comandante Galáctico", "🌌"),
    (3000, "Mestre Celestial", "👑"),
]

PONTOS = {
    "oracao": 15,
    "oracao_matinal": 25,
    "exame": 30,
    "historia": 10,
    "quiz_acerto": 10,
    "quiz_perfeito": 30,
    "tarefa": 10,
    "missao": 20,
    "todas_missoes": 50,
    "conversa_santo": 5,
    "terco": 50,
    "agenda": 5,
    "sequencia_por_dia": 5,
}
LIMITE_DIARIO_PERGUNTAS = 60  # evita "farmar" pontos com perguntas repetidas


@dataclass
class Evento:
    tipo: str                       # pontos | nivel | medalha | missao | missoes | sequencia
    texto: str
    pontos: int = 0
    som: str = "moeda"
    dados: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Medalha:
    id: str
    nome: str
    emoji: str
    descricao: str
    condicao: Callable[[dict, dict], bool]   # (estatisticas, jogo) -> bool


def _e(chave: str, minimo: int) -> Callable[[dict, dict], bool]:
    return lambda est, _jogo: est.get(chave, 0) >= minimo


MEDALHAS = [
    Medalha("primeiro_contato", "Primeiro Contato", "📡", "Fez a primeira pergunta ao Jarvis", _e("perguntas", 1)),
    Medalha("mente_curiosa", "Mente Curiosa", "🧠", "Fez 50 perguntas curiosas", _e("perguntas", 50)),
    Medalha("genio_quiz", "Gênio do Quiz", "🧩", "Acertou 10 perguntas no Quiz", _e("quiz_acertos", 10)),
    Medalha("mestre_quiz", "Mestre do Quiz", "🏅", "Acertou 50 perguntas no Quiz", _e("quiz_acertos", 50)),
    Medalha("missao_perfeita", "Missão Perfeita", "💯", "Gabaritou uma rodada do Quiz", _e("quiz_perfeitos", 1)),
    Medalha("sentinela_oracao", "Sentinela da Oração", "🙏", "Rezou 7 vezes com o Jarvis", _e("oracoes", 7)),
    Medalha("guerreiro_manha", "Guerreiro da Manhã", "🌅", "Fez 7 orações matinais", _e("oracoes_matinais", 7)),
    Medalha("guardiao_rosario", "Guardião do Rosário", "📿", "Rezou 5 terços com o Jarvis", _e("tercos", 5)),
    Medalha("coracao_limpo", "Coração Limpo", "💎", "Fez 7 Exames de Consciência", _e("exames", 7)),
    Medalha("explorador_biblia", "Explorador da Bíblia", "📜", "Ouviu 5 histórias da Bíblia", _e("historias", 5)),
    Medalha("maos_a_obra", "Mãos à Obra", "🛠️", "Concluiu 10 atividades da mesada", _e("tarefas", 10)),
    Medalha("coracao_generoso", "Coração Generoso", "❤️", "Entregou o dízimo ou uma doação",
            lambda est, _j: est.get("dizimos_entregues", 0) + est.get("doacoes_entregues", 0) >= 1),
    Medalha("poupador_estelar", "Poupador Estelar", "🐷", "Atingiu a meta de um cofrinho", _e("metas_atingidas", 1)),
    Medalha("investidor_mirim", "Investidor Mirim", "📈", "O investimento já rendeu 1 real", _e("rendimento_centavos", 100)),
    Medalha("amigo_dos_santos", "Amigo dos Santos", "😇", "Conversou com 3 santos diferentes",
            lambda _est, jogo: len(jogo.get("santos_visitados", [])) >= 3),
    Medalha("combo_7", "Combo de 7 Dias", "🔥", "Usou o Jarvis 7 dias seguidos", _e("maior_sequencia", 7)),
    Medalha("lenda_constancia", "Lenda da Constância", "⭐", "Usou o Jarvis 30 dias seguidos", _e("maior_sequencia", 30)),
]

# id -> (descrição, estatística que conta, meta)
MISSOES = {
    "oracao": ("Fazer uma oração com o Jarvis", "oracoes", 1),
    "quiz": ("Acertar 3 perguntas no Quiz", "quiz_acertos", 3),
    "exame": ("Fazer o Exame de Consciência", "exames", 1),
    "tarefa": ("Concluir 1 atividade da mesada", "tarefas", 1),
    "pergunta": ("Fazer 2 perguntas curiosas", "perguntas", 2),
    "historia": ("Ouvir uma história da Bíblia", "historias", 1),
    "santo": ("Conversar com um santo", "conversas_santos", 1),
    "terco": ("Rezar um terço (pode ser o mini-terço)", "tercos", 1),
}

_INTERROGATIVAS = ("por que", "porque", "como", "o que", "oque", "qual", "quais", "quem", "quando",
                   "onde", "quanto", "quantos", "quantas", "sera que", "e verdade", "explica", "me conta",
                   "voce sabe", "pra que", "para que", "e se")
_PROFUNDAS = ("por que", "como funciona", "qual a diferenca", "o que aconteceria", "e se", "para que serve",
              "pra que serve", "explica", "como e possivel", "de onde vem", "como sabemos")
_TEMAS_BONUS = ("deus", "jesus", "santo", "biblia", "igreja", "oracao", "universo", "planeta", "ciencia",
                "corpo", "animal", "historia", "computador", "robo", "matematica", "dinheiro", "virtude")


def nivel_de(pontos: int) -> tuple[int, str, str, int, int | None]:
    """Retorna (índice, nome, emoji, pontos mínimos do nível, pontos do próximo nível)."""
    indice = 0
    for i, (minimo, _nome, _emoji) in enumerate(NIVEIS):
        if pontos >= minimo:
            indice = i
    minimo, nome, emoji = NIVEIS[indice]
    proximo = NIVEIS[indice + 1][0] if indice + 1 < len(NIVEIS) else None
    return indice, nome, emoji, minimo, proximo


def avaliar_pergunta(texto: str) -> tuple[int, str]:
    """Heurística local e instantânea para premiar perguntas curiosas."""
    t = normalizar(texto)
    palavras = t.split()
    e_pergunta = "?" in texto or any(t.startswith(i) or f" {i} " in f" {t} " for i in _INTERROGATIVAS)
    if not e_pergunta or len(palavras) < 3:
        return 0, ""
    pontos, rotulo = 2, "Pergunta Curiosa"
    if any(p in t for p in _PROFUNDAS):
        pontos, rotulo = pontos + 3, "Pergunta de Cientista"
    if len(palavras) >= 8:
        pontos += 2
    if any(tema in t for tema in _TEMAS_BONUS):
        pontos += 2
        if rotulo == "Pergunta de Cientista":
            rotulo = "Pergunta de Filósofo"
    return min(pontos, 10), rotulo


class Gamificacao:
    def __init__(self, perfil: Perfil):
        self.perfil = perfil

    # --------------------------------------------------------------- leitura
    @property
    def jogo(self) -> dict:
        return self.perfil.jogo

    @property
    def pontos(self) -> int:
        return self.jogo["pontos"]

    @property
    def estatisticas(self) -> dict:
        return self.jogo["estatisticas"]

    @property
    def nivel(self) -> tuple[int, str, str, int, int | None]:
        return nivel_de(self.pontos)

    @property
    def nome_nivel(self) -> str:
        return self.nivel[1]

    # ----------------------------------------------------------------- ações
    def ganhar(self, pontos: int, motivo: str) -> list[Evento]:
        if pontos <= 0:
            return []
        nivel_antes = self.nivel[0]
        self.jogo["pontos"] += pontos
        eventos = [Evento("pontos", f"+{pontos} Pontos de Sabedoria — {motivo}", pontos, "moeda")]
        indice, nome, emoji, *_ = self.nivel
        if indice > nivel_antes:
            eventos.append(Evento("nivel", f"{emoji} NOVO NÍVEL: {nome}!", som="nivel",
                                  dados={"indice": indice, "nome": nome}))
        return eventos

    def registrar(self, estatistica: str, quantidade: int = 1) -> list[Evento]:
        """Soma uma estatística e confere missões e medalhas."""
        self.estatisticas[estatistica] = self.estatisticas.get(estatistica, 0) + quantidade
        return self._avancar_missoes(estatistica, quantidade) + self._conferir_medalhas()

    def iniciar_dia(self) -> list[Evento]:
        """Atualiza a sequência de dias seguidos e sorteia as missões do dia."""
        eventos: list[Evento] = []
        dia = hoje()
        ultimo = self.jogo.get("ultimo_dia", "")
        if ultimo != dia:
            ontem = (date.fromisoformat(dia) - timedelta(days=1)).isoformat()
            self.jogo["dias_seguidos"] = self.jogo.get("dias_seguidos", 0) + 1 if ultimo == ontem else 1
            self.jogo["ultimo_dia"] = dia
            seq = self.jogo["dias_seguidos"]
            self.estatisticas["maior_sequencia"] = max(self.estatisticas.get("maior_sequencia", 0), seq)
            bonus = PONTOS["sequencia_por_dia"] * min(seq, 7)
            eventos += self.ganhar(bonus, f"sequência de {seq} dia{'s' if seq > 1 else ''} 🔥")
            eventos += self._conferir_medalhas()
        self._sortear_missoes()
        return eventos

    def dentro_do_limite(self, chave: str, maximo: int) -> bool:
        """Conta usos diários (ex.: 3 orações premiadas por dia) para evitar 'farmar' pontos."""
        limites = self.jogo.setdefault("limites", {})
        if limites.get("data") != hoje():
            limites.clear()
            limites.update({"data": hoje(), "contagens": {}})
        contagens = limites["contagens"]
        if contagens.get(chave, 0) >= maximo:
            return False
        contagens[chave] = contagens.get(chave, 0) + 1
        return True

    def registrar_santo(self, santo_id: str) -> list[Evento]:
        if santo_id not in self.jogo["santos_visitados"]:
            self.jogo["santos_visitados"].append(santo_id)
        return self.registrar("conversas_santos")

    def pontuar_pergunta(self, texto: str) -> list[Evento]:
        pontos, rotulo = avaliar_pergunta(texto)
        if not pontos:
            return []
        controle = self.jogo["perguntas_hoje"]
        if controle.get("data") != hoje():
            controle.update({"data": hoje(), "pontos": 0, "vistas": []})
        chave = normalizar(texto)[:120]
        if chave in controle["vistas"]:
            return []
        controle["vistas"] = (controle["vistas"] + [chave])[-50:]
        disponivel = LIMITE_DIARIO_PERGUNTAS - controle["pontos"]
        pontos = min(pontos, max(0, disponivel))
        eventos = self.registrar("perguntas")
        if pontos:
            controle["pontos"] += pontos
            eventos = self.ganhar(pontos, rotulo) + eventos
        return eventos

    # --------------------------------------------------------------- missões
    def missoes_de_hoje(self) -> list[dict]:
        self._sortear_missoes()
        return self.jogo["missoes"]["lista"]

    def _sortear_missoes(self) -> None:
        missoes = self.jogo["missoes"]
        if missoes.get("data") == hoje() and missoes.get("lista"):
            return
        sorteio = random.Random(f"{hoje()}-{self.perfil.nome}")
        outras = [m for m in MISSOES if m != "oracao"]
        escolhidas = ["oracao"] + sorteio.sample(outras, 3)
        missoes.update({
            "data": hoje(),
            "bonus_pago": False,
            "lista": [
                {"id": m, "descricao": MISSOES[m][0], "meta": MISSOES[m][2], "progresso": 0, "concluida": False}
                for m in escolhidas
            ],
        })

    def _avancar_missoes(self, estatistica: str, quantidade: int) -> list[Evento]:
        self._sortear_missoes()
        eventos: list[Evento] = []
        missoes = self.jogo["missoes"]
        for missao in missoes["lista"]:
            if missao["concluida"] or MISSOES.get(missao["id"], ("", "", 0))[1] != estatistica:
                continue
            missao["progresso"] = min(missao["meta"], missao["progresso"] + quantidade)
            if missao["progresso"] >= missao["meta"]:
                missao["concluida"] = True
                eventos.append(Evento("missao", f"🎯 Missão cumprida: {missao['descricao']}", som="missao"))
                eventos += self.ganhar(PONTOS["missao"], "missão do dia")
        if all(m["concluida"] for m in missoes["lista"]) and not missoes["bonus_pago"]:
            missoes["bonus_pago"] = True
            eventos.append(Evento("missoes", "🏆 TODAS AS MISSÕES DO DIA CONCLUÍDAS!", som="nivel"))
            eventos += self.ganhar(PONTOS["todas_missoes"], "dia perfeito")
        return eventos

    def _conferir_medalhas(self) -> list[Evento]:
        eventos = []
        for medalha in MEDALHAS:
            if medalha.id in self.jogo["medalhas"]:
                continue
            if medalha.condicao(self.estatisticas, self.jogo):
                self.jogo["medalhas"].append(medalha.id)
                eventos.append(Evento("medalha", f"{medalha.emoji} MEDALHA DESBLOQUEADA: {medalha.nome}!",
                                      som="medalha", dados={"descricao": medalha.descricao}))
        return eventos
