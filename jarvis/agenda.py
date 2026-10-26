"""
Agenda / planner da criança.

Mistura os compromissos que a criança cadastra (prova, aniversário, futebol...) com itens
automáticos da fé: o santo ou a festa do dia, o Dia do Senhor (domingo, com o horário da
Missa da família) e os dias santos de guarda do Brasil.

Os compromissos ficam num arquivo próprio (``<perfil>.agenda.json``) e o acesso é protegido
por uma trava, porque a interface gráfica pode ler e gravar a agenda ao mesmo tempo que o Jarvis.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from jarvis.armazenamento import agora
from jarvis.fe.liturgia import dia_liturgico, pascoa
from jarvis.texto import data_por_extenso, ler_data, ler_hora, normalizar

CATEGORIAS = {
    "escola": ("📚", "Escola"), "familia": ("👨‍👩‍👧", "Família"), "fe": ("⛪", "Fé"), "esporte": ("⚽", "Esporte e lazer"),
    "aniversario": ("🎂", "Aniversário"), "saude": ("🩺", "Saúde"), "outro": ("📌", "Outro"),
}
REPETICOES = {"": "não repete", "semanal": "toda semana", "anual": "todo ano"}
MAXIMO_EVENTOS = 500


@dataclass
class ItemAgenda:
    data: str
    hora: str
    titulo: str
    emoji: str
    categoria: str
    automatico: bool = False
    id: str = ""

    @property
    def texto_falado(self) -> str:
        return self.titulo + (f" às {hora_falada(self.hora)}" if self.hora else "")


def dias_santos_de_guarda(ano: int) -> dict[date, str]:
    """Além dos domingos, no Brasil: 1º de janeiro, Corpus Christi, 8 de dezembro e Natal."""
    return {
        date(ano, 1, 1): "Santa Maria, Mãe de Deus",
        pascoa(ano) + timedelta(days=60): "Corpus Christi",
        date(ano, 12, 8): "Imaculada Conceição",
        date(ano, 12, 25): "Natal do Senhor",
    }


class Agenda:
    def __init__(self, arquivo: Path, missa_horario: str = "", missa_local: str = ""):
        self.arquivo = arquivo
        self.missa_horario, self.missa_local = missa_horario, missa_local
        self._trava = threading.RLock()
        try:
            self._eventos: list[dict] = json.loads(arquivo.read_text(encoding="utf-8"))["eventos"]
        except (OSError, ValueError, KeyError):
            self._eventos = []

    # ------------------------------------------------------------- gravação
    def _salvar(self) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps({"eventos": self._eventos}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporario, self.arquivo)

    def adicionar(self, titulo: str, data: date, hora: str = "", categoria: str = "outro", repetir: str = "") -> dict:
        titulo = " ".join(titulo.split())[:60]
        if not titulo:
            raise ValueError("O compromisso precisa de um nome.")
        categoria = categoria if categoria in CATEGORIAS else "outro"
        evento = {"id": uuid.uuid4().hex[:8], "titulo": titulo, "data": data.isoformat(), "hora": hora,
                  "categoria": categoria, "emoji": CATEGORIAS[categoria][0],
                  "repetir": repetir if repetir in REPETICOES else "", "criado_em": agora()}
        with self._trava:
            if len(self._eventos) >= MAXIMO_EVENTOS:
                raise ValueError("A agenda está cheia. Apague compromissos antigos.")
            self._eventos.append(evento)
            self._salvar()
        return evento

    def remover(self, evento_id: str) -> bool:
        with self._trava:
            antes = len(self._eventos)
            self._eventos = [e for e in self._eventos if e["id"] != evento_id]
            if len(self._eventos) != antes:
                self._salvar()
                return True
        return False

    # -------------------------------------------------------------- leitura
    def _acontece_em(self, evento: dict, dia: date) -> bool:
        inicio = date.fromisoformat(evento["data"])
        if dia < inicio:
            return False
        if evento.get("repetir") == "semanal":
            return (dia - inicio).days % 7 == 0
        if evento.get("repetir") == "anual":
            return (dia.month, dia.day) == (inicio.month, inicio.day)
        return dia == inicio

    def automaticos(self, dia: date) -> list[ItemAgenda]:
        itens = []
        liturgia = dia_liturgico(dia)
        if liturgia.celebracao:
            itens.append(ItemAgenda(dia.isoformat(), "", liturgia.celebracao, "✝️", "fe", True, f"lit-{dia}"))
        guarda = dias_santos_de_guarda(dia.year)
        if dia.weekday() == 6 or dia in guarda:
            titulo = "Dia do Senhor: Missa em família" if dia.weekday() == 6 else f"Dia santo ({guarda[dia]}): Missa"
            if self.missa_local:
                titulo += f" — {self.missa_local}"
            itens.append(ItemAgenda(dia.isoformat(), self.missa_horario, titulo, "⛪", "missa", True, f"missa-{dia}"))
        return itens

    def do_dia(self, dia: date | None = None) -> list[ItemAgenda]:
        dia = dia or date.today()
        with self._trava:
            proprios = [ItemAgenda(dia.isoformat(), e["hora"], e["titulo"], e["emoji"], e["categoria"], False, e["id"])
                        for e in self._eventos if self._acontece_em(e, dia)]
        itens = self.automaticos(dia) + proprios
        return sorted(itens, key=lambda i: (i.hora or "99:99", not i.automatico))

    def intervalo(self, inicio: date, fim: date) -> list[ItemAgenda]:
        itens, dia = [], inicio
        while dia < fim and len(itens) < 2000:
            itens += self.do_dia(dia)
            dia += timedelta(days=1)
        return itens

    def para_calendario(self, inicio: date, fim: date) -> list[dict]:
        """Formato do FullCalendar (interface gráfica)."""
        cores = {"missa": "#ffd75f", "fe": "#d7afff", "escola": "#00d7ff", "familia": "#ff87d7", "esporte": "#5fffaf",
                 "aniversario": "#ffaf5f", "saude": "#ff5f5f", "outro": "#87afff"}
        eventos = []
        for item in self.intervalo(inicio, fim):
            evento = {"id": item.id, "title": f"{item.emoji} {item.titulo}", "allDay": not item.hora,
                      "start": f"{item.data}T{item.hora}:00" if item.hora else item.data,
                      "color": cores.get(item.categoria, "#87afff"), "textColor": "#001018",
                      "extendedProps": {"automatico": item.automatico, **asdict(item)}}
            eventos.append(evento)
        return eventos


# -----------------------------------------------------------------------------
#  "Jarvis, marca prova de matemática na sexta às 8h"
# -----------------------------------------------------------------------------
_GATILHO = re.compile(
    r"^\W*(?:(?:ei|oi|ok|ola|olá)\W+)?(?:jarvis\W+)?(?:por favor\W+)?"
    r"(?:(?:me\s+)?lembr(?:a|e|ar)(?:-me)?\s+(?:de|que)|marc(?:a|e|ar)|anot(?:a|e|ar)|agend(?:a|e|ar)|"
    r"coloc(?:a|e|ar)|p[õo]e|ponha|bot(?:a|e))\s+"
    r"(?:(?:na|em)\s+(?:minha\s+)?agenda\W*\s*)?(?:que\s+(?:eu\s+)?(?:tenho|vou ter)\s+|pra mim\s+|para mim\s+)?",
    re.IGNORECASE)
_DIAS = r"(?:segunda|ter[çc]a|quarta|quinta|sexta)(?:[- ]feira)?|s[áa]bado|domingo"
_MESES = r"janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
_TRECHOS_DE_TEMPO = [
    r"\b(?:tod[ao]s?\s+(?:as\s+|os\s+)?)(?:" + _DIAS + r")s?\b",
    r"\btoda\s+semana\b|\btodo\s+ano\b",
    r"\b(?:(?:para|pra|no|na|em)\s+)?(?:depois de amanh[ãa]|amanh[ãa]|hoje)\b",
    r"\b(?:(?:para|pra|no|na|nesta|nessa|em)\s+)?(?:pr[óo]xim[ao]\s+)?(?:" + _DIAS + r")(?:\s+que\s+vem)?\b",
    r"\b(?:(?:para|pra|no|em)\s+)?(?:o\s+)?dia\s+\d{1,2}(?:\s+de\s+(?:" + _MESES + r"))?\b",
    r"\b(?:(?:para|pra|no|em)\s+)?\d{1,2}\s+de\s+(?:" + _MESES + r")\b",
    r"\b(?:(?:para|pra|no|em|dia)\s+)*\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
    r"\b(?:(?:na|para|pra)\s+)?semana\s+que\s+vem\b",
    r"\b(?:(?:[àa]s?|ao|por volta d[ae]s?)\s+)?meio[- ]dia\b",
    r"\b(?:(?:[àa]s?|por volta d[ae]s?)\s+)?\d{1,2}(?:\s*(?:h|:)\s*\d{2}|\s*h(?:oras?)?\b|\s+horas?\b)?"
    r"(?:\s+da\s+(?:manh[ãa]|tarde|noite|madrugada))?(?!\s*(?:/|de\s))\b",
]
# Ordem importa: "apresentação de piano" é lazer, "trabalho de ciências" é escola.
_CATEGORIAS_PALAVRAS = {
    "aniversario": ["aniversario", "niver"],
    "saude": ["medico", "medica", "dentista", "vacina", "consulta", "oculista", "pediatra", "fono", "terapia"],
    "fe": ["missa", "catequese", "terco", "rosario", "crisma", "confissao", "comunhao", "igreja", "paroquia",
           "grupo de oracao", "adoracao", "retiro", "coroinha", "novena"],
    "esporte": ["futebol", "futsal", "natacao", "ballet", "bale", "judo", "karate", "treino", "jogo", "volei",
                "basquete", "ginastica", "danca", "musica", "violao", "piano", "teclado", "bateria", "bicicleta", "skate",
                "escoteiros", "acampamento"],
    "familia": ["vovo", "vovo", "avo", "avos", "tio", "tia", "primo", "prima", "familia", "viagem", "passeio", "visita",
                "casamento", "batizado", "almoco", "jantar", "churrasco"],
    "escola": ["prova", "provas", "teste", "trabalho", "escola", "aula", "licao", "dever", "tarefa", "redacao",
               "feira de ciencias", "apresentacao", "reuniao", "boletim", "simulado", "recuperacao", "lanche", "livro"],
}


def adivinhar_categoria(titulo: str) -> str:
    t = normalizar(titulo)
    for categoria, palavras in _CATEGORIAS_PALAVRAS.items():
        if any(re.search(rf"\b{re.escape(p)}\b", t) for p in palavras):
            return categoria
    return "outro"


def interpretar_compromisso(texto: str, hoje: date | None = None) -> dict | None:
    """
    'Jarvis, marca prova de matemática na sexta às 8h' ->
    {'titulo': 'Prova de matemática', 'data': date(...), 'hora': '08:00', 'categoria': 'escola', 'repetir': ''}.
    Retorna None se a frase não é um pedido de agenda. 'data' pode vir None (aí o Jarvis pergunta o dia).
    """
    m = _GATILHO.match(texto)
    if not m:
        return None
    resto = texto[m.end():].strip()
    titulo = resto
    for padrao in _TRECHOS_DE_TEMPO:
        titulo = re.sub(padrao, " ", titulo, flags=re.IGNORECASE)
    titulo = re.sub(r"\s+", " ", titulo).strip(" ,.;:!?-")
    titulo = re.sub(r"(?:\s+(?:na|no|nas|nos|em|de|da|do|para|pra|as|às|a|e|que|dia))+$", "", titulo, flags=re.IGNORECASE)
    titulo = re.sub(r"^(?:(?:um|uma|o|a|que|é|e)\s+)+", "", titulo, flags=re.IGNORECASE).strip(" ,.;:!?-")
    if len(titulo) < 2:
        return None
    data, hora = ler_data(resto, hoje), ler_hora(resto)
    if data is None and not hora and "agenda" not in m.group(0).lower():
        return None  # "marca um gol!" não é compromisso
    t = normalizar(resto)
    semanal = re.search(r"\b(toda semana|tod[ao]s? (as |os )?(segunda|terca|quarta|quinta|sexta|sabado|domingo))", t)
    repetir = "semanal" if semanal else "anual" if "todo ano" in t else ""
    categoria = adivinhar_categoria(titulo)
    if categoria == "aniversario" and not repetir:
        repetir = "anual"
    return {"titulo": titulo[0].upper() + titulo[1:], "data": data, "hora": hora, "categoria": categoria,
            "repetir": repetir}


def descrever_quando(dia: date, hora: str, hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    if dia == hoje:
        quando = "hoje"
    elif dia == hoje + timedelta(days=1):
        quando = "amanhã"
    else:
        quando = data_por_extenso(dia)
    return f"{quando} às {hora_falada(hora)}" if hora else quando


def hora_falada(hora: str) -> str:
    """'09:30' -> '9h30'; '15:00' -> '15h'."""
    h, m = hora.split(":")
    return f"{int(h)}h" + (m if m != "00" else "")


def resumo_do_dia(itens: list[ItemAgenda], dia: date | None = None) -> str:
    """Frase falada: o que tem na agenda hoje (compromissos da criança e a Missa)."""
    proprios = [i for i in itens if not i.automatico or i.categoria == "missa"]
    if not proprios:
        return "Você não tem compromissos marcados para hoje."
    partes = [i.texto_falado for i in proprios[:4]]
    lista = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]
    return f"Na sua agenda de hoje: {lista}."
