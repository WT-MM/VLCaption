# VLCaption redesign review — July 2026

A design review of the original (April 2026) architecture, based on (a) live
end-to-end testing on macOS 15 / VLC 3.0.21, and (b) a research pass over the
mid-2026 local-STT and VLC-ecosystem landscape. Verdict up front: **the core
idea is sound and the niche is still open, but two of the three original
design pillars — the dialog-driven extension and the faster-whisper engine —
are the wrong choices in 2026.**

## What was verified working (live, this machine)

- The extension IS discovered on macOS, appears under VLC > Extensions, and
  its dialog renders fully (label, dropdown, both buttons, status label).
  "Extensions never worked on Mac" is false — VLC's Cocoa UI ships a complete
  extension dialog provider.
- The full designed flow succeeded end to end: activate → Generate (server
  auto-launched via the nohup launcher) → transcribe → Refresh →
  `vlc.input.add_subtitle` → "Subtitles loaded!", track added.
- `io.popen`+curl works in the extension context on the notarized VLC build
  (hardened runtime, but no app-sandbox entitlement — verified via codesign).
- VLC auto-loads AND auto-selects a same-basename `.srt` on media open.
  Writing the SRT next to the file is a zero-integration delivery path for
  every future viewing.

## Confirmed defects (reproduced live)

1. **Opening a new media file deactivates the extension** (macOS behavior):
   the dialog closes, `deactivate()` fires, and — because `deactivate()`
   POSTs `/shutdown` — **the transcription server is killed**. Changing
   files mid-transcription aborts everything. Design flaw, not a bug.
2. **Two-click reopen** — after the dialog closes, the Extensions menu item
   must be clicked twice to reactivate (VideoLAN gitlab #27688 / #29147,
   open since 2023; fixed in master 2026-05, unreleased in 3.x).
3. **The 10-second watchdog**: extension Lua callbacks that block ~10s
   trigger VLC's "Extension does not respond — kill it?" dialog
   (`WATCH_TIMER_PERIOD`). Our synchronous `io.popen(curl --max-time 10)`
   sits exactly on that line; a slow first health-check or model download
   makes VLC offer to kill us. Likely the original "it never worked" culprit.
4. **`add_subtitle(path)` does not auto-select the track.** VLC 3.0.x
   supports `vlc.input.add_subtitle(path, true)` — the second arg is
   autoselect (verified in vlc-3.0 `libs/input.c` and empirically on this
   machine). Must pass a plain path, NOT a file:// URI (double-encodes).
5. **Status gap during model load**: `set_started()` is called only after
   `WhisperModel(...)` returns, so during load/download `/progress` reports
   `idle` and the UI says "No transcription in progress" while work is
   happening. Reproduced live.
6. **`language` is always "unknown"**: `server._run_transcription` reads the
   detected language from the progress snapshot *before* `set_complete` ever
   stores it, and the transcriber never writes it during transcription.
   Reproduced live (log said `Detected language 'en' (p=1.00)`).
7. `playing_changed` never fires on macOS (gitlab #22778) — don't build
   anything on input-state callbacks.

## Research findings that change the design

### Engine (the big one)

- **faster-whisper / CTranslate2 is CPU-only on macOS** — no Metal/MPS
  backend, none planned (CTranslate2 #1562). It is now the slowest
  mainstream engine on Apple Silicon (~7x slower than MLX runtimes in the
  9-engine mac-whisper-speedtest).
- **NVIDIA Parakeet TDT 0.6B (v3, 25 languages) via `parakeet-mlx`** is
  where the Mac subtitle ecosystem converged in 2025-26 (MacWhisper,
  superwhisper, Subtitle Edit): better English WER than whisper-large-v3
  (6.34 vs ~7.4 Open-ASR avg), ~65x realtime on an M3 (68-min video in
  ~62s), first-class word/segment timestamps, and — critical for movies —
  near-zero hallucination on silence/music (transducer architecture;
  whisper-large-v3 hallucinates on ~100% of non-speech audio per the
  Calm-Whisper study). CC-BY-4.0, `pip install parakeet-mlx`, chunked
  long-form built in (120s chunks, 15s overlap-merge).
- **Fallback for the ~75 languages Parakeet lacks: whisper-large-v3-turbo
  via `mlx-whisper`** (~2x faster than whisper.cpp/Metal; OpenAI-shaped
  segment output, near drop-in for our existing segment handling). Needs
  external Silero VAD + `condition_on_previous_text=False` for movie audio.
- Keep faster-whisper only as the non-Mac / CPU portability backend.

### Ecosystem / competition

- **VLC 4 will eventually obsolete this**: whisper.cpp STT is an unmerged
  draft (VideoLAN MR !5155, opened 2024) targeting VLC 4.0, which is still
  nightlies-only. Realistic window: 1-2+ years. Frame VLCaption as the
  stopgap for the VLC 3.x installed base.
- FFmpeg 8.0 ships a native `whisper` audio filter (af_whisper) — a
  maintained one-command video→SRT primitive, useful as an alt backend.
- Closest competitor: `vlc-ai-subs` (Mar 2026, ~3 stars) — same
  extension+Python-sidecar shape, unproven. MacWhisper ($59, closed) does
  watch-folders but lives outside the player. IINA/mpv-on-mac have nothing.
- **Open gaps worth owning**: (1) zero-friction Mac-native VLC companion,
  (2) **progressive subtitles** — transcribe ahead of the playhead and
  append cues so subs appear during *this* viewing, which nothing on macOS
  does today.

### Better VLC control paths than the extension

Verified options for pushing an SRT into a *running* VLC from outside:

- **AppleScript**: `tell application "VLC" to OpenURL "file:///path/x.srt"`
  hits an undocumented `tryAsSubtitle:YES` path that adds the SRT as a
  subtitle slave to the current input **with autoselect** (VLCPlaylist.m).
  macOS-only, trivial, verified.
- **HTTP interface** (`--extraintf http --http-password …`):
  `?command=addsubtitle&val=<path>` (+ `command=subtitle_track&val=<id>` to
  select). Cross-platform, requires one-time VLC pref change.
  `/requests/playlist.json` reveals the currently-playing file URI —
  enabling a companion that *watches* VLC instead of living inside it.
- Same-basename `.srt` next to the media: zero-integration, auto-loads and
  auto-selects on every future open (verified). No mid-playback rescan.

## Revised architecture

**Move the brains out of the Lua extension.** The Python server becomes the
product (a small daemon/CLI, later possibly a menubar app); VLC becomes a
target we push subtitles into, not the place logic lives.

```
vlcaption daemon (Python, uv tool install vlcaption)
  ├─ engines: parakeet-mlx (default on Apple Silicon)
  │           mlx-whisper large-v3-turbo (non-Parakeet languages)
  │           faster-whisper (non-Mac fallback)
  ├─ watches VLC via /requests/playlist.json (opt-in) or is invoked per-file
  ├─ writes <media>.srt next to the file (persistent for replays)
  └─ pushes into the running player: AppleScript OpenURL (mac)
                                     or HTTP addsubtitle (all platforms)

extension/vlcaption.lua (optional thin trigger, kept for discoverability)
  └─ one button: POST /transcribe for the current item; never blocks >2s;
     no /shutdown on deactivate; add_subtitle(path, true) on completion
```

Progressive mode (differentiator, phase 2): transcribe in chunk order from
the current playhead position, append cues to the SRT as they finish, and
re-push the file (players re-read on add; mpv supports `sub-add cached`
re-selection — a future mpv/IINA port shares the daemon).

## Immediate fix list (independent of architecture)

All implemented and merged (PRs #5-#7), kept for the record:

- [x] `add_subtitle(path, true)` — autoselect (extension/vlcaption.lua)
- [x] Remove `/shutdown` from `deactivate()` — rely on the existing
      30-min idle timer instead
- [x] `set_started()` before model load + a distinct `loading_model` status
- [x] Fix detected-language plumbing (store into progress at detection time)
- [x] Background the curl in `do_generate` or drop `--max-time` to ≤5s to
      stay clear of the 10s watchdog
- [x] Engine abstraction + parakeet-mlx backend, model dropdown becomes
      engine/quality picker
