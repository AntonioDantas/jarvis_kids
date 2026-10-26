"""
Calendário litúrgico calculado no próprio computador (sem internet).

Calcula a Páscoa (algoritmo gregoriano), as festas móveis, o tempo litúrgico, a cor do dia,
o ano A/B/C dos domingos e contagens regressivas — seguindo as regras do Brasil:
Epifania, Ascensão, São Pedro e São Paulo, Assunção e Todos os Santos celebrados no domingo;
Corpus Christi na quinta-feira.

Limitações (documentadas de propósito): a precedência completa entre celebrações e as
transferências raras de solenidades não são tratadas; para isso, consulte o calendário oficial
da CNBB ou da sua diocese.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from jarvis.dados import carregar_dados

SIGNIFICADO_CORES = {
    "verde": "a cor da esperança e do crescimento",
    "roxo": "a cor da preparação e da conversão",
    "branco": "a cor da alegria e da festa",
    "vermelho": "a cor do fogo do Espírito Santo e do amor dos mártires",
    "rosa": "a cor da alegria no meio da espera",
}
EVANGELISTAS = {"A": "Mateus", "B": "Marcos", "C": "Lucas"}

# Solenidades de data fixa que mudam a cor do dia (as transferidas para o domingo no Brasil ficam de fora).
SOLENIDADES_FIXAS = {
    (1, 1): ("Santa Maria, Mãe de Deus", "branco"),
    (3, 19): ("São José, esposo de Maria", "branco"),
    (3, 25): ("Anunciação do Senhor", "branco"),
    (6, 24): ("Nascimento de São João Batista", "branco"),
    (10, 12): ("Nossa Senhora Aparecida, Padroeira do Brasil", "branco"),
    (11, 2): ("Finados: rezamos por todos os que já morreram", "roxo"),
    (12, 8): ("Imaculada Conceição de Nossa Senhora", "branco"),
    (12, 25): ("Natal do Senhor", "branco"),
}


@dataclass
class DiaLiturgico:
    data: date
    tempo: str
    cor: str
    celebracao: str | None
    ano: str  # A, B ou C

    @property
    def evangelista(self) -> str:
        return EVANGELISTAS[self.ano]

    @property
    def significado_cor(self) -> str:
        return SIGNIFICADO_CORES[self.cor]


def pascoa(ano: int) -> date:
    """Domingo de Páscoa no calendário gregoriano (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = (h + l_ - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def _domingo_ate(dia: date) -> date:
    """O domingo igual ou anterior a ``dia``."""
    return dia - timedelta(days=(dia.weekday() + 1) % 7)


def inicio_advento(ano: int) -> date:
    return _domingo_ate(date(ano, 12, 24)) - timedelta(weeks=3)


def epifania(ano: int) -> date:
    """No Brasil, a Epifania é celebrada no domingo entre 2 e 8 de janeiro."""
    return _domingo_ate(date(ano, 1, 8))


def batismo_do_senhor(ano: int) -> date:
    ep = epifania(ano)
    return ep + timedelta(days=1) if ep.day >= 7 else ep + timedelta(days=7)


def sagrada_familia(ano: int) -> date:
    """Domingo entre 26 e 31 de dezembro; se o Natal cair no domingo, dia 30."""
    natal = date(ano, 12, 25)
    if natal.weekday() == 6:
        return date(ano, 12, 30)
    return natal + timedelta(days=6 - natal.weekday())


def festas_moveis(ano: int) -> dict[date, tuple[str, str]]:
    p = pascoa(ano)
    advento = inicio_advento(ano)
    dias = {
        epifania(ano): ("Epifania do Senhor: os Reis Magos visitam Jesus", "branco"),
        batismo_do_senhor(ano): ("Batismo do Senhor", "branco"),
        p - timedelta(days=46): ("Quarta-feira de Cinzas: começa a Quaresma", "roxo"),
        p - timedelta(days=21): ("4º Domingo da Quaresma (Laetare)", "rosa"),
        p - timedelta(days=7): ("Domingo de Ramos e da Paixão do Senhor", "vermelho"),
        p - timedelta(days=3): ("Quinta-feira Santa: a Última Ceia", "branco"),
        p - timedelta(days=2): ("Sexta-feira da Paixão do Senhor", "vermelho"),
        p - timedelta(days=1): ("Sábado Santo: à noite, a Vigília Pascal", "roxo"),
        p: ("Domingo de Páscoa: Jesus ressuscitou!", "branco"),
        p + timedelta(days=7): ("Domingo da Divina Misericórdia", "branco"),
        p + timedelta(days=42): ("Ascensão do Senhor", "branco"),
        p + timedelta(days=49): ("Pentecostes: a vinda do Espírito Santo", "vermelho"),
        p + timedelta(days=56): ("Santíssima Trindade", "branco"),
        p + timedelta(days=60): ("Corpus Christi: Corpo e Sangue de Cristo", "branco"),
        p + timedelta(days=68): ("Sagrado Coração de Jesus", "branco"),
        advento - timedelta(days=7): ("Nosso Senhor Jesus Cristo, Rei do Universo", "branco"),
        advento: ("1º Domingo do Advento: começa o novo ano litúrgico", "roxo"),
        advento + timedelta(days=14): ("3º Domingo do Advento (Gaudete)", "rosa"),
        sagrada_familia(ano): ("Sagrada Família: Jesus, Maria e José", "branco"),
        # No Brasil estas solenidades vão para o domingo da semana em que caem:
        _domingo_ate(date(ano, 7, 4)): ("São Pedro e São Paulo, apóstolos", "vermelho"),
        _domingo_ate(date(ano, 8, 21)): ("Assunção de Nossa Senhora ao Céu", "branco"),
    }
    todos_os_santos = _domingo_ate(date(ano, 11, 7))
    if todos_os_santos.day != 2:  # se cair em 2/11, Finados continua no domingo
        dias[todos_os_santos] = ("Todos os Santos", "branco")
    return dias


def _tempo(dia: date) -> tuple[str, str]:
    ano = dia.year
    p = pascoa(ano)
    if dia >= inicio_advento(ano):
        return ("Natal", "branco") if dia >= date(ano, 12, 25) else ("Advento", "roxo")
    if dia <= batismo_do_senhor(ano):
        return "Natal", "branco"
    if dia < p - timedelta(days=46):
        return "Tempo Comum", "verde"
    if dia < p - timedelta(days=3):
        return "Quaresma", "roxo"
    if dia < p:
        return "Tríduo Pascal", "roxo"
    if dia <= p + timedelta(days=49):
        return "Tempo Pascal", "branco"
    return "Tempo Comum", "verde"


def ano_liturgico(dia: date) -> str:
    """Ano A, B ou C dos domingos (o ano litúrgico começa no 1º domingo do Advento)."""
    ano_final = dia.year + 1 if dia >= inicio_advento(dia.year) else dia.year
    return {1: "A", 2: "B", 0: "C"}[ano_final % 3]


def dia_liturgico(dia: date | None = None) -> DiaLiturgico:
    dia = dia or date.today()
    tempo, cor = _tempo(dia)
    celebracao = None
    moveis = festas_moveis(dia.year)
    p = pascoa(dia.year)
    semana_santa_ou_oitava = p - timedelta(days=7) <= dia <= p + timedelta(days=7)
    if dia in moveis:
        celebracao, cor = moveis[dia]
    elif (dia.month, dia.day) in SOLENIDADES_FIXAS and not semana_santa_ou_oitava:
        celebracao, cor = SOLENIDADES_FIXAS[(dia.month, dia.day)]
    else:
        celebracao = carregar_dados("calendario_santos.json")["dias"].get(dia.strftime("%m-%d"))
    return DiaLiturgico(dia, tempo, cor, celebracao, ano_liturgico(dia))


def proximas_grandes_festas(dia: date | None = None) -> list[tuple[str, int]]:
    """Contagem regressiva: [('Natal', 59), ('Páscoa', 155), ...]."""
    dia = dia or date.today()
    alvos = []
    for nome, calcula in (("Natal", lambda a: date(a, 12, 25)), ("Páscoa", pascoa),
                          ("Pentecostes", lambda a: pascoa(a) + timedelta(days=49))):
        data = calcula(dia.year)
        if data < dia:
            data = calcula(dia.year + 1)
        alvos.append((nome, (data - dia).days))
    return sorted(alvos, key=lambda x: x[1])


def resumo_falado(info: DiaLiturgico) -> str:
    texto = f"Hoje estamos no {info.tempo}, e a cor da Igreja é {info.cor}, {info.significado_cor}."
    if info.celebracao:
        texto += f" Hoje a Igreja celebra: {info.celebracao}."
    return texto
