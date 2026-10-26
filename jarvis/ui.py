"""
Camada de tela do Jarvis.

Todos os módulos desenham por aqui, com funções "semânticas" (fala, painel, tabela, menu,
evento, entrada...). Por padrão elas desenham no terminal (biblioteca Rich). Quando a
interface gráfica futurista está ligada (``usar_tela(TelaWeb)``), as mesmas chamadas viram
eventos para a janela do Jarvis — os módulos não precisam saber qual tela está em uso.
"""

from __future__ import annotations

from contextlib import contextmanager

from rich.align import Align
from rich.box import HEAVY, ROUNDED
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(highlight=False, emoji=True)

_LETRAS = {
    "J": ["     ██╗", "     ██║", "     ██║", "██   ██║", "╚█████╔╝", " ╚════╝ "],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "R": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝"],
    "V": ["██╗   ██╗", "██║   ██║", "██║   ██║", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚═══╝  "],
    "I": ["██╗", "██║", "██║", "██║", "██║", "╚═╝"],
    "S": ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
}
_GRADIENTE = ["#00e5ff", "#00c8ff", "#00a8ff", "#3d8bff", "#6a6bff", "#9b4dff"]

CORES = {"jarvis": "#00d7ff", "crianca": "#ffd75f", "santo": "#ffaf5f", "fe": "#d7afff",
         "dinheiro": "#87ff87", "alerta": "#ff5f5f", "suave": "grey62"}

_tela = None  # TelaWeb quando a interface gráfica está ligada


def usar_tela(tela) -> None:
    global _tela
    _tela = tela


def web_ativa() -> bool:
    return _tela is not None


def texto_simples(valor) -> str:
    """Converte textos com marcação do Rich ('[grey50]...[/]') ou objetos Text em texto puro."""
    if isinstance(valor, Text):
        return valor.plain
    try:
        return Text.from_markup(str(valor)).plain
    except Exception:
        return str(valor)


def banner(versao: str) -> None:
    if _tela:
        return _tela.banner(versao)
    linhas = Text()
    for i in range(6):
        linhas.append(" ".join(_LETRAS[c][i] for c in "JARVIS") + "\n", style=f"bold {_GRADIENTE[i]}")
    subtitulo = Text.assemble(
        ("K I D S", "bold #ffd75f"), ("  ·  ", "grey50"),
        ("Jovem Assistente de Raciocínio, Virtudes, Inteligência e Sabedoria", "italic #87d7ff"),
    )
    rodape = Text(f"v{versao} · 100% local · privacidade total · open-source", style="grey50")
    console.print(Panel(Group(Align.center(linhas), Align.center(subtitulo), Align.center(rodape)),
                        box=HEAVY, border_style="#00afff", padding=(1, 2)))


def limpar() -> None:
    if _tela:
        return _tela.limpar()
    console.clear()


@contextmanager
def carregando(texto: str):
    if _tela:
        with _tela.carregando(texto):
            yield
        return
    with console.status(f"[#00d7ff]{texto}[/]", spinner="dots12", spinner_style="#00d7ff"):
        yield


def etapa(nome: str, ok: bool | None, detalhe: str = "") -> None:
    """Linha do 'boot': ✓ (ok), ⚠ (funcionando com reserva) ou ✗ (indisponível)."""
    if _tela:
        return _tela.etapa(nome, ok, detalhe)
    simbolo, cor = {True: ("✓", "green"), None: ("⚠", "yellow"), False: ("✗", "red")}[ok]
    pontos = "." * max(2, 36 - len(nome))
    console.print(f"  [#00d7ff]◉[/] {nome} [grey35]{pontos}[/] [{cor}]{simbolo}[/] [grey62]{detalhe}[/]")


def barra(atual: int, total: int, largura: int = 18, cor: str = "#00d7ff") -> Text:
    fracao = 0 if total <= 0 else max(0.0, min(1.0, atual / total))
    cheio = int(round(fracao * largura))
    return Text.assemble(("█" * cheio, cor), ("░" * (largura - cheio), "grey30"))


def hud(nome: str, nivel: tuple, pontos: int, dias: int, saldo: str, missoes: list[dict], persona: str | None) -> None:
    if _tela:
        return _tela.hud(nome, nivel, pontos, dias, saldo, missoes, persona)
    _indice, nome_nivel, emoji, minimo, proximo = nivel
    progresso = barra(pontos - minimo, (proximo - minimo) if proximo else 1)
    xp = f"{pontos}/{proximo}" if proximo else f"{pontos} (nível máximo!)"
    feitas = sum(1 for m in missoes if m["concluida"])
    tabela = Table.grid(expand=True, padding=(0, 2))
    for _ in range(4):
        tabela.add_column(justify="center")
    tabela.add_row(
        Text.assemble(("👤 ", ""), (nome, "bold #ffd75f")),
        Text.assemble((f"{emoji} ", ""), (nome_nivel, "bold #d7afff")),
        Text.assemble(("🔥 ", ""), (f"{dias} dia{'s' if dias != 1 else ''}", "bold #ff875f")),
        Text.assemble(("💰 ", ""), (saldo, "bold #87ff87")),
    )
    tabela.add_row(
        Text.assemble(("Sabedoria ", "grey62"), progresso, (f" {xp}", "grey62")),
        "",
        Text.assemble(("🎯 Missões ", "grey62"), (f"{feitas}/{len(missoes)}", "bold")),
        Text(f"🎭 {persona}", style="#ffaf5f") if persona else Text("🤖 modo Jarvis", style="grey62"),
    )
    console.print(Panel(tabela, box=ROUNDED, border_style="#005f87", title="[bold #00d7ff]◢ PAINEL DO AGENTE ◣[/]"))


def comandos_rapidos() -> None:
    if _tela:
        return _tela.comandos_rapidos()
    itens = [("1", "🧠 Quiz"), ("2", "🙏 Oração"), ("3", "🔍 Exame"), ("4", "📖 Vozes"),
             ("5", "💰 Mesada"), ("6", "🏆 Conquistas"), ("7", "👪 Pais"), ("8", "📿 Terço"), ("9", "📅 Calendário"),
             ("0", "⏻ Sair")]
    console.print(Columns([Text.assemble((f"[{chave}]", "bold #00d7ff"), (f" {nome}", "grey85")) for chave, nome in itens],
                          padding=(0, 2)), style="")
    console.print("  [grey50]Também: [bold #00d7ff]agenda[/] 📅 · [bold #00d7ff]mudar a voz[/] 🗣️ · "
                  "[bold #00d7ff]ajuda[/] ❔  …ou simplesmente converse comigo! Fale (ENTER) ou digite.[/]")


def fala(texto: str, titulo: str = "J.A.R.V.I.S.", cor: str = CORES["jarvis"]) -> None:
    if _tela:
        return _tela.fala(texto, titulo, cor)
    console.print(Panel(Text(texto), title=f"[bold {cor}]◈ {titulo}[/]", title_align="left",
                        border_style=cor, box=ROUNDED, padding=(0, 1)))


def crianca_disse(nome: str, texto: str) -> None:
    if _tela:
        return _tela.crianca_disse(nome, texto)
    console.print(f"  [bold {CORES['crianca']}]🗣️  {nome}:[/] {texto}")


class PainelAoVivo:
    """Painel que vai sendo preenchido enquanto o Jarvis responde."""

    def __new__(cls, titulo: str, cor: str):
        if _tela:
            return _tela.painel_ao_vivo(titulo, cor)
        return super().__new__(cls)

    def __init__(self, titulo: str, cor: str):
        self.titulo, self.cor, self.texto = titulo, cor, ""
        self._live = Live(self._render(True), console=console, refresh_per_second=12, transient=False)

    def _render(self, pensando: bool) -> Panel:
        corpo = Text(self.texto)
        if pensando:
            corpo.append(" ▌" if self.texto else "⚡ processando…", style=f"blink {self.cor}")
        return Panel(corpo, title=f"[bold {self.cor}]◈ {self.titulo}[/]", title_align="left",
                     border_style=self.cor, box=ROUNDED, padding=(0, 1))

    def __enter__(self) -> PainelAoVivo:
        self._live.__enter__()
        return self

    def acrescentar(self, frase: str) -> None:
        self.texto = f"{self.texto} {frase}".strip()
        self._live.update(self._render(True))

    def __exit__(self, *exc) -> None:
        self._live.update(self._render(False))
        self._live.__exit__(*exc)
        if not console.is_terminal:
            console.print()  # fora de um terminal (ex.: testes), o Live não quebra a linha


def evento(tipo: str, texto: str, detalhe: str = "") -> None:
    if _tela:
        return _tela.evento(tipo, texto, detalhe)
    if tipo in ("nivel", "missoes"):
        console.print(Panel(Align.center(Text(texto, style="bold #ffd75f")), box=HEAVY,
                            border_style="#d75fff", subtitle="[#d75fff]★ ★ ★[/]"))
    elif tipo == "medalha":
        console.print(Panel(Align.center(Text.assemble((texto, "bold #ffd700"), (f"\n{detalhe}", "grey70"))),
                            box=ROUNDED, border_style="#ffd700"))
    elif tipo == "missao":
        console.print(f"  [bold #5fffaf]{texto}[/]")
    else:
        console.print(f"  [bold #87ff87]✦ {texto}[/]")


def menu(titulo: str, opcoes: list[str], cor: str = CORES["jarvis"], pergunta: str = "") -> None:
    if _tela:
        return _tela.menu(titulo, opcoes, cor, pergunta)
    tabela = Table.grid(padding=(0, 2))
    tabela.add_column(style=f"bold {cor}", justify="right")
    tabela.add_column()
    for i, opcao in enumerate(opcoes, 1):
        tabela.add_row(f"[{i}]", opcao)
    tabela.add_row("[0]", "[grey62]↩ Voltar[/]")
    console.print(Panel(tabela, title=f"[bold {cor}]{titulo}[/]", border_style=cor, box=ROUNDED, expand=False))


def tabela(titulo: str, colunas: list[str], linhas: list[list], cor: str = CORES["jarvis"]) -> None:
    if _tela:
        return _tela.tabela(titulo, colunas, linhas, cor)
    t = Table(title=f"[bold {cor}]{titulo}[/]", box=ROUNDED, border_style=cor, header_style=f"bold {cor}")
    for coluna in colunas:
        t.add_column(coluna)
    for linha in linhas:
        t.add_row(*[c if isinstance(c, Text) else str(c) for c in linha])
    console.print(t)


def aviso(texto: str) -> None:
    if _tela:
        return _tela.aviso(texto)
    console.print(f"  [yellow]⚠ {texto}[/]")


def erro(texto: str) -> None:
    if _tela:
        return _tela.erro(texto)
    console.print(f"  [bold red]✗ {texto}[/]")


def info(texto: str) -> None:
    if _tela:
        return _tela.info(texto)
    console.print(f"  [grey62]{texto}[/]")


def entrada(rotulo: str, tipo: str = "texto", opcoes: list[str] | None = None) -> str:
    """
    Lê uma resposta. ``tipo`` diz à interface gráfica qual controle mostrar:
    principal, texto, escolha, quiz, sim_nao, valor, numero, pin, continuar.
    Resposta vazia = "quero falar" (a interação liga o microfone).
    """
    if _tela:
        return _tela.entrada(rotulo, tipo, opcoes)
    if tipo == "pin":
        return console.input(f"[bold #ff87d7]{rotulo}[/] › ", password=True)
    return console.input(f"\n[bold #00d7ff]{rotulo}[/] [grey50]›[/] ")


# -----------------------------------------------------------------------------
#  Elementos usados pelos módulos de fé, quiz e mesada
# -----------------------------------------------------------------------------
def painel(titulo: str, texto: str, cor: str = CORES["jarvis"], subtitulo: str = "", destaque: str = "") -> None:
    """Cartão com título, texto e uma linha de destaque opcional (ex.: 'Fruto do mistério: fé')."""
    if _tela:
        return _tela.painel(titulo, texto, cor, subtitulo, destaque)
    corpo = Text(texto, style="#eeeeee")
    if destaque:
        corpo.append(f"\n\n✦ {destaque}", style="bold #ffd75f")
    console.print(Panel(corpo, title=f"[bold {cor}]{titulo}[/]", subtitle=f"[grey50]{subtitulo}[/]" if subtitulo else None,
                        border_style=cor))


def linha_oracao(texto: str) -> None:
    """Uma linha de oração sendo rezada agora (a interface destaca, como karaokê)."""
    if _tela:
        return _tela.linha_oracao(texto)
    console.print(f"  [bold {CORES['fe']}]✝[/] [italic]{texto}[/]")


def contas(atual: int, total: int) -> None:
    """Contas do terço acendendo uma a uma."""
    if _tela:
        return _tela.contas(atual, total)
    console.print(Text.assemble(("  📿 ", ""), ("●" * atual, "bold #d7afff"), ("○" * (total - atual), "grey42"),
                                (f"  {atual}/{total}", "grey62")))


def pergunta_quiz(numero: int, total: int, pergunta: str, opcoes: list[str], rodape: str) -> None:
    if _tela:
        return _tela.pergunta_quiz(numero, total, pergunta, opcoes, rodape)
    texto = Text(pergunta + "\n\n", style="bold")
    for letra, opcao in zip("ABCD", opcoes, strict=False):
        texto.append(f"  {letra}) ", style="bold #00d7ff")
        texto.append(opcao + "\n")
    console.print(Panel(texto, title=f"[bold #00d7ff]Pergunta {numero}/{total}[/]", subtitle=f"[grey50]{rodape}[/]",
                        border_style="#00d7ff"))


def resultado(correto: bool, texto: str, detalhe: str = "") -> None:
    if _tela:
        return _tela.resultado(correto, texto, detalhe)
    cor = "bold green" if correto else "bold red"
    console.print(f"  [{cor}]{'✔' if correto else '✘'} {texto}[/]  [grey62]{detalhe}[/]")


def sucesso(texto: str) -> None:
    if _tela:
        return _tela.sucesso(texto)
    console.print(f"  [bold green]✓ {texto}[/]")


def estado(nome: str) -> None:
    """Estado do Jarvis para as animações: ocioso, ouvindo, pensando, falando."""
    if _tela:
        _tela.estado(nome)


def nivel_microfone(valor: float) -> None:
    """Volume da voz da criança (0 a 1) enquanto ela fala: faz o núcleo do Jarvis pulsar."""
    if _tela:
        _tela.nivel_microfone(valor)


def progresso(texto: str, feito: int, total: int) -> None:
    if _tela:
        _tela.progresso(texto, feito, total)


def agenda(itens: list, titulo: str = "📅 AGENDA") -> None:
    if _tela:
        return _tela.agenda(itens, titulo)
    console.print(f"\n  [bold #ffd75f]{titulo}[/]")
    if not itens:
        console.print("  [grey62]Nada marcado.[/]")
        return
    for item in itens:
        hora = item.hora or "—"
        console.print(f"  [bold #00d7ff]{hora:>5}[/]  {item.emoji} {item.titulo}")


def lateral(dados: dict) -> None:
    """Painel da direita da janela (liturgia do dia, agenda, contagem regressiva). Não existe no terminal."""
    if _tela:
        _tela.atualizar_lateral(dados)


def abrir_planner() -> bool:
    """Na interface gráfica abre o calendário completo. Retorna False no terminal."""
    return bool(_tela and _tela.abrir_planner())
