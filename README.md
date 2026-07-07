# VLCaption

[![Tests](https://github.com/WT-MM/VLCaption/actions/workflows/test.yml/badge.svg)](https://github.com/WT-MM/VLCaption/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)

Auto-generate subtitles for whatever is playing in VLC, using fast local
speech-to-text. Everything runs on your machine — no cloud APIs, no data
leaves your computer.

```
$ vlcaption-watch
Watching VLC (model=auto, every 3s). Ctrl-C to stop.
New media playing: /Movies/lecture.mp4
Wrote 812 segments (language=auto): /Movies/lecture.srt
Pushed subtitles into VLC: /Movies/lecture.srt      # ← appears mid-playback
```

On Apple Silicon the default engine is NVIDIA **Parakeet TDT 0.6B v3**
(via [parakeet-mlx](https://github.com/senstella/parakeet-mlx)): better
English accuracy than whisper-large-v3, ~10-60x realtime on M-series, 25
European languages, and — unlike Whisper — it doesn't hallucinate captions
over music and silence. Whisper (via
[mlx-whisper](https://pypi.org/project/mlx-whisper/) on Mac,
faster-whisper elsewhere) covers the other ~75 languages.

---

## Two ways to use it

### Watch mode (recommended, macOS)

A tiny daemon watches VLC and subtitles whatever you play:

```bash
uv run vlcaption-watch
```

Play any video in VLC. If it has no `.srt` next to it, one is generated and
pushed into the running player — subtitles appear mid-playback, usually
within seconds on Apple Silicon, and auto-load on every future open. No VLC
configuration, no extension, no clicks.

Options: `--model` (default `auto`), `--interval` seconds (default 3),
`--overwrite`, `--include-audio`, `--embed` (also bake captions into a
`.subbed` copy of the video).

### VLC extension

1. Open VLC and play a video
2. Go to **VLC > Extensions > VLCaption - Auto Subtitles**
3. Pick a model and click **Generate Subtitles**
4. Subtitles load into the player automatically when transcription finishes

The Python transcription server auto-launches on demand and exits after 30
idle minutes. Note for macOS: VLC deactivates extensions whenever you open a
new file, so you'll need to reopen the dialog per video — watch mode has no
such limitation.

## Installation

### Prerequisites

- [VLC media player](https://www.videolan.org/)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip

### Quick Install

```bash
git clone https://github.com/WT-MM/VLCaption.git
cd VLCaption
chmod +x install.sh
./install.sh
```

This installs the Python package (with the MLX engines on Apple Silicon)
and copies the VLC Lua extension into place.

### Manual Install

1. Install the Python package:
   ```bash
   uv sync --extra mlx   # Apple Silicon
   uv sync               # elsewhere (CPU faster-whisper)
   ```

2. (Optional, for the extension) Copy it to your VLC extensions directory:
   - **macOS**: `~/Library/Application Support/org.videolan.vlc/lua/extensions/`
   - **Linux**: `~/.local/share/vlc/lua/extensions/`
   - **Windows**: `%APPDATA%\vlc\lua\extensions\`

   ```bash
   # macOS example:
   cp extension/vlcaption.lua ~/Library/Application\ Support/org.videolan.vlc/lua/extensions/
   ```

3. Restart VLC.

## Models

| Choice | Engine | Languages | Notes |
|--------|--------|-----------|-------|
| `auto` (default) | Parakeet if installed, else Whisper turbo | — | Best available |
| `parakeet` | parakeet-mlx (~1.2 GB) | EN + 24 European | Fastest and most accurate on Apple Silicon; no music/silence hallucinations |
| `turbo` | mlx-whisper / faster-whisper (~1.6 GB) | ~100 | Best multilingual coverage |
| `tiny` / `base` / `small` / `medium` / `large-v3` | mlx-whisper / faster-whisper | ~100 | Classic Whisper sizes (75 MB – 3 GB) |

Models download automatically on first use. A `whisper-` prefix is also
accepted (`whisper-base` = `base`).

### Hardware support

The `auto` choice picks the fastest stack for your machine:

| Hardware | Engine | Acceleration |
|----------|--------|--------------|
| Apple Silicon | Parakeet via parakeet-mlx (Whisper choices via mlx-whisper) | MLX on the Apple GPU |
| NVIDIA GPU | Whisper turbo via faster-whisper | CUDA, float16 (auto-detected) |
| Anything else | Whisper turbo via faster-whisper | CPU, int8 |

There's no torch/MPS path on purpose: mlx-whisper already runs the full
model on the Apple GPU and benchmarks faster than MPS Whisper ports, and
CTranslate2 has no Metal backend. The server logs which engine it picked
at the start of each job.

The MLX engines decode audio through the `ffmpeg` CLI, so on a Mac:
`brew install ffmpeg`.

## Caption files

Captions are always saved as a standard `.srt` next to the media file
(`movie.mp4` → `movie.srt`), so VLC — and most other players — auto-load
them on every future open, and you can edit or share them.

To bake the captions **into** the video itself as a selectable subtitle
track (a lossless remux — video/audio are untouched):

```bash
vlcaption-embed movie.mp4                    # writes movie.subbed.mp4
vlcaption-embed movie.mp4 --replace          # overwrites movie.mp4 in place
vlcaption-embed movie.mkv --language eng     # tag the track's language
```

Works for mp4/m4v/mov (mov_text), mkv (srt), and webm (webvtt) containers.
Watch mode can do this automatically with `vlcaption-watch --embed`, which
writes a `.subbed` copy after each transcription (never in place, since VLC
still has the original open).

## Running the Server Manually

The extension auto-launches the server, but you can also run it yourself:

```bash
uv run vlcaption-server               # or: python -m vlcaption
uv run vlcaption-server --port 9839 --device auto
```

Options:
- `--host`: Bind address (default: `127.0.0.1`)
- `--port`: Port number (default: `9839`)
- `--device`: Compute device for faster-whisper — `auto`, `cpu`, or `cuda`

API: `POST /transcribe` with `{"file_path": ..., "model": "auto",
"language": null, "auto_load": true}`; `GET /progress`; `GET /health`;
`POST /shutdown`. With `auto_load` (default), the server pushes the
finished SRT into the running VLC automatically (macOS).

## Development

```bash
uv sync --extra dev --extra mlx

make format         # format code
make static-checks  # ruff + mypy
make test           # pytest
```

See `docs/redesign-2026-07.md` for the architecture review behind the
current design (engine choices, VLC macOS extension pitfalls, and why
subtitle delivery is done from the Python side).

## Troubleshooting

**Debug logs**: Open **VLC > Tools > Messages** and set verbosity to **2
(debug)**. All VLCaption extension logs are prefixed with `[VLCaption]`.

**Extension doesn't appear in VLC**: Make sure the `.lua` file is in the
correct extensions directory and restart VLC. On macOS it's under the
**VLC > Extensions** application menu.

**Extension menu item needs two clicks**: Known VLC 3.x bug after a dialog
closes (VideoLAN #27688). Watch mode is unaffected.

**"FFmpeg is not installed or not in your PATH"**: The MLX engines decode
audio via the `ffmpeg` CLI — `brew install ffmpeg`. If ffmpeg is installed
but the error appears when the *extension* starts the server, your launcher
predates the PATH fix (GUI apps don't see Homebrew's PATH): re-run
`./install.sh` to regenerate it.

**Server won't start**: Run the launcher directly to see errors:
```bash
~/.config/vlcaption/launch-server.sh
```
If the launcher doesn't exist, re-run `./install.sh`.

**Subtitles generated but not showing**: Audio-only files have no video
surface to render subtitles on. For videos, check
**Subtitles > Subtitle Track** — the pushed track should be selected.

**"Only local files are supported"**: VLCaption works with local media
files only, not streams or URLs.

## Uninstall

```bash
rm ~/Library/Application\ Support/org.videolan.vlc/lua/extensions/vlcaption.lua  # the extension
rm -rf ~/.config/vlcaption                                                       # the server launcher
rm -rf VLCaption                                                                 # this repo + its venv
```

Downloaded models live in the Hugging Face cache (`~/.cache/huggingface/`)
and can be removed with `huggingface-cli delete-cache`.

## License

MIT
