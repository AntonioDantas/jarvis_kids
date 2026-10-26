"""
Abre a janela do Jarvis.

Prefere o Edge, o Chrome, o Chromium ou o Brave em "modo aplicativo" (uma janela limpa, sem
barra de endereço nem abas, parecendo um programa). Se nenhum for encontrado, usa o navegador
padrão. Um perfil separado do navegador é usado só para o Jarvis: nada de histórico, senhas ou
extensões da família se misturam com ele.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path


def _candidatos() -> list[str]:
    if sys.platform.startswith("win"):
        bases = [os.environ.get(v, "") for v in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
        relativos = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                     r"BraveSoftware\Brave-Browser\Application\brave.exe", r"Chromium\Application\chrome.exe"]
        return [str(Path(b) / r) for r in relativos for b in bases if b]
    if sys.platform == "darwin":
        apps = ["Google Chrome", "Microsoft Edge", "Chromium", "Brave Browser"]
        return [f"/Applications/{a}.app/Contents/MacOS/{a}" for a in apps] + \
               [str(Path.home() / f"Applications/{a}.app/Contents/MacOS/{a}") for a in apps]
    nomes = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge",
             "microsoft-edge-stable", "brave-browser"]
    return [caminho for nome in nomes if (caminho := shutil.which(nome))]


def encontrar_navegador() -> str | None:
    for caminho in _candidatos():
        if caminho and Path(caminho).is_file():
            return caminho
    return None


class Janela:
    def __init__(self) -> None:
        self.processo: subprocess.Popen | None = None
        self.modo = ""

    def abrir(self, endereco: str, pasta_perfil: Path, tela_cheia: bool = False) -> bool:
        navegador = encontrar_navegador()
        if navegador:
            pasta_perfil.mkdir(parents=True, exist_ok=True)
            argumentos = [navegador, f"--app={endereco}", f"--user-data-dir={pasta_perfil}", "--no-first-run",
                          "--no-default-browser-check", "--disable-sync", "--disable-extensions",
                          "--window-size=1440,900", "--lang=pt-BR", "--autoplay-policy=no-user-gesture-required"]
            if tela_cheia:
                argumentos.append("--start-fullscreen")
            try:
                self.processo = subprocess.Popen(argumentos, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                 stdin=subprocess.DEVNULL)
                self.modo = "aplicativo"
                return True
            except OSError:
                self.processo = None
        try:
            if webbrowser.open(endereco, new=1):
                self.modo = "navegador"
                return True
        except webbrowser.Error:
            pass
        return False

    def viva(self) -> bool:
        """Só sabemos com certeza quando abrimos o navegador em modo aplicativo."""
        return self.processo is None or self.processo.poll() is None

    def fechar(self) -> None:
        if self.processo and self.processo.poll() is None:
            try:
                self.processo.terminate()
            except OSError:
                pass
