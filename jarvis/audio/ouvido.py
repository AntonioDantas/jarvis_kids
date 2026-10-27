"""
Ouvido do Jarvis: microfone + VAD + Speech-to-Text (faster-whisper), 100% local.

Fluxo: o microfone entrega quadros de 32 ms -> o Silero VAD diz se há fala ->
quando a criança para de falar (silêncio de ~0,9 s), o trecho gravado vai
inteiro para o Whisper, que devolve o texto.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from collections.abc import Callable

import numpy as np

from jarvis.audio.efeitos import reamostrar
from jarvis.audio.vad import TAMANHO_QUADRO, TAXA_VAD, SensorVoz
from jarvis.texto import normalizar

MS_POR_QUADRO = TAMANHO_QUADRO * 1000 / TAXA_VAD  # 32 ms

# Frases que o Whisper costuma "inventar" quando só há ruído
ALUCINACOES = (
    "amara.org", "legendas pela comunidade", "legendado por", "obrigado por assistir",
    "obrigada por assistir", "inscreva-se", "inscreva se no canal", "ate o proximo video",
    "transcricao e legendas", "sous-titres", "subtitles by",
    "conversa em portugues do brasil com o jarvis",  # eco do initial_prompt
)


class Microfone:
    def __init__(self, sensor: SensorVoz):
        import sounddevice as sd

        self._sd = sd
        self.sensor = sensor
        dispositivo = sd.query_devices(kind="input")  # erro aqui = sem microfone
        self.nome = dispositivo["name"]
        try:
            sd.check_input_settings(samplerate=TAXA_VAD, channels=1, dtype="float32")
            self.taxa = TAXA_VAD
        except Exception:  # alguns microfones não gravam em 16 kHz
            self.taxa = int(dispositivo["default_samplerate"])

    def gravar_frase(
        self,
        espera_max_s: float | None = 8.0,
        duracao_max_s: float = 20.0,
        silencio_fim_ms: int = 900,
        limiar_inicio: float = 0.5,
        limiar_fim: float = 0.35,
        ao_detectar_fala: Callable[[], None] | None = None,
        ao_nivel: Callable[[float], None] | None = None,
        cancelar: threading.Event | None = None,
    ) -> np.ndarray | None:
        """
        Espera a criança começar a falar e devolve o áudio (16 kHz, mono) quando ela termina.
        Retorna None se ninguém falar dentro de ``espera_max_s`` (None = espera para sempre) ou se
        ``cancelar`` for acionado (ex.: a criança tocou num botão da janela em vez de falar).
        """
        fila: queue.Queue = queue.Queue()
        pre_fala: deque = deque(maxlen=int(300 / MS_POR_QUADRO))  # 300 ms antes da fala
        fala: list[np.ndarray] = []
        falando, seguidos, silencio, quadros_lidos = False, 0, 0, 0
        sobra = np.zeros(0, dtype=np.float32)
        inicio = time.monotonic()
        self.sensor.reiniciar()

        def callback(indata, _frames, _tempo, _status):
            fila.put(indata[:, 0].copy())

        bloco = TAMANHO_QUADRO if self.taxa == TAXA_VAD else int(self.taxa * MS_POR_QUADRO / 1000)
        with self._sd.InputStream(samplerate=self.taxa, channels=1, dtype="float32",
                                  blocksize=bloco, callback=callback):
            while True:
                if cancelar is not None and cancelar.is_set():
                    return None
                try:
                    pedaco = fila.get(timeout=0.25)
                except queue.Empty:
                    pedaco = None
                if pedaco is not None:
                    if self.taxa != TAXA_VAD:
                        pedaco = reamostrar(pedaco, self.taxa, TAXA_VAD)
                    sobra = np.concatenate([sobra, pedaco])
                    while sobra.size >= TAMANHO_QUADRO:
                        quadro, sobra = sobra[:TAMANHO_QUADRO], sobra[TAMANHO_QUADRO:]
                        prob = self.sensor.probabilidade(quadro)
                        quadros_lidos += 1
                        if ao_nivel and quadros_lidos % 3 == 0:  # ~10 vezes por segundo
                            ao_nivel(min(1.0, float(np.sqrt(np.mean(quadro ** 2))) * 12))
                        if not falando:
                            pre_fala.append(quadro)
                            seguidos = seguidos + 1 if prob >= limiar_inicio else 0
                            if seguidos >= 3:  # ~100 ms de fala contínua
                                falando, fala, silencio = True, list(pre_fala), 0
                                if ao_detectar_fala:
                                    ao_detectar_fala()
                            continue
                        fala.append(quadro)
                        silencio = silencio + 1 if prob < limiar_fim else 0
                        if silencio * MS_POR_QUADRO >= silencio_fim_ms or len(fala) * MS_POR_QUADRO >= duracao_max_s * 1000:
                            util = fala[: max(1, len(fala) - max(0, silencio - 6))]  # corta o silêncio do fim
                            return np.concatenate(util)
                if not falando and espera_max_s is not None and time.monotonic() - inicio > espera_max_s:
                    return None


class Transcritor:
    def __init__(self, modelo: str, dispositivo: str, precisao: str):
        self._args = (modelo, dispositivo, precisao)
        self._carregar(modelo, dispositivo, precisao)
        try:
            self._transcrever_bruto(np.zeros(TAXA_VAD, dtype=np.float32))  # aquece e testa a GPU
        except Exception:
            if dispositivo != "cpu":
                self._carregar(modelo, "cpu", "int8")
            else:
                raise

    def _carregar(self, modelo: str, dispositivo: str, precisao: str) -> None:
        from faster_whisper import WhisperModel

        try:
            self.modelo = WhisperModel(modelo, device=dispositivo, compute_type=precisao)
        except Exception:
            if dispositivo == "cpu":
                raise
            # GPU sem as bibliotecas CUDA/cuDNN: segue na CPU, que também é rápida
            dispositivo, precisao = "cpu", "int8"
            self.modelo = WhisperModel(modelo, device=dispositivo, compute_type=precisao)
        self.dispositivo = dispositivo
        self.descricao = f"Whisper '{modelo}' ({'GPU' if dispositivo == 'cuda' else 'CPU'}, {precisao})"

    def _transcrever_bruto(self, audio: np.ndarray) -> str:
        segmentos, _info = self.modelo.transcribe(
            audio,
            language="pt",
            beam_size=5 if self.dispositivo == "cuda" else 1,
            vad_filter=False,                 # o Silero já recortou a fala
            condition_on_previous_text=False,
            without_timestamps=True,
            initial_prompt="Conversa em português do Brasil com o Jarvis.",
        )
        partes = [s.text.strip() for s in segmentos if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)]
        return " ".join(p for p in partes if p).strip()

    def transcrever(self, audio: np.ndarray) -> str:
        if audio is None or audio.size < TAXA_VAD * 0.2:
            return ""
        texto = self._transcrever_bruto(audio.astype(np.float32))
        if any(a in normalizar(texto) for a in ALUCINACOES):
            return ""
        return texto
