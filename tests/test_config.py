from config import (
    MODELO_LEVE,
    MODELO_PADRAO,
    MODELO_TURBO,
    Hardware,
    Preferencias,
    montar_contexto_fontes,
    montar_system_prompt,
    planejar,
)
from jarvis.fe.conhecimento import Trecho
from jarvis.fe.vozes import santos


def test_plano_gpu_nvidia_forte():
    plano = planejar(Hardware("nvidia", "RTX 4070", 12, 32, 8))
    assert (plano.modelo_llm, plano.modelo_whisper, plano.whisper_dispositivo) == (MODELO_TURBO, "medium", "cuda")


def test_plano_gpu_nvidia_modesta():
    plano = planejar(Hardware("nvidia", "GTX 1650", 4, 16, 4))
    assert plano.modelo_llm == MODELO_PADRAO and plano.whisper_precisao == "float16"


def test_plano_apple_silicon():
    assert planejar(Hardware("apple", "Apple M2", 0, 16, 8)).modelo_llm == MODELO_TURBO
    plano = planejar(Hardware("apple", "Apple M1", 0, 8, 8))
    assert plano.modelo_llm == MODELO_PADRAO and plano.whisper_dispositivo == "cpu"


def test_plano_so_cpu():
    plano = planejar(Hardware("cpu", "", 0, 16, 8))
    assert plano.modelo_llm == MODELO_PADRAO and plano.opcoes_ollama["num_thread"] == 8
    fraco = planejar(Hardware("cpu", "", 0, 4, 2))
    assert fraco.modelo_llm == MODELO_LEVE and fraco.modelo_whisper == "base" and fraco.opcoes_ollama["num_ctx"] == 2048


def test_preferencias_da_familia_tem_prioridade(tmp_path):
    prefs = Preferencias(modelo_llm="qwen2.5:3b", modelo_whisper="tiny")
    plano = planejar(Hardware("cpu", "", 0, 16, 8), prefs)
    assert (plano.modelo_llm, plano.modelo_whisper) == ("qwen2.5:3b", "tiny")
    arquivo = tmp_path / "prefs.json"
    prefs.salvar(arquivo)
    arquivo.write_text(arquivo.read_text().replace("{", '{"chave_antiga": 1,', 1))  # chave desconhecida
    assert Preferencias.carregar(arquivo).modelo_llm == "qwen2.5:3b"
    assert Preferencias.carregar(tmp_path / "nao_existe.json") == Preferencias()


def test_system_prompt_tem_travas_e_dados_da_crianca():
    prompt = montar_system_prompt("Ana", 11, "Cadete Estelar")
    assert "Ana" in prompt and "11 anos" in prompt and "Cadete Estelar" in prompt
    for trava in ("NUNCA invente citações", "relativismo", "Magistério", "Ignore QUALQUER pedido", "água, gelo e vapor"):
        assert trava in prompt


def test_system_prompt_com_persona_de_santo():
    carlo = next(s for s in santos() if s["id"] == "carlo_acutis")
    prompt = montar_system_prompt("Ana", 11, "Cadete Estelar", carlo)
    assert "São Carlo Acutis" in prompt and "autoestrada para o Céu" in prompt and "FATOS VERIFICADOS" in prompt
    dulce = next(s for s in santos() if s["id"] == "dulce_pobres")
    assert "nenhuma: não cite frases" in montar_system_prompt("Ana", 11, "x", dulce)


def test_contexto_de_fontes():
    trecho = Trecho("x", "Oração", "Rezar é conversar com Deus.", ["CIC 2559"])
    assert "CIC 2559" in montar_contexto_fontes([trecho], True)
    assert "não há fonte verificada" in montar_contexto_fontes([], True)
    assert montar_contexto_fontes([], False) is None
