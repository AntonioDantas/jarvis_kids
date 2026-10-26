"""
Interface no terminal com visual de HUD futurista (biblioteca Rich).
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


def banner(versao: str) -> None:
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
    console.clear()


@contextmanager
def carregando(texto: str):
    with console.status(f"[#00d7ff]{texto}[/]", spinner="dots12", spinner_style="#00d7ff"):
        yield


def etapa(nome: str, ok: bool | None, detalhe: str = "") -> None:
    """Linha do 'boot': ✓ (ok), ⚠ (funcionando com reserva) ou ✗ (indisponível)."""
    simbolo, cor = {True: ("✓", "green"), None: ("⚠", "yellow"), False: ("✗", "red")}[ok]
    pontos = "." * max(2, 36 - len(nome))
    console.print(f"  [#00d7ff]◉[/] {nome} [grey35]{pontos}[/] [{cor}]{simbolo}[/] [grey62]{detalhe}[/]")


def barra(atual: int, total: int, largura: int = 18, cor: str = "#00d7ff") -> Text:
    fracao = 0 if total <= 0 else max(0.0, min(1.0, atual / total))
    cheio = int(round(fracao * largura))
    return Text.assemble(("█" * cheio, cor), ("░" * (largura - cheio), "grey30"))


def hud(nome: str, nivel: tuple, pontos: int, dias: int, saldo: str, missoes: list[dict], persona: str | None) -> None:
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
    itens = [("1", "🧠 Quiz"), ("2", "🙏 Oração"), ("3", "🔍 Exame"), ("4", "📖 Vozes"),
             ("5", "💰 Mesada"), ("6", "🏆 Conquistas"), ("7", "👪 Pais"), ("0", "⏻ Sair")]
    console.print(Columns([Text.assemble((f"[{chave}]", "bold #00d7ff"), (f" {nome}", "grey85")) for chave, nome in itens],
                          padding=(0, 2)), style="")
    console.print("  [grey50]…ou simplesmente converse comigo! Fale (ENTER) ou digite sua pergunta.[/]")


def fala(texto: str, titulo: str = "J.A.R.V.I.S.", cor: str = CORES["jarvis"]) -> None:
    console.print(Panel(Text(texto), title=f"[bold {cor}]◈ {titulo}[/]", title_align="left",
                        border_style=cor, box=ROUNDED, padding=(0, 1)))


def crianca_disse(nome: str, texto: str) -> None:
    console.print(f"  [bold {CORES['crianca']}]🗣️  {nome}:[/] {texto}")


class PainelAoVivo:
    """Painel que vai sendo preenchido enquanto o Jarvis responde."""

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


def menu(titulo: str, opcoes: list[str], cor: str = CORES["jarvis"]) -> None:
    tabela = Table.grid(padding=(0, 2))
    tabela.add_column(style=f"bold {cor}", justify="right")
    tabela.add_column()
    for i, opcao in enumerate(opcoes, 1):
        tabela.add_row(f"[{i}]", opcao)
    tabela.add_row("[0]", "[grey62]↩ Voltar[/]")
    console.print(Panel(tabela, title=f"[bold {cor}]{titulo}[/]", border_style=cor, box=ROUNDED, expand=False))


def tabela(titulo: str, colunas: list[str], linhas: list[list], cor: str = CORES["jarvis"]) -> None:
    t = Table(title=f"[bold {cor}]{titulo}[/]", box=ROUNDED, border_style=cor, header_style=f"bold {cor}")
    for coluna in colunas:
        t.add_column(coluna)
    for linha in linhas:
        t.add_row(*[c if isinstance(c, Text) else str(c) for c in linha])
    console.print(t)


def aviso(texto: str) -> None:
    console.print(f"  [yellow]⚠ {texto}[/]")


def erro(texto: str) -> None:
    console.print(f"  [bold red]✗ {texto}[/]")


def info(texto: str) -> None:
    console.print(f"  [grey62]{texto}[/]")


def entrada(rotulo: str) -> str:
    return console.input(f"\n[bold #00d7ff]{rotulo}[/] [grey50]›[/] ")
