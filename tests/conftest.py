"""Configuração dos testes: dados do usuário vão para uma pasta temporária."""

import os
import sys
import tempfile
from pathlib import Path

os.environ["JARVIS_DADOS"] = tempfile.mkdtemp(prefix="jarvis_testes_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from jarvis.armazenamento import criar_perfil  # noqa: E402


@pytest.fixture
def perfil(tmp_path):
    return criar_perfil("Agente Teste", 10, pasta=tmp_path)
