"""Descarga audio de Youtube (canciones o playlists) con metadata y caratula."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Prompt
from rich.table import Table
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from yt_dlp.version import __version__ as ytdlpVersion

REPO_URL = "https://github.com/felipendelicia/download-youtube-script"
DEFAULT_OUTPUT = "./songs"
ARCHIVE_NAME = ".downloaded.txt"
FFMPEG_NAME = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
AUDIO_FORMATS = ("mp3", "opus", "m4a", "native")

console = Console()

Result = namedtuple("Result", "title ok detail warnings")


# --------------------------------------------------------------------------- #
# ffmpeg
# --------------------------------------------------------------------------- #

def findFfmpeg():
    """Ruta a ffmpeg: el embebido por PyInstaller o el del sistema."""
    bundleDir = getattr(sys, "_MEIPASS", None)
    if bundleDir:
        bundled = os.path.join(bundleDir, FFMPEG_NAME)
        if os.path.isfile(bundled):
            return bundled
    return shutil.which("ffmpeg")


def printFfmpegMissing():
    console.print("[bold red]ffmpeg no esta instalado[/] y es necesario para convertir el audio.")
    console.print("  Linux:   [cyan]sudo apt install ffmpeg[/]")
    console.print("  Windows: [cyan]https://ffmpeg.org/download.html[/]")
    console.print("           (o usa el .exe de la ultima release, que ya lo incluye)")


def selfCheck() -> int:
    """Valida el entorno sin usar la red. Lo corre el CI sobre el .exe generado."""
    console.print(f"python: [cyan]{sys.version.split()[0]}[/]")
    console.print(f"yt-dlp: [cyan]{ytdlpVersion}[/]")

    # mutagen es lo que permite embeber la caratula en opus/m4a. Sin el, esos
    # formatos salen sin portada.
    try:
        from importlib.metadata import version

        console.print(f"mutagen: [cyan]{version('mutagen')}[/]")
    except Exception:  # noqa: BLE001
        console.print("mutagen: [yellow]no encontrado[/] (opus y m4a saldran sin caratula)")

    ffmpeg = findFfmpeg()
    if ffmpeg is None:
        printFfmpegMissing()
        return 1
    console.print(f"ffmpeg: [cyan]{ffmpeg}[/]")

    # Un segundo de silencio a mp3: prueba que libmp3lame este compilado.
    target = os.path.join(tempfile.gettempdir(), "dys-selfcheck.mp3")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-y",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", "1", "-c:a", "libmp3lame", target],
        capture_output=True,
        text=True,
    )
    ok = result.returncode == 0 and os.path.isfile(target)
    if os.path.isfile(target):
        os.remove(target)

    if not ok:
        console.print("[bold red]ffmpeg no puede codificar mp3[/] (falta libmp3lame).")
        console.print(result.stderr.strip()[-800:])
        return 1

    console.print("encoder mp3: [bold green]OK[/]")
    return 0


# --------------------------------------------------------------------------- #
# Archivo de descargas: evita volver a bajar lo que ya esta
# --------------------------------------------------------------------------- #

def readArchive(path: str) -> set:
    if not path or not os.path.isfile(path):
        return set()
    done = set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) >= 2:
                done.add(parts[1])
    return done


def appendArchive(path: str, videoId: str, lock: threading.Lock):
    """Mismo formato que el --download-archive de yt-dlp, para ser compatible."""
    if not path or not videoId:
        return
    with lock:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"youtube {videoId}\n")


# --------------------------------------------------------------------------- #
# Descarga
# --------------------------------------------------------------------------- #

def formatSelector(audioFormat: str) -> str:
    """Prefiere el contenedor que evita recodificar."""
    if audioFormat == "m4a":
        return "bestaudio[ext=m4a]/bestaudio/best"
    if audioFormat in ("opus", "native"):
        return "bestaudio[ext=webm]/bestaudio/best"
    return "bestaudio/best"


class CapturingLogger:
    """Guarda los mensajes de yt-dlp en vez de imprimirlos: romperian la barra
    de progreso, pero perderlos esconde fallos reales (una caratula que no se
    embebio, un formato que no estaba)."""

    def __init__(self):
        self.warnings = []
        self.errors = []

    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        self.warnings.append(str(message).strip())

    def error(self, message):
        self.errors.append(str(message).strip())


def buildOptions(args, ffmpeg: str, template: str, hooks, logger) -> dict:
    options = {
        "format": formatSelector(args.format),
        "outtmpl": template,
        "ffmpeg_location": ffmpeg,
        "noplaylist": True,  # la playlist ya la enumeramos nosotros
        "quiet": True,
        "logger": logger,
        "noprogress": True,
        "windowsfilenames": True,
        "concurrent_fragment_downloads": 4,
        "retries": 5,
        "progress_hooks": [hooks.onProgress],
        "postprocessor_hooks": [hooks.onPostProcess],
        "postprocessors": [],
    }

    if args.cookies:
        options["cookiesfrombrowser"] = (args.cookies,)

    postprocessors = options["postprocessors"]

    # El orden importa: primero se extrae el audio, despues se le pegan los tags.
    if args.format != "native":
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": args.format,
            "preferredquality": str(args.quality),
        })

    if not args.no_metadata:
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
        # El audio nativo de Youtube viene en webm, contenedor que no admite
        # caratula embebida. Los demas formatos si.
        if args.format != "native":
            options["writethumbnail"] = True
            postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    return options


class ItemHooks:
    """Traduce los eventos de yt-dlp a una barra de progreso de rich."""

    def __init__(self, progress: Progress, taskId, title: str):
        self.progress = progress
        self.taskId = taskId
        self.title = title

    def onProgress(self, status: dict):
        if status["status"] == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            self.progress.update(
                self.taskId,
                total=total,
                completed=status.get("downloaded_bytes", 0),
            )
        elif status["status"] == "finished":
            # Fija el total real para que la barra no quede en "1/1 bytes".
            size = status.get("total_bytes") or status.get("downloaded_bytes")
            self.progress.update(
                self.taskId,
                total=size,
                completed=size,
                description=f"[yellow]convirtiendo[/] {self.title}",
            )

    def onPostProcess(self, status: dict):
        if status.get("status") == "started":
            name = status.get("postprocessor", "")
            if name == "EmbedThumbnail":
                self.progress.update(self.taskId, description=f"[yellow]caratula[/] {self.title}")


def outputTemplate(outputDir: str, index) -> str:
    """Numera los archivos solo cuando forman parte de una playlist."""
    if index is None:
        return os.path.join(outputDir, "%(title)s.%(ext)s")
    return os.path.join(outputDir, f"{index:02d} - %(title)s.%(ext)s")


def downloadEntry(entry, index, args, ffmpeg, progress, archive, lock):
    title = entry.get("title") or entry.get("id") or "sin titulo"
    shortTitle = title if len(title) <= 45 else title[:44] + "…"
    taskId = progress.add_task(f"[cyan]bajando[/] {shortTitle}", total=None)

    hooks = ItemHooks(progress, taskId, shortTitle)
    logger = CapturingLogger()
    options = buildOptions(args, ffmpeg, outputTemplate(args.output, index), hooks, logger)

    url = entry.get("url") or entry.get("webpage_url") or entry.get("id")
    try:
        with YoutubeDL(options) as downloader:
            downloader.download([url])
    except DownloadError as error:
        progress.update(taskId, description=f"[red]fallo[/] {shortTitle}", total=1, completed=1)
        detail = logger.errors[-1] if logger.errors else str(error).strip().splitlines()[-1]
        return Result(title, False, detail[:160], logger.warnings)
    except Exception as error:  # noqa: BLE001 - se reporta en el resumen final
        progress.update(taskId, description=f"[red]fallo[/] {shortTitle}", total=1, completed=1)
        return Result(title, False, f"{type(error).__name__}: {error}"[:160], logger.warnings)

    appendArchive(archive, entry.get("id"), lock)
    progress.update(taskId, description=f"[green]listo[/] {shortTitle}")
    return Result(title, True, None, logger.warnings)


def listEntries(url: str, allowPlaylist: bool):
    """Enumera la playlist sin descargar. Devuelve (titulo, entries)."""
    options = {
        "quiet": True,
        "logger": CapturingLogger(),  # el error se traduce a un mensaje propio
        "extract_flat": "in_playlist",
        "noplaylist": not allowPlaylist,
        "ignoreerrors": True,
    }
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)

    if info is None:
        return None, []
    if info.get("_type") == "playlist":
        return info.get("title"), [e for e in (info.get("entries") or []) if e]
    return None, [info]


# --------------------------------------------------------------------------- #
# Interfaz
# --------------------------------------------------------------------------- #

def isAmbiguous(url: str) -> bool:
    """URL de un video que ademas pertenece a una playlist."""
    return "list=" in url and ("watch?v=" in url or "/shorts/" in url)


def showBanner():
    console.print(Panel(
        "[bold]Download youtube script[/] [dim]by felipendelicia[/]\n"
        f"[dim]{REPO_URL}[/]",
        border_style="cyan",
        expand=False,
    ))


def askInteractive(args):
    """Completa los datos que falten preguntando. Devuelve la URL."""
    showBanner()
    url = ""
    while not url.strip():
        url = Prompt.ask("[bold cyan]URL[/] de la cancion o playlist")

    if isAmbiguous(url) and args.playlist is None:
        console.print()
        console.print("Esa URL es un video [bold]dentro de[/] una playlist.")
        choice = Prompt.ask(
            "Que queres bajar",
            choices=["cancion", "playlist"],
            default="cancion",
        )
        args.playlist = choice == "playlist"

    return url.strip()


def shorten(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def showSummary(results, skipped: int, outputDir: str):
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    warned = [r for r in results if r.warnings]

    console.print()
    if failed:
        table = Table(title="No se pudieron bajar", title_style="bold red")
        table.add_column("Cancion", style="white", overflow="fold")
        table.add_column("Motivo", style="dim", overflow="fold")
        for item in failed:
            table.add_row(item.title, item.detail or "error desconocido")
        console.print(table)
        console.print()

    if warned:
        # Los avisos suelen ser del entorno, no de una cancion puntual: se
        # agrupan para no repetir el mismo texto una vez por item.
        counts = {}
        for item in warned:
            for warning in dict.fromkeys(item.warnings):
                counts[warning] = counts.get(warning, 0) + 1

        table = Table(title="Avisos", title_style="bold yellow")
        table.add_column("Aviso", style="dim", overflow="fold")
        table.add_column("Canciones", style="dim", justify="right")
        for warning, count in sorted(counts.items(), key=lambda pair: -pair[1]):
            table.add_row(shorten(warning, 160), str(count))
        console.print(table)
        console.print()

    parts = [f"[bold green]{len(ok)} descargadas[/]"]
    if failed:
        parts.append(f"[bold red]{len(failed)} con error[/]")
    if skipped:
        parts.append(f"[dim]{skipped} ya estaban[/]")
    console.print(" · ".join(parts))
    console.print(f"[dim]Carpeta:[/] {os.path.abspath(outputDir)}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parseArgs(argv):
    parser = argparse.ArgumentParser(
        prog="download-youtube-script",
        description="Descarga canciones o playlists de Youtube como audio con metadata.",
        epilog="Sin argumentos abre el modo interactivo.",
    )
    parser.add_argument("url", nargs="?", help="URL de la cancion o playlist")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help=f"carpeta destino (default: {DEFAULT_OUTPUT})")
    parser.add_argument("-f", "--format", default="mp3", choices=AUDIO_FORMATS,
                        help="formato de salida; 'opus' conserva la calidad original y "
                             "'native' guarda el archivo sin tocar, pero sin caratula "
                             "(default: mp3)")
    parser.add_argument("-q", "--quality", default="192",
                        help="bitrate para mp3, en kbps (default: 192)")
    parser.add_argument("-j", "--jobs", type=int, default=1,
                        help="descargas en paralelo (default: 1)")
    parser.add_argument("--cookies", metavar="NAVEGADOR",
                        help="usar cookies del navegador (chrome, firefox, edge, brave...) "
                             "para videos con restriccion de edad")

    playlist = parser.add_mutually_exclusive_group()
    playlist.add_argument("--playlist", dest="playlist", action="store_true", default=None,
                          help="bajar la playlist entera")
    playlist.add_argument("--no-playlist", dest="playlist", action="store_false",
                          help="bajar solo el video, aunque la URL traiga una playlist")

    parser.add_argument("--archive", metavar="RUTA",
                        help=f"archivo de descargas (default: <output>/{ARCHIVE_NAME})")
    parser.add_argument("--no-archive", action="store_true",
                        help="no registrar ni saltear lo ya descargado")
    parser.add_argument("--no-metadata", action="store_true",
                        help="no embeber tags ni caratula")
    parser.add_argument("--check", action="store_true",
                        help="verifica ffmpeg y el encoder mp3, sin usar la red")

    return parser.parse_args(argv)


def run(args) -> int:
    ffmpeg = findFfmpeg()
    if ffmpeg is None:
        printFfmpegMissing()
        return 1

    url = args.url or askInteractive(args)
    os.makedirs(args.output, exist_ok=True)

    archive = None if args.no_archive else (args.archive or os.path.join(args.output, ARCHIVE_NAME))
    lock = threading.Lock()

    with console.status("[cyan]Buscando...[/]"):
        playlistTitle, entries = listEntries(url, allowPlaylist=bool(args.playlist))

    if not entries:
        console.print("[bold red]No se encontro nada en esa URL.[/]")
        console.print("[dim]Puede ser privada, borrada, o la URL puede estar mal.[/]")
        return 1

    isPlaylist = playlistTitle is not None
    if isPlaylist:
        console.print(f"Playlist: [bold]{playlistTitle}[/] · {len(entries)} elementos")

    done = readArchive(archive)
    pending = [(i, e) for i, e in enumerate(entries, start=1) if e.get("id") not in done]
    skipped = len(entries) - len(pending)

    if skipped:
        console.print(f"[dim]{skipped} ya estaban descargadas, se saltean.[/]")
    if not pending:
        console.print("[bold green]Todo al dia, no hay nada nuevo.[/]")
        return 0

    columns = [
        TextColumn("{task.description}"),
        BarColumn(bar_width=24),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ]
    results = []

    console.print()
    with Progress(SpinnerColumn(), *columns, console=console, transient=False) as progress:
        def work(item):
            index, entry = item
            return downloadEntry(
                entry,
                index if isPlaylist else None,
                args, ffmpeg, progress, archive, lock,
            )

        if args.jobs > 1:
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                results = list(pool.map(work, pending))
        else:
            results = [work(item) for item in pending]

    showSummary(results, skipped, args.output)
    return 0 if all(r.ok for r in results) else 1


def main():
    args = parseArgs(sys.argv[1:])

    if args.check:
        sys.exit(selfCheck())

    interactive = args.url is None
    try:
        code = run(args)
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Cancelado.[/]")
        code = 130

    if interactive:
        console.print()
        console.input("[dim]Enter para salir...[/]")
    sys.exit(code)


if __name__ == "__main__":
    main()
