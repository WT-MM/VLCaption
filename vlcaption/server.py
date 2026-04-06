"""Flask HTTP server for VLCaption."""

import json
import logging
import os
import signal
import threading
import time
from argparse import ArgumentParser

from flask import Flask, Response, request

from vlcaption.srt import write_srt_file
from vlcaption.transcriber import Transcriber

logger = logging.getLogger(__name__)

app = Flask(__name__)
transcriber = Transcriber()

# Idle auto-shutdown: 30 minutes
IDLE_TIMEOUT_SECONDS = 30 * 60
_last_activity: float = time.time()
_idle_timer: threading.Timer | None = None


def _update_activity() -> None:
    """Reset the idle timer on any request."""
    global _last_activity
    _last_activity = time.time()


def _check_idle() -> None:
    """Shut down the server if idle for too long."""
    global _idle_timer
    elapsed = time.time() - _last_activity
    if elapsed >= IDLE_TIMEOUT_SECONDS:
        logger.info("Idle timeout reached (%.0fs), shutting down.", elapsed)
        os.kill(os.getpid(), signal.SIGTERM)
    else:
        remaining = IDLE_TIMEOUT_SECONDS - elapsed
        _idle_timer = threading.Timer(remaining, _check_idle)
        _idle_timer.daemon = True
        _idle_timer.start()


def _start_idle_timer() -> None:
    """Start the idle auto-shutdown timer."""
    global _idle_timer
    _idle_timer = threading.Timer(IDLE_TIMEOUT_SECONDS, _check_idle)
    _idle_timer.daemon = True
    _idle_timer.start()


def _json_response(data: dict, status: int = 200) -> Response:  # noqa: ANN401
    """Create a JSON response."""
    return Response(json.dumps(data), status=status, mimetype="application/json")


@app.before_request
def before_request() -> None:
    _update_activity()


@app.route("/health", methods=["GET"])
def health() -> Response:
    """Health check endpoint."""
    return _json_response({"status": "ok"})


@app.route("/transcribe", methods=["POST"])
def transcribe() -> Response:
    """Start a transcription job."""
    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path", "")
    model = data.get("model", "base")
    language = data.get("language")

    if not file_path:
        return _json_response({"status": "error", "message": "file_path is required"}, 400)

    if not os.path.isfile(file_path):
        return _json_response({"status": "error", "message": f"File not found: {file_path}"}, 400)

    if transcriber.is_busy():
        return _json_response({"status": "error", "message": "A transcription is already in progress"}, 409)

    def _run_transcription() -> None:
        try:
            segments = transcriber.transcribe(file_path, model_size=model, language=language)
            srt_path = write_srt_file(segments, file_path)
            detected_lang = transcriber.progress.snapshot().get("language", "unknown")
            transcriber.progress.set_complete(srt_path, str(detected_lang))
            logger.info("Transcription complete: %s", srt_path)
        except Exception:
            pass  # Error is already set in transcriber.progress

    thread = threading.Thread(target=_run_transcription, daemon=True)
    thread.start()

    return _json_response({"status": "started"})


@app.route("/progress", methods=["GET"])
def progress() -> Response:
    """Get transcription progress."""
    return _json_response(transcriber.progress.snapshot())


@app.route("/shutdown", methods=["POST"])
def shutdown() -> Response:
    """Gracefully shut down the server."""
    logger.info("Shutdown requested.")

    def _delayed_shutdown() -> None:
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_delayed_shutdown, daemon=True).start()
    return _json_response({"status": "shutting_down"})


def main() -> None:
    """Entry point for the VLCaption server."""
    parser = ArgumentParser(description="VLCaption transcription server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9839, help="Port to bind to (default: 9839)")
    parser.add_argument("--model", default="base", help="Default Whisper model size (default: base)")
    parser.add_argument("--device", default="auto", help="Compute device: auto, cpu, cuda (default: auto)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    transcriber.set_device(args.device)
    logger.info("Starting VLCaption server on %s:%d (device=%s)", args.host, args.port, args.device)

    _start_idle_timer()
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
