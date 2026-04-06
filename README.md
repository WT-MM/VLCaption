# VLCaption

Auto-generate subtitles for any media playing in VLC, using local Whisper models.

---

## How It Works

VLCaption is a VLC extension that transcribes audio from your media files and loads subtitles directly into VLC. Everything runs locally on your machine -- no cloud APIs, no data leaves your computer.

1. Open VLC and play a video
2. Go to **View > VLCaption - Auto Subtitles**
3. Pick a model size and click **Generate Subtitles**
4. Subtitles appear automatically when transcription finishes

The Python transcription server starts and stops automatically with VLC.

## Installation

### Prerequisites

- [VLC media player](https://www.videolan.org/)
- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip

### Quick Install

```bash
git clone https://github.com/WT-MM/VLCaption.git
cd VLCaption
chmod +x install.sh
./install.sh
```

This will:
- Install the Python package and dependencies
- Copy the VLC Lua extension to the correct directory for your OS

### Manual Install

1. Install the Python package:
   ```bash
   uv sync        # or: pip install -e .
   ```

2. Copy the VLC extension to your VLC extensions directory:
   - **macOS**: `~/Library/Application Support/org.videolan.vlc/lua/extensions/`
   - **Linux**: `~/.local/share/vlc/lua/extensions/`
   - **Windows**: `%APPDATA%\vlc\lua\extensions\`

   ```bash
   # macOS example:
   cp extension/vlcaption.lua ~/Library/Application\ Support/org.videolan.vlc/lua/extensions/
   ```

3. Restart VLC.

## Model Sizes

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| tiny | ~75 MB | Fastest | Basic |
| base | ~150 MB | Fast | Good |
| small | ~500 MB | Medium | Better |
| medium | ~1.5 GB | Slow | Great |
| large-v3 | ~3 GB | Slowest | Best |

Models are downloaded automatically on first use. Start with `base` for a good balance of speed and quality.

If you have an NVIDIA GPU with CUDA, transcription will be significantly faster. The server auto-detects GPU availability.

## Running the Server Manually

The extension auto-launches the server, but you can also run it manually:

```bash
# Using uv
uv run python -m vlcaption

# Or directly
python -m vlcaption

# With options
python -m vlcaption --port 9839 --model base --device auto
```

Options:
- `--host`: Bind address (default: `127.0.0.1`)
- `--port`: Port number (default: `9839`)
- `--model`: Pre-load a model at startup (default: `base`)
- `--device`: Compute device -- `auto`, `cpu`, or `cuda` (default: `auto`)

## Development

```bash
uv sync --extra dev

# Format code
make format

# Run static checks (ruff + mypy)
make static-checks

# Run tests
make test
```

## Troubleshooting

**Extension doesn't appear in VLC**: Make sure the `.lua` file is in the correct extensions directory and restart VLC. Check VLC > Tools > Messages for errors.

**Server won't start**: Verify `python3 -m vlcaption` works from your terminal. The extension runs this command in the background.

**Slow transcription**: Try the `tiny` or `base` model. If you have an NVIDIA GPU, ensure CUDA is installed for GPU acceleration.

**"Only local files are supported"**: VLCaption works with local media files only, not streams or URLs.

## License

MIT
