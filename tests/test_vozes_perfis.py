import numpy as np

from jarvis.audio.efeitos import AltoFalante
from jarvis.audio.voz import PERFIS_VOZ, VOZ_PADRAO, Voz, VozKokoro


def test_perfis_de_voz_completos():
    assert VOZ_PADRAO in PERFIS_VOZ
    for perfil in PERFIS_VOZ.values():
        assert perfil["kokoro"] in {"pm_alex", "pf_dora", "pm_santa"}
        assert 0.8 <= perfil["velocidade"] <= 1.3 and 1.0 <= perfil["tom"] <= 1.35
    assert any(p["tom"] >= 1.3 for p in PERFIS_VOZ.values()), "precisa existir uma voz infantil"


class PipelineFalso:
    def __init__(self):
        self.chamadas = []

    def __call__(self, texto, voice, speed):
        self.chamadas.append((voice, speed))
        yield None, None, np.ones(24_000, dtype=np.float32)  # 1 segundo de áudio


def test_tom_eleva_a_voz_sem_mudar_a_velocidade_final():
    motor = VozKokoro.__new__(VozKokoro)
    motor.pipeline, motor.voz_padrao, motor.velocidade = PipelineFalso(), "pm_alex", 1.0
    audio, taxa = motor.sintetizar("oi", {"kokoro": "pf_dora", "velocidade": 1.0, "tom": 1.25})
    voz, velocidade = motor.pipeline.chamadas[0]
    assert voz == "pf_dora" and abs(velocidade - 0.8) < 1e-9  # sintetiza 25% mais devagar…
    assert taxa == 24_000 and len(audio) == 19_200              # …e acelera 25% ao reamostrar (tom mais alto)
    audio, _ = motor.sintetizar("oi", {"tom": 1.0})
    assert len(audio) == 24_000


def test_voz_escolhida_vira_o_padrao():
    voz = Voz("mudo", "pm_alex", "x", 1.0, AltoFalante())
    voz.definir_padrao(PERFIS_VOZ["estrelinha"])
    assert voz.com(velocidade=0.9) == {**PERFIS_VOZ["estrelinha"], "velocidade": 0.9}
    assert voz.iniciar_fluxo().voz["kokoro"] == "pf_dora"
