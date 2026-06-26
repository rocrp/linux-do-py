"""Tests for pure rendering helpers in cli.py (no network)."""

from __future__ import annotations

from linux_do_py.cli import _format_count, _post_body, _relative_time


def test_format_count():
    assert _format_count(0) == "0"
    assert _format_count(999) == "999"
    assert _format_count(1500) == "1.5k"
    assert _format_count(110500) == "110.5k"


def test_relative_time_buckets():
    assert _relative_time("") == ""
    assert _relative_time("garbage-timestamp") == "garbage-ti"  # first 10 chars fallback


def test_post_body_prefers_raw():
    post = {"raw": "# Hello\n\nWorld", "cooked": "<h1>Hello</h1><p>World</p>"}
    assert _post_body(post) == "# Hello\n\nWorld"


def test_post_body_falls_back_to_cooked():
    post = {"raw": "   ", "cooked": "<p>Just <strong>cooked</strong></p>"}
    body = _post_body(post)
    assert "cooked" in body
    assert "<" not in body  # HTML stripped to markdown
