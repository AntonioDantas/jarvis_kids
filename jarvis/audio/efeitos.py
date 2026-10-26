"""
Alto-falante e efeitos sonoros futuristas.

Os efeitos (bip de ativação, bop de fim de escuta, moeda, nível, medalha...)
são GERADOS POR CÓDIGO com numpy: o repositório não precisa de nenhum arquivo
de áudio e tudo funciona offline.
"""

from __future__ import annotations

import threading

import numpy as np

TAXA_EFEITOS = 44_100


def reamostrar(audio: np.ndarray, taxa_origem: int, taxa_destino: int) -> np.ndarray:
    """Reamostragem linear simples (suficiente para voz e efeitos)."""
    if taxa_origem == taxa_destino or audio.size == 0:
        return audio.astype(np.float32)
    n = int(round(audio.size * taxa_destino / taxa_origem))
    x_novo = np.linspace(0, audio.size, n, endpoint=False)
    return np.interp(x_novo, np.arange(audio.size), audio).astype(np.float32)


class AltoFalante:
    """Toca áudio com segurança entre threads (voz e efeitos não se atropelam)."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self.erro = ""
        try:
            import sounddevice as sd

            sd.query_devices(kind="output")
            self._sd = sd
        except Exception as exc:  # sem PortAudio, sem caixa de som, etc.
            self._sd = None
            self.erro = str(exc)

    @property
    def disponivel(self) -> bool:
        return self._sd is not None

    def tocar(self, audio: np.ndarray, taxa: int) -> None:
        if self._sd is None or audio is None or len(audio) == 0:
            return
        audio = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
        with self._trava:
            try:
                self._sd.play(audio, taxa)
                self._sd.wait()
            except Exception:
                # Algumas placas de som só aceitam 44,1/48 kHz
                try:
                    self._sd.play(reamostrar(audio, taxa, 48_000), 48_000)
                    self._sd.wait()
                except Exception as exc:
                    self.erro = str(exc)

    def parar(self) -> None:
        if self._sd is not None:
            try:
                self._sd.stop()
            except Exception:
                pass


# -----------------------------------------------------------------------------
#  Sintetizador de efeitos
# -----------------------------------------------------------------------------
def _tom(f_ini: float, f_fim: float, duracao: float, forma: str = "seno", volume: float = 0.25) -> np.ndarray:
    n = int(TAXA_EFEITOS * duracao)
    freq = np.linspace(f_ini, f_fim, n)
    fase = 2 * np.pi * np.cumsum(freq) / TAXA_EFEITOS
    if forma == "quadrada":
        onda = np.sign(np.sin(fase)) * 0.45
    elif forma == "triangulo":
        onda = 2 / np.pi * np.arcsin(np.sin(fase))
    else:
        onda = np.sin(fase) + 0.25 * np.sin(2 * fase)  # um harmônico deixa o som mais "digital"
    ataque = min(n, int(0.004 * TAXA_EFEITOS))
    envelope = np.ones(n)
    envelope[:ataque] = np.linspace(0, 1, ataque)
    envelope *= np.exp(-np.linspace(0, 3.0, n))  # decaimento suave
    return (onda * envelope * volume).astype(np.float32)


def _juntar(*partes: np.ndarray, pausa: float = 0.0) -> np.ndarray:
    silencio = np.zeros(int(TAXA_EFEITOS * pausa), dtype=np.float32)
    saida = []
    for parte in partes:
        saida += [parte, silencio]
    return np.concatenate(saida[:-1]) if saida else silencio


def _misturar(*partes: np.ndarray) -> np.ndarray:
    tamanho = max(p.size for p in partes)
    saida = np.zeros(tamanho, dtype=np.float32)
    for p in partes:
        saida[: p.size] += p
    return saida / max(1.0, float(np.abs(saida).max()) / 0.6)


def _criar_sons() -> dict[str, np.ndarray]:
    notas = {"do": 523.25, "mi": 659.25, "sol": 783.99, "do2": 1046.5, "mi2": 1318.5, "si": 987.77}
    return {
        # bip ascendente: "estou ouvindo"
        "ativar": _juntar(_tom(700, 1500, 0.07), _tom(1500, 1900, 0.06), pausa=0.01),
        # bop descendente: "terminei de ouvir, processando"
        "ouvido": _tom(1300, 650, 0.11, "triangulo"),
        "pensando": _juntar(_tom(900, 900, 0.03, volume=0.12), _tom(1200, 1200, 0.03, volume=0.12), pausa=0.04),
        "moeda": _juntar(_tom(notas["si"], notas["si"], 0.07, "quadrada", 0.15),
                         _tom(notas["mi2"], notas["mi2"], 0.28, "quadrada", 0.15)),
        "missao": _juntar(_tom(notas["sol"], notas["sol"], 0.09), _tom(notas["do2"], notas["do2"], 0.22), pausa=0.02),
        "medalha": _juntar(*[_tom(f, f * 1.01, 0.06, volume=0.18) for f in (1568, 1760, 2093, 2637)], pausa=0.01),
        "nivel": _juntar(
            *[_tom(notas[n], notas[n], 0.11, "quadrada", 0.14) for n in ("do", "mi", "sol", "do2")],
            _misturar(*[_tom(notas[n], notas[n], 0.55, "seno", 0.2) for n in ("do", "mi", "sol", "do2")]),
            pausa=0.015,
        ),
        "erro": _juntar(_tom(240, 200, 0.12, "quadrada", 0.12), _tom(200, 160, 0.16, "quadrada", 0.12), pausa=0.03),
        "inicializar": _juntar(_tom(220, 880, 0.35, volume=0.18), _tom(880, 1760, 0.12, volume=0.14),
                               _misturar(_tom(440, 440, 0.4, volume=0.15), _tom(660, 660, 0.4, volume=0.12))),
        "desligar": _juntar(_tom(1200, 300, 0.45, volume=0.18), _tom(300, 120, 0.25, volume=0.12)),
    }


class Efeitos:
    def __init__(self, alto_falante: AltoFalante, ativo: bool = True):
        self.alto_falante = alto_falante
        self.ativo = ativo and alto_falante.disponivel
        self._sons = _criar_sons() if self.ativo else {}

    def tocar(self, nome: str) -> None:
        if self.ativo and nome in self._sons:
            self.alto_falante.tocar(self._sons[nome], TAXA_EFEITOS)
