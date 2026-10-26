"""
Sensor de voz (Voice Activity Detection).

Usa o Silero VAD para saber, a cada 32 ms, se a criança está falando.
Se o Silero não estiver disponível (ex.: Mac Intel sem PyTorch), cai para um
detector por energia com ajuste automático ao ruído do ambiente.
"""

from __future__ import annotations

import numpy as np

TAXA_VAD = 16_000
TAMANHO_QUADRO = 512  # 32 ms a 16 kHz — o tamanho que o Silero espera


class SensorVoz:
    def __init__(self) -> None:
        self._modelo = None
        self._torch = None
        self._ruido = 0.004
        try:
            import torch
            from silero_vad import load_silero_vad

            self._torch = torch
            self._modelo = load_silero_vad()
            self.motor = "Silero VAD"
        except Exception:
            self.motor = "detector por energia (reserva)"

    def reiniciar(self) -> None:
        if self._modelo is not None:
            self._modelo.reset_states()

    def probabilidade(self, quadro: np.ndarray) -> float:
        """Probabilidade (0 a 1) de haver fala em um quadro de 512 amostras."""
        if self._modelo is not None:
            with self._torch.no_grad():
                return float(self._modelo(self._torch.from_numpy(quadro.astype(np.float32)), TAXA_VAD).item())
        energia = float(np.sqrt(np.mean(np.square(quadro))) + 1e-7)
        prob = float(np.clip((energia / self._ruido - 2.5) / 4.0, 0.0, 1.0))
        if prob < 0.2:  # aprende o ruído de fundo apenas nos silêncios
            self._ruido = 0.95 * self._ruido + 0.05 * max(energia, 1e-4)
        return prob
