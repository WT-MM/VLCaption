# VLCaption

[![Tests](https://github.com/WT-MM/VLCaption/actions/workflows/test.yml/badge.svg)](https://github.com/WT-MM/VLCaption/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)

Auto-generate subtitles for whatever is playing in VLC. Fully local — no
cloud APIs. On Apple Silicon it uses NVIDIA Parakeet via
[parakeet-mlx](https://github.com/senstella/parakeet-mlx): more accurate
than whisper-large-v3 in English, ~10-60x realtime, and it doesn't
hallucinate captions over music or silence. Whisper covers ~100 languages
as fallback.

## Use it

**VLC extension (recommended):** play a video, open
**VLC > Extensions > VLCaption - Auto Subtitles**, click **Generate
Subtitles**. Subtitles load automatically when ready. The server starts on
demand and exits a couple of minutes after VLC quits.

**Watch mode (macOS):** zero clicks — subtitles whatever VLC plays:

```bash
vlcaption watch    # --model auto --interval 3 --overwrite --include-audio --embed
```

Long files are progressive: a quick pass around the playhead puts
subtitles up within seconds, then the full pass replaces them
(`--no-progressive` to disable, `--quick-window` to size the first pass).

Either way, captions are saved as `movie.srt` next to `movie.mp4`, so they
auto-load on every future open.

## Install

```bash
# From PyPI — with uv
uv tool install "vlcaption[mlx]"   # Apple Silicon ([mlx] = fast engines)
uv tool install vlcaption          # elsewhere

# ...or with pip / pipx
pip install "vlcaption[mlx]"
pipx install "vlcaption[mlx]"

vlcaption install                  # set up the VLC extension (optional)

# Or from source
git clone https://github.com/WT-MM/VLCaption.git && cd VLCaption && ./install.sh
```

Needs VLC, Python 3.11+, and on a Mac `ffmpeg` (`brew install ffmpeg`).
Manual extension install: copy `vlcaption/extension/vlcaption.lua` into
VLC's `lua/extensions/` directory and restart VLC.

## Platform support

Developed and tested end-to-end on **macOS (Apple Silicon, VLC 3.0.21)** only, so far.

| Platform | Extension | Watch mode | Auto-load into VLC | Engine |
|----------|-----------|------------|--------------------|--------|
| macOS Apple Silicon | ✅ tested | ✅ tested | ✅ tested | Parakeet / mlx-whisper (GPU) |
| macOS Intel | should work | should work | should work | faster-whisper (CPU) |
| Linux | untested | ❌ | ❌ click Refresh | faster-whisper (CPU/CUDA) |
| Windows | ❌ | ❌ | ❌ | faster-whisper (CPU/CUDA) |

Reports and fixes from other platforms welcome.

## Models

| Choice | Engine | Languages | Size |
|--------|--------|-----------|------|
| `auto` (default) | best available | — | — |
| `parakeet` | parakeet-mlx, Apple GPU | EN + 24 European | 1.2 GB |
| `turbo` | mlx-whisper / faster-whisper | ~100 | 1.6 GB |
| `tiny`…`large-v3` | mlx-whisper / faster-whisper | ~100 | 75 MB – 3 GB |

Models download on first use. `auto` = Parakeet on Apple Silicon, Whisper
turbo elsewhere (CUDA float16 on NVIDIA, int8 on CPU). The engine chosen is
logged per job. No torch/MPS path on purpose: MLX is faster than the MPS
Whisper ports and CTranslate2 has no Metal backend.

## Embed captions into the video

Lossless remux (mp4/m4v/mov/mkv/webm) — the `.srt` becomes a subtitle
track inside the file:

```bash
vlcaption embed movie.mp4               # writes movie.subbed.mp4
vlcaption embed movie.mp4 --replace     # in place (atomic)
```

## Server API

The extension auto-starts the server (port 9839). Run it yourself as
`vlcaption serve`
with `--host/--port/--device/--exit-with-vlc`. Hyphenated aliases
(`vlcaption-watch`, `vlcaption-server`, ...) also exist. Endpoints: `POST /transcribe`
(`file_path`, `model`, `language`, `auto_load`), `GET /progress`,
`GET /health`, `POST /shutdown`.

## Development

```bash
uv sync --extra dev --extra mlx
make format && make static-checks && make test
```

Architecture notes and the design review behind this layout:
`docs/redesign-2026-07.md`.

## Troubleshooting

- **Extension missing from menu** — check the `.lua` is in the extensions
  dir; restart VLC. Menu is under the VLC application menu on macOS.
- **Menu item needs two clicks to reopen** — VLC 3.x bug ([#27688](https://code.videolan.org/videolan/vlc/-/issues/27688)).
- **"FFmpeg is not installed or not in your PATH"** — `brew install ffmpeg`;
  if it's installed but the extension-started server can't see it, re-run
  `vlcaption-install` (GUI apps don't get Homebrew's PATH).
- **Subtitles generated but invisible** — audio-only files have no video
  surface; check **Subtitles > Subtitle Track** on videos.
- **Debug logs** — VLC > Tools > Messages at verbosity 2, prefix `[VLCaption]`;
  server logs: run the launcher in a terminal.

## Uninstall

```bash
rm ~/Library/Application\ Support/org.videolan.vlc/lua/extensions/vlcaption.lua
rm -rf ~/.config/vlcaption
uv tool uninstall vlcaption   # or delete the cloned repo
```

Models live in `~/.cache/huggingface/`.

## License

MIT
