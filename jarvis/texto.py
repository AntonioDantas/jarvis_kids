"""
Utilidades de texto em português: normalização, radicais (para busca e
comandos de voz), divisão em frases, valores em dinheiro e limpeza para TTS.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "e", "em",
    "no", "na", "nos", "nas", "por", "para", "pra", "pro", "com", "sem", "que", "se", "me", "te",
    "eu", "tu", "ele", "ela", "voce", "voces", "eles", "elas", "meu", "minha", "seu", "sua",
    "ao", "aos", "isso", "isto", "esse", "essa", "este", "esta", "aquele", "aquela", "ja", "mais",
    "muito", "muita", "bem", "tem", "ter", "ser", "foi", "sao", "era", "como", "qual", "quais",
    "quem", "quando", "onde", "porque", "por que", "oque", "ou", "mas", "entao", "tambem", "so",
    "jarvis", "favor", "pode", "poderia", "sobre", "lhe", "la", "ai", "ne", "tipo", "ate", "nao",
    "sim", "ola", "oi", "hoje", "vou", "vai", "quero", "queria", "gostaria", "fala", "falar",
    "diga", "conta", "contar", "explica", "explicar", "sabe", "saber", "coisa", "coisas", "fazer",
    "faz", "fiz", "fez", "feito", "acabei", "terminei", "quanto", "quantos", "quanta", "quantas",
    "mesmo", "gente", "todo", "toda", "todos", "todas", "vez", "vezes", "existe", "acontece",
}

_ORDINAIS_FALA = ("primeiro", "segundo", "terceiro", "quarto", "quinto", "sexto", "sétimo", "oitavo",
                  "nono", "décimo")
_ORDINAIS = {1: "primeiro", 2: "segundo", 3: "terceiro", 4: "quarto", 5: "quinto", 6: "sexto",
             7: "setimo", 8: "oitavo", 9: "nono", 10: "decimo"}

_SUFIXOS = (
    "amentos", "imentos", "amento", "imento", "mente", "acoes", "icoes", "acao", "icao", "coes",
    "cao", "ando", "endo", "indo", "ados", "idos", "ado", "ido", "ar", "er", "ir", "ei",
    "oes", "aes", "ais", "eis", "is", "as", "es", "os", "a", "e", "o", "s",
)


def sem_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos, ordinais por extenso ("4º" -> "quarto") e espaços únicos."""
    texto = re.sub(r"\b(10|[1-9])\s?[º°ª]", lambda m: _ORDINAIS[int(m.group(1))], texto)
    return re.sub(r"\s+", " ", sem_acentos(texto.lower())).strip()


def palavras(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalizar(texto))


def radical(palavra: str) -> str:
    """Radical simplificado: 'arrumei', 'arrumar' e 'arrumando' viram 'arrum'."""
    if len(palavra) <= 3 or palavra.isdigit():
        return palavra
    for sufixo in _SUFIXOS:
        if palavra.endswith(sufixo) and len(palavra) - len(sufixo) >= 3:
            palavra = palavra[: -len(sufixo)]
            if sufixo == "ei":  # reguei -> reg(ar), fiquei -> fic(ar), brinquei -> brinc(ar)
                if palavra.endswith("gu"):
                    palavra = palavra[:-1]
                elif palavra.endswith("qu"):
                    palavra = palavra[:-2] + "c"
            break
    return palavra[:6]


def radicais(texto: str, remover_stopwords: bool = True) -> list[str]:
    return [
        radical(p) for p in palavras(texto) if not (remover_stopwords and p in STOPWORDS)
    ]


def contem_frase(texto_normalizado: str, frase: str) -> bool:
    """Procura uma frase inteira (com limites de palavra) num texto já normalizado."""
    return re.search(rf"(?<![a-z0-9]){re.escape(normalizar(frase))}(?![a-z0-9])", texto_normalizado) is not None


# -----------------------------------------------------------------------------
#  Frases (para falar enquanto a IA ainda está pensando)
# -----------------------------------------------------------------------------
_ABREVIACOES = {"sr", "sra", "dr", "dra", "sto", "sta", "pe", "prof", "profa", "n", "no", "pag", "cap", "s", "d"}
_FIM_FRASE = re.compile(r"([.!?…]+)[\"'”»)]*(\s+|$)|\n+")


def separar_frases(buffer: str, final: bool = False, max_sem_pontuacao: int = 220) -> tuple[list[str], str]:
    """
    Separa as frases completas de um texto que ainda está chegando (streaming).
    Retorna (frases_prontas, resto_incompleto). Com ``final=True`` o resto também sai.
    """
    frases: list[str] = []
    inicio = 0
    for m in _FIM_FRASE.finditer(buffer):
        if m.group(2) == "" and not final and m.end() == len(buffer):
            break  # pontuação no fim do buffer: pode ser "3." de "3.5" — espere mais texto
        trecho = buffer[inicio:m.end()]
        ultima = re.findall(r"([A-Za-zÀ-ÿ]+)\.\s*$", trecho)
        if ultima and normalizar(ultima[0]) in _ABREVIACOES:
            continue  # "S. João", "Pe. Fábio": não é fim de frase
        if trecho.strip():
            frases.append(trecho.strip())
        inicio = m.end()
    resto = buffer[inicio:]
    if final and resto.strip():
        frases.append(resto.strip())
        resto = ""
    elif len(resto) > max_sem_pontuacao:
        corte = max(resto.rfind(", ", 0, max_sem_pontuacao), resto.rfind("; ", 0, max_sem_pontuacao))
        if corte > 40:
            frases.append(resto[: corte + 1].strip())
            resto = resto[corte + 2:]
    return frases, resto


# -----------------------------------------------------------------------------
#  Dinheiro: centavos <-> texto
# -----------------------------------------------------------------------------
def formatar_reais(centavos: int) -> str:
    sinal = "-" if centavos < 0 else ""
    reais, cents = divmod(abs(int(centavos)), 100)
    return f"{sinal}R$ {reais:,}".replace(",", ".") + f",{cents:02d}"


def reais_por_extenso(centavos: int) -> str:
    """Formato bom para a voz: '12 reais e 50 centavos'."""
    reais, cents = divmod(abs(int(centavos)), 100)
    partes = []
    if reais:
        partes.append(f"{reais} {'real' if reais == 1 else 'reais'}")
    if cents:
        partes.append(f"{cents} {'centavo' if cents == 1 else 'centavos'}")
    return " e ".join(partes) if partes else "zero reais"


_NUMEROS = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "quatorze": 14, "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18,
    "dezenove": 19, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
    "setenta": 70, "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200,
    "duzentas": 200, "trezentos": 300, "quatrocentos": 400, "quinhentos": 500, "seiscentos": 600,
    "setecentos": 700, "oitocentos": 800, "novecentos": 900,
}


def numero_por_palavras(texto: str) -> int | None:
    """'dois mil e quinhentos' -> 2500 ; 'trinta e sete' -> 37 ; '15' -> 15."""
    total, atual, achou = 0, 0, False
    for p in palavras(texto):
        if p.isdigit():
            atual += int(p)
            achou = True
        elif p in _NUMEROS:
            atual += _NUMEROS[p]
            achou = True
        elif p == "mil":
            total += (atual or 1) * 1000
            atual, achou = 0, True
        elif p == "e":
            continue
        elif achou:
            break
    return total + atual if achou else None


def ler_valor(texto: str) -> int | None:
    """
    Converte o que a criança digitou ou falou em centavos.
    Aceita: '2', '2,50', 'R$ 2.50', '1.000', '2 reais e 50 centavos',
    'dois reais e cinquenta', 'cinquenta centavos'.
    """
    t = normalizar(texto).replace("r$", " ")
    m_reais = re.search(r"\b(reais|real)\b", t)
    antes, depois = (t[: m_reais.start()], t[m_reais.end():]) if m_reais else (t, "")

    if not m_reais and re.search(r"\bcentavos?\b", antes):  # "cinquenta centavos"
        valor = numero_por_palavras(antes.split("centavo")[0])
        return min(valor, 99) if valor is not None else None

    m_num = re.search(r"\d[\d.]*(?:,\d{1,2})?", antes)
    if m_num:
        base: int | None = _decimal_em_centavos(m_num.group(0))
    else:
        n = numero_por_palavras(antes)
        base = n * 100 if n is not None else None

    if m_reais:  # "2 reais e 50 centavos" / "dois reais e cinquenta"
        extra = numero_por_palavras(depois) or 0
        return (base or 0) + min(extra, 99)
    return base


def _decimal_em_centavos(bruto: str) -> int:
    """'1.234,56' -> 123456 ; '2.50' -> 250 ; '1.000' -> 100000 ; '7' -> 700."""
    if "," in bruto:
        inteiro, frac = bruto.split(",")
        inteiro = inteiro.replace(".", "")
    elif re.fullmatch(r"\d+\.\d{1,2}", bruto):
        inteiro, frac = bruto.split(".")
    else:
        inteiro, frac = bruto.replace(".", ""), "0"
    return int(inteiro or 0) * 100 + int(frac.ljust(2, "0")[:2])


# -----------------------------------------------------------------------------
#  Limpeza para a voz (TTS)
# -----------------------------------------------------------------------------
_EMOJIS = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF️‍⭐⬆↔-⇿]"
)
_LIVROS_BIBLIA = {
    "Gn": "Gênesis", "Ex": "Êxodo", "Lv": "Levítico", "Nm": "Números", "Dt": "Deuteronômio",
    "Js": "Josué", "Jz": "Juízes", "Rt": "Rute", "1Sm": "Primeiro Samuel", "2Sm": "Segundo Samuel",
    "1Rs": "Primeiro Reis", "2Rs": "Segundo Reis", "Tb": "Tobias", "Jt": "Judite", "Est": "Ester",
    "Jó": "Jó", "Sl": "Salmo", "Pr": "Provérbios", "Ecl": "Eclesiastes", "Sb": "Sabedoria",
    "Eclo": "Eclesiástico", "Is": "Isaías", "Jr": "Jeremias", "Ez": "Ezequiel", "Dn": "Daniel",
    "Os": "Oseias", "Jn": "Jonas", "Mq": "Miqueias", "Ml": "Malaquias", "Mt": "Mateus",
    "Mc": "Marcos", "Lc": "Lucas", "Jo": "João", "At": "Atos dos Apóstolos", "Rm": "Romanos",
    "1Cor": "Primeira Coríntios", "2Cor": "Segunda Coríntios", "Gl": "Gálatas", "Ef": "Efésios",
    "Fl": "Filipenses", "Cl": "Colossenses", "1Ts": "Primeira Tessalonicenses",
    "1Tm": "Primeira Timóteo", "2Tm": "Segunda Timóteo", "Hb": "Hebreus", "Tg": "Tiago",
    "1Pd": "Primeira Pedro", "1Jo": "Primeira João", "Ap": "Apocalipse",
}
_REF_BIBLICA = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _LIVROS_BIBLIA), key=len, reverse=True)) + r")\s?(\d+),(\d+)(?:[-–](\d+))?"
)
# Só capítulo ("Lc 2", "Ex 20"). Abreviações ambíguas ("Os 2 peixes") ficam de fora.
_REF_CAPITULO = re.compile(
    r"\b("
    + "|".join(sorted((re.escape(k) for k in _LIVROS_BIBLIA if k not in {"Os", "Is", "Est", "Sb", "Jó", "At"}),
                      key=len, reverse=True))
    + r")\s(\d+)\b(?![,\d])"
)


def _ler_referencia(m: re.Match) -> str:
    livro, cap, v1, v2 = m.groups()
    versos = f"versículos {v1} a {v2}" if v2 else f"versículo {v1}"
    return f"{_LIVROS_BIBLIA[livro]}, capítulo {cap}, {versos}"


def preparar_para_fala(texto: str) -> str:
    """Remove símbolos que soariam estranhos na voz e deixa números legíveis."""
    t = _EMOJIS.sub("", texto)
    t = re.sub(r"[*_#`>|~]", "", t)
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.MULTILINE)
    t = re.sub(
        r"R\$\s?(\d[\d.]*)(?:,(\d{2}))?",
        lambda m: reais_por_extenso(int(m.group(1).replace(".", "")) * 100 + int(m.group(2) or 0)),
        t,
    )
    t = _REF_BIBLICA.sub(_ler_referencia, t)
    t = _REF_CAPITULO.sub(lambda m: f"{_LIVROS_BIBLIA[m.group(1)]}, capítulo {m.group(2)}", t)
    t = re.sub(r"\b([01]?\d|2[0-3])h([0-5]\d)\b", r"\1 e \2", t)  # 17h30 -> "17 e 30"
    t = re.sub(r"\b1h\b", "1 hora", t)
    t = re.sub(r"\b([01]?\d|2[0-3])h\b", r"\1 horas", t)
    t = re.sub(r"\bCIC\s?(\d)", r"Catecismo, número \1", t)
    t = re.sub(r"\bCIC\b", "Catecismo", t)
    t = re.sub(r"\b[nN][º°]\s?", "número ", t)
    t = re.sub(r"\b(10|[1-9])\s?º", lambda m: _ORDINAIS_FALA[int(m.group(1)) - 1], t)
    t = re.sub(r"(\d)\s?%", r"\1 por cento", t)
    t = re.sub(r"(\d)\s?[x×]\s?(\d)", r"\1 vezes \2", t)
    t = re.sub(r"\bJ\.A\.R\.V\.I\.S\.", "Jarvis", t)
    return re.sub(r"\s+", " ", t).strip()


# -----------------------------------------------------------------------------
#  Datas e horas faladas ("sexta às 8h", "amanhã", "dia 15", "25/12", "3 da tarde")
# -----------------------------------------------------------------------------
_DIAS_SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
_MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
          "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12, "jan": 1, "fev": 2, "mar": 3, "abr": 4,
          "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
_RE_DATA_NUM = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_RE_DIA_MES = re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(sorted(_MESES, key=len, reverse=True)) + r")\b")
_RE_DIA = re.compile(r"\bdia\s+(\d{1,2})\b")
_RE_HORA = re.compile(r"\b(\d{1,2})(?:\s*(?:h|:|horas?)\s*(\d{2})?|\s*h\b)(?:\s*min(?:utos)?)?")
_RE_PERIODO = re.compile(r"\b(\d{1,2})\s+(?:hora[s]?\s+)?da\s+(manha|tarde|noite|madrugada)\b")


def ler_data(texto: str, hoje: date | None = None) -> date | None:
    """Entende datas do jeito que a criança fala. Retorna None se não houver data."""
    hoje = hoje or date.today()
    t = normalizar(texto)
    if contem_frase(t, "depois de amanha"):
        return hoje + timedelta(days=2)
    if contem_frase(t, "amanha"):
        return hoje + timedelta(days=1)
    if contem_frase(t, "hoje"):
        return hoje
    if m := _RE_DATA_NUM.search(t):
        dia, mes = int(m.group(1)), int(m.group(2))
        ano = int(m.group(3)) if m.group(3) else hoje.year
        ano = ano + 2000 if ano < 100 else ano
        try:
            data = date(ano, mes, dia)
        except ValueError:
            return None
        return data.replace(year=data.year + 1) if not m.group(3) and data < hoje else data
    if m := _RE_DIA_MES.search(t):
        try:
            data = date(hoje.year, _MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
        return data.replace(year=data.year + 1) if data < hoje else data
    for nome, numero in _DIAS_SEMANA.items():
        if re.search(rf"\b{nome}(-feira| feira)?\b", t):
            dias = (numero - hoje.weekday()) % 7
            if re.search(r"\b(proxima|proximo|que vem)\b", t) and dias == 0:
                dias = 7
            return hoje + timedelta(days=dias)
    if m := _RE_DIA.search(t):
        dia = int(m.group(1))
        for mais in (0, 1):
            mes = (hoje.month - 1 + mais) % 12 + 1
            ano = hoje.year + (hoje.month - 1 + mais) // 12
            try:
                data = date(ano, mes, dia)
            except ValueError:
                continue
            if data >= hoje:
                return data
        return None
    if contem_frase(t, "semana que vem"):
        return hoje + timedelta(days=7)
    return None


def ler_hora(texto: str) -> str:
    """'8h', '8:30', 'às 15h', '3 da tarde', 'meio-dia' -> 'HH:MM' (ou '' se não houver hora)."""
    t = normalizar(texto).replace("meio-dia", "meio dia")
    if contem_frase(t, "meio dia"):
        return "12:00"
    if m := _RE_PERIODO.search(t):
        hora, periodo = int(m.group(1)), m.group(2)
        if periodo in ("tarde", "noite") and hora < 12:
            hora += 12
        return f"{hora % 24:02d}:00"
    sem_datas = _RE_DATA_NUM.sub(" ", t)
    for m in _RE_HORA.finditer(sem_datas):
        hora, minutos = int(m.group(1)), int(m.group(2) or 0)
        if hora <= 23 and minutos <= 59:
            return f"{hora:02d}:{minutos:02d}"
    if (m := re.search(r"\b(?:as|a)\s+(\d{1,2})\b", sem_datas)) and int(m.group(1)) <= 23:  # "às 7"
        return f"{int(m.group(1)):02d}:00"
    return ""


_NOMES_DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
_NOMES_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
                "novembro", "dezembro")


def data_por_extenso(dia: date, com_dia_semana: bool = True) -> str:
    """date(2026, 10, 26) -> 'segunda-feira, 26 de outubro'."""
    texto = f"{dia.day} de {_NOMES_MESES[dia.month - 1]}"
    return f"{_NOMES_DIAS[dia.weekday()]}, {texto}" if com_dia_semana else texto
