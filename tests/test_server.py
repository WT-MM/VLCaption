"""Tests for the HTTP API's request validation (no models loaded)."""

import json

import pytest
from flask.testing import FlaskClient

from vlcaption.server import app


@pytest.fixture
def client() -> FlaskClient:
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client: FlaskClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert json.loads(resp.data)["status"] == "ok"


def test_transcribe_requires_file_path(client: FlaskClient) -> None:
    resp = client.post("/transcribe", json={})
    assert resp.status_code == 400
    assert "file_path is required" in json.loads(resp.data)["message"]


def test_transcribe_rejects_unknown_model(client: FlaskClient) -> None:
    resp = client.post("/transcribe", json={"file_path": "/tmp/x.mp4", "model": "large-v2"})
    assert resp.status_code == 400
    assert "model must be one of" in json.loads(resp.data)["message"]


def test_transcribe_rejects_non_string_model(client: FlaskClient) -> None:
    resp = client.post("/transcribe", json={"file_path": "/tmp/x.mp4", "model": 3})
    assert resp.status_code == 400


def test_transcribe_rejects_missing_file(client: FlaskClient) -> None:
    resp = client.post("/transcribe", json={"file_path": "/nonexistent/file.mp4"})
    assert resp.status_code == 400
    assert "File not found" in json.loads(resp.data)["message"]


def test_progress_starts_idle(client: FlaskClient) -> None:
    resp = client.get("/progress")
    assert resp.status_code == 200
    assert json.loads(resp.data)["status"] in {"idle", "loading_model", "transcribing", "complete", "error"}
