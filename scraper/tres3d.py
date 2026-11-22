"""Renderiza un reel 3D (scraper/tres/escena.html + three.js) en Chromium sin pantalla y lo junta con FFmpeg.

  render(spec, destino, voz=None)   spec = {"escenas": [{"tipo": "portada"|"barras"|"flechas"|"curva"|"tarjetas"|"movil"|"mesa"|"cierre", "dur": s, ...}]}
Sin voz: solo música (redes.musica). Con voz (archivo WAV), se mezcla como en los demás reels.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redes  # noqa: E402

PAGINA = Path(__file__).resolve().parent / "tres" / "escena.html"
FPS = 30


def render(spec: dict, destino: Path, voz: Path | None = None, fps: int = FPS) -> Path:
    from playwright.sync_api import sync_playwright
    destino.parent.mkdir(parents=True, exist_ok=True)
    mudo = destino.with_name(destino.stem + "-mudo.mp4")
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--allow-file-access-from-files",
                                      "--ignore-gpu-blocklist"])
        pag = nav.new_page(viewport={"width": 1080, "height": 1920})
        errores: list[str] = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.goto(PAGINA.as_uri())
        pag.wait_for_function("window.listo === true", timeout=60000)
        total = pag.evaluate("spec => montar(spec)", spec)
        n = int(round(total * fps))
        ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(mudo)], stdin=subprocess.PIPE)
        try:
            for i in range(n):
                url = pag.evaluate("t => cuadro(t)", i / fps)
                ff.stdin.write(base64.b64decode(url.split(",", 1)[1]))
                if errores:
                    raise RuntimeError("Error en la escena 3D: " + errores[0])
        finally:
            ff.stdin.close()
            ff.wait()
            nav.close()
    sonido = redes.musica(destino.with_suffix(".wav"), total)
    try:
        entradas = ["-i", str(mudo), "-i", str(sonido)] + (["-i", str(voz)] if voz else [])
        mezcla = ("[1:a]volume=0.35[m];[2:a]adelay=600|600,volume=1.6[v];[m][v]amix=inputs=2:duration=first[a]" if voz
                  else "[1:a]volume=0.8[a]")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *entradas, "-filter_complex", mezcla, "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(destino)], check=True)
    finally:
        sonido.unlink(missing_ok=True)
        mudo.unlink(missing_ok=True)
    return destino


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(render(spec, Path(sys.argv[2])))
