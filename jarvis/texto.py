"""
Utilidades de texto em português: normalização, radicais (para busca e
comandos de voz), divisão em frases, valores em dinheiro e limpeza para TTS.
"""

from __future__ import annotations

import re
import unicodedata

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
    t = re.sub(r"\bCIC\s?(\d)", r"Catecismo, número \1", t)
    t = re.sub(r"\bCIC\b", "Catecismo", t)
    t = re.sub(r"\b[nN][º°]\s?", "número ", t)
    t = re.sub(r"\b(10|[1-9])\s?º", lambda m: _ORDINAIS_FALA[int(m.group(1)) - 1], t)
    t = re.sub(r"(\d)\s?%", r"\1 por cento", t)
    t = re.sub(r"(\d)\s?[x×]\s?(\d)", r"\1 vezes \2", t)
    t = re.sub(r"\bJ\.A\.R\.V\.I\.S\.", "Jarvis", t)
    return re.sub(r"\s+", " ", t).strip()
