# Download youtube script

Descarga canciones o playlists de Youtube como audio, con tags y caratula
embebidos para que se vean bien en cualquier reproductor.

* Convierte a **mp3** (o `opus` / `m4a` sin perder calidad).
* Embebe **titulo, artista, album y caratula**.
* Recuerda lo que ya bajo: volver a correr una playlist trae **solo lo nuevo**.
* Descargas **en paralelo** y resumen final de lo que fallo y por que.

## Uso

### Windows

* Descargar el `.exe` de la [ultima release](https://github.com/felipendelicia/download-youtube-script/releases/latest).
* Abrir y utilizar. No hace falta instalar nada: el ejecutable ya trae ffmpeg adentro.

### Linux

* Instalar ffmpeg.

`sudo apt install ffmpeg`

* Clonar codigo de la rama main.

`git clone https://github.com/felipendelicia/download-youtube-script`

* Instalar requerimientos.

`pip install -r requirements.txt`

* Ejecutar archivo index.

`python3 index.py`

Sin argumentos abre el modo interactivo de siempre: pide la URL y listo. Si la
URL es un video que ademas pertenece a una playlist, pregunta cual de los dos
queres; en el resto de los casos no molesta con preguntas.

## Linea de comandos

```
python3 index.py URL [opciones]
```

| Opcion | Que hace |
|---|---|
| `-o, --output DIR` | Carpeta destino (default `./songs`) |
| `-f, --format` | `mp3` (default), `opus`, `m4a` o `native` |
| `-q, --quality` | Bitrate del mp3 en kbps (default `192`) |
| `-j, --jobs N` | Descargas en paralelo (default `1`) |
| `--playlist` / `--no-playlist` | Forzar bajar la playlist entera o solo el video |
| `--cookies NAVEGADOR` | Usar cookies de `chrome`, `firefox`, `edge`... para videos con restriccion de edad |
| `--archive RUTA` | Archivo de descargas (default `<output>/.downloaded.txt`) |
| `--no-archive` | No saltear ni registrar lo ya descargado |
| `--no-metadata` | No embeber tags ni caratula |
| `--check` | Verifica el entorno sin usar la red |

Ejemplos:

```bash
# Una cancion
python3 index.py "https://www.youtube.com/watch?v=..."

# Playlist entera, 4 en paralelo, en otra carpeta
python3 index.py "https://www.youtube.com/playlist?list=..." -j 4 -o ~/Musica

# Sincronizar: baja solo lo que se agrego desde la ultima vez
python3 index.py "https://www.youtube.com/playlist?list=..." -j 4 -o ~/Musica
```

### Sobre los formatos

Youtube entrega el audio en **opus**. Convertirlo a mp3 recomprime algo ya
comprimido, asi que se pierde un poco de calidad: mp3 es el default solo porque
lo lee cualquier cosa.

* `-f opus` guarda el audio original **sin recodificar** (mejor calidad, mas rapido) y acepta tags y caratula.
* `-f native` deja el archivo exactamente como viene, en `.webm`. Ese contenedor no admite caratula, asi que sale solo con tags.

## Diagnostico

Si algo no funciona, correr el self-check. Verifica ffmpeg, el encoder mp3 y las
dependencias de caratula, sin usar la red:

`python3 index.py --check`   (o `download-youtube-script.exe --check` en Windows)

## Mantener actualizado

Youtube cambia seguido y `yt-dlp` se actualiza para acompañarlo. Si las descargas
empiezan a fallar, lo primero es actualizar la dependencia:

`pip install -U yt-dlp`

En Windows no hace falta hacer nada: un rebuild automatico reemplaza el `.exe` de
la ultima release todos los meses con el `yt-dlp` del momento.

## Releases automaticas

El workflow `.github/workflows/release.yml` construye el `.exe` y publica la
release al pushear un tag:

```
git tag 1.0.0
git push origin 1.0.0
```

El build corre en `windows-latest`, empaqueta con PyInstaller (`icon.ico`
incluido) y embebe una build LGPL de ffmpeg. Antes de publicar corre `--check`
sobre el ejecutable generado: si el ffmpeg embebido no puede codificar mp3, la
release no sale.

Para probar un build sin publicar nada, correr el workflow a mano desde la
pestaña Actions (`workflow_dispatch`): deja el `.exe` como artifact.
