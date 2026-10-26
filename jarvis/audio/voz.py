"""
Boca do Jarvis: Text-to-Speech com vários motores e queda automática.

  * Kokoro-82M  — voz neural 100% local em português do Brasil (padrão)
  * Sistema     — voz do próprio sistema operacional (macOS "say", SAPI no
                  Windows, eSpeak no Linux): offline e funciona em qualquer PC
  * Edge-TTS    — vozes da Microsoft; OPCIONAL, precisa de internet e envia
                  o texto para a Microsoft (desligado por padrão)
  * Mudo        — só texto na tela

O ``FluxoFala`` sintetiza a frase seguinte enquanto a anterior está tocando:
o Jarvis começa a falar antes de a IA terminar de pensar.
"""

from __future__ import annotations

import io
import queue
import re
import shutil
import subprocess
import sys
import threading
import warnings

import numpy as np

from jarvis.audio.efeitos import AltoFalante
from jarvis.texto import preparar_para_fala

VOZES_PT_BR = ("pm_alex", "pm_santa", "pf_dora")


class MotorVoz:
    nome = "mudo"
    gera_audio = False  # True: sintetizar() devolve áudio; False: falar() fala direto

    def sintetizar(self, texto: str, voz: dict) -> tuple[np.ndarray, int] | None:
        return None

    def falar(self, texto: str, voz: dict) -> None:
        return None


class VozKokoro(MotorVoz):
    nome = "Kokoro-82M (neural, local)"
    gera_audio = True

    def __init__(self, voz_padrao: str, velocidade: float):
        warnings.filterwarnings("ignore", category=UserWarning, module="torch")
        warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
        import torch
        from kokoro import KPipeline

        dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipeline = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M", device=dispositivo)
        self.voz_padrao, self.velocidade = voz_padrao, velocidade
        for voz in VOZES_PT_BR:  # baixa todas as vozes já (os santos usam outras), para depois funcionar offline
            try:
                self.pipeline.load_voice(voz)
            except Exception:
                pass
        self.sintetizar("Olá.", {})  # aquece o modelo

    def sintetizar(self, texto: str, voz: dict) -> tuple[np.ndarray, int] | None:
        partes = []
        for _grafemas, _fonemas, audio in self.pipeline(
            texto, voice=voz.get("kokoro", self.voz_padrao), speed=voz.get("velocidade", self.velocidade)
        ):
            if audio is not None:
                partes.append(audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio))
        return (np.concatenate(partes).astype(np.float32), 24_000) if partes else None


class VozEdge(MotorVoz):
    nome = "Edge-TTS (online, Microsoft)"
    gera_audio = True

    def __init__(self, voz_padrao: str, velocidade: float):
        import edge_tts  # noqa: F401
        import soundfile  # noqa: F401  (decodifica o MP3)

        self.voz_padrao, self.velocidade = voz_padrao, velocidade
        if self.sintetizar("Olá.", {}) is None:
            raise RuntimeError("Edge-TTS não respondeu (sem internet?)")

    def sintetizar(self, texto: str, voz: dict) -> tuple[np.ndarray, int] | None:
        import asyncio

        import edge_tts
        import soundfile as sf

        taxa = f"{round((voz.get('velocidade', self.velocidade) - 1) * 100):+d}%"

        async def baixar() -> bytes:
            dados = b""
            comunicador = edge_tts.Communicate(texto, voz.get("edge", self.voz_padrao), rate=taxa)
            async for pedaco in comunicador.stream():
                if pedaco["type"] == "audio":
                    dados += pedaco["data"]
            return dados

        try:
            mp3 = asyncio.run(baixar())
            audio, taxa_amostra = sf.read(io.BytesIO(mp3), dtype="float32")
        except Exception:
            return None
        return (audio if audio.ndim == 1 else audio.mean(axis=1)), taxa_amostra


class VozSistema(MotorVoz):
    """Voz nativa do sistema operacional, rodando numa thread dedicada."""

    nome = "voz do sistema (offline)"

    def __init__(self, velocidade: float):
        self.velocidade = velocidade
        self._mac_voz = self._voz_mac() if sys.platform == "darwin" else None
        if self._mac_voz is not None:
            self.nome = f"voz do macOS ({self._mac_voz or 'padrão'})"
            return
        self._fila: queue.Queue = queue.Queue()
        pronto, self._erro = threading.Event(), None
        threading.Thread(target=self._servico_pyttsx3, args=(pronto,), daemon=True).start()
        pronto.wait(15)
        if self._erro or not pronto.is_set():
            raise RuntimeError(f"voz do sistema indisponível: {self._erro}")

    @staticmethod
    def _voz_mac() -> str | None:
        if not shutil.which("say"):
            return None
        saida = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
        for linha in saida.splitlines():
            if "pt_BR" in linha:
                return re.split(r"\s{2,}", linha.strip())[0]
        return ""

    def _servico_pyttsx3(self, pronto: threading.Event) -> None:
        try:
            if sys.platform == "win32":
                try:
                    import comtypes

                    comtypes.CoInitialize()
                except Exception:
                    pass
            import pyttsx3

            motor = pyttsx3.init()
            for v in motor.getProperty("voices"):
                descricao = f"{v.id} {v.name} {getattr(v, 'languages', '')}".lower()
                if any(chave in descricao for chave in ("pt-br", "pt_br", "brazil", "portugu", "maria", "daniel")):
                    motor.setProperty("voice", v.id)
                    break
            motor.setProperty("rate", int(175 * self.velocidade))
        except Exception as exc:
            self._erro = exc
            pronto.set()
            return
        pronto.set()
        while True:
            texto, feito = self._fila.get()
            try:
                motor.say(texto)
                motor.runAndWait()
            except Exception:
                pass
            feito.set()

    def falar(self, texto: str, voz: dict) -> None:
        if self._mac_voz is not None:
            comando = ["say", "-r", str(int(185 * voz.get("velocidade", self.velocidade)))]
            if self._mac_voz:
                comando += ["-v", self._mac_voz]
            subprocess.run(comando + [texto], check=False)
            return
        feito = threading.Event()
        self._fila.put((texto, feito))
        feito.wait(60)


class FluxoFala:
    """Fala frases à medida que chegam: sintetiza a próxima enquanto toca a atual."""

    def __init__(self, motor: MotorVoz, alto_falante: AltoFalante, voz: dict):
        self.motor, self.alto_falante, self.voz = motor, alto_falante, voz
        self._textos: queue.Queue = queue.Queue()
        self._audios: queue.Queue = queue.Queue(maxsize=3)
        self._cancelado = threading.Event()
        self._threads = [threading.Thread(target=self._sintetizador, daemon=True)]
        if motor.gera_audio:
            self._threads.append(threading.Thread(target=self._reprodutor, daemon=True))
        for t in self._threads:
            t.start()

    def adicionar(self, frase: str) -> None:
        texto = preparar_para_fala(frase)
        if texto:
            self._textos.put(texto)

    def finalizar(self) -> None:
        """Espera terminar de falar tudo."""
        self._textos.put(None)
        for t in self._threads:
            while t.is_alive():
                t.join(0.2)  # join com timeout deixa o Ctrl+C funcionar

    def cancelar(self) -> None:
        self._cancelado.set()
        self.alto_falante.parar()
        self._textos.put(None)

    def _entregar(self, item) -> None:
        while not self._cancelado.is_set():
            try:
                self._audios.put(item, timeout=0.2)
                return
            except queue.Full:
                continue

    def _sintetizador(self) -> None:
        while True:
            texto = self._textos.get()
            if texto is None or self._cancelado.is_set():
                if self.motor.gera_audio:
                    self._entregar(None)
                return
            if self.motor.gera_audio:
                try:
                    resultado = self.motor.sintetizar(texto, self.voz)
                except Exception:
                    resultado = None
                if resultado is not None:
                    self._entregar(resultado)
            else:
                self.motor.falar(texto, self.voz)

    def _reprodutor(self) -> None:
        while True:
            item = self._audios.get()
            if item is None or self._cancelado.is_set():
                return
            self.alto_falante.tocar(*item)


class Voz:
    """Escolhe o melhor motor disponível, com quedas automáticas."""

    def __init__(self, preferido: str, voz_kokoro: str, voz_edge: str, velocidade: float, alto_falante: AltoFalante):
        self.alto_falante = alto_falante
        self.avisos: list[str] = []
        ordem = {
            "auto": ["kokoro", "sistema"],
            "kokoro": ["kokoro", "sistema"],
            "edge": ["edge", "kokoro", "sistema"],
            "sistema": ["sistema"],
            "mudo": [],
        }.get(preferido, ["kokoro", "sistema"])
        self.motor: MotorVoz = MotorVoz()
        if not alto_falante.disponivel:
            ordem = []
            self.avisos.append(f"sem alto-falante ({alto_falante.erro[:60]})")
        construtores = {
            "kokoro": lambda: VozKokoro(voz_kokoro, velocidade),
            "edge": lambda: VozEdge(voz_edge, velocidade),
            "sistema": lambda: VozSistema(velocidade),
        }
        for nome in ordem:
            try:
                self.motor = construtores[nome]()
                break
            except Exception as exc:
                self.avisos.append(f"{nome}: {str(exc)[:80]}")

    @property
    def descricao(self) -> str:
        return self.motor.nome

    @property
    def ativa(self) -> bool:
        return type(self.motor) is not MotorVoz

    def iniciar_fluxo(self, voz: dict | None = None) -> FluxoFala:
        return FluxoFala(self.motor, self.alto_falante, voz or {})

    def falar(self, texto: str, voz: dict | None = None) -> None:
        fluxo = self.iniciar_fluxo(voz)
        fluxo.adicionar(texto)
        fluxo.finalizar()
