"""Tests for pure parsing / URL-building logic in api.py (no network)."""

from __future__ import annotations

from linux_do_py.api import (
    Category,
    Tag,
    Topic,
    _feed_path,
    _match_category,
    _normalize,
)


def _cat(id, name, slug, *, parent_id=None, parent_slug=None) -> Category:
    return Category(
        id=id,
        name=name,
        slug=slug,
        topic_count=0,
        post_count=0,
        parent_id=parent_id,
        parent_slug=parent_slug,
    )


# ── Topic / Category / Tag dataclasses ───────────────────────────────────────


def test_topic_from_dict_and_url():
    t = Topic.from_dict({"id": 123, "title": "Hello", "slug": "hello-world", "tags": [{"name": "foo"}, "bar"]})
    assert t.id == 123
    assert t.tags == ["foo", "bar"]
    assert t.url == "https://linux.do/t/hello-world/123"


def test_category_path_segments_toplevel_and_sub():
    top = _cat(4, "Develop", "develop")
    sub = _cat(94, "Cloud Asset", "cloud-asset", parent_id=14, parent_slug="resource")
    assert top.path_segments == "develop/4"
    assert sub.path_segments == "resource/cloud-asset/94"


def test_tag_url():
    assert Tag(id=1, name="SSL", slug="ssl", count=22).url == "https://linux.do/tag/ssl"


# ── _feed_path URL building ──────────────────────────────────────────────────


def test_feed_path_plain_listings():
    assert _feed_path("latest", page=0) == "/latest.json?page=0"
    assert _feed_path("hot", page=2) == "/hot.json?page=2"
    assert _feed_path("top", period="daily") == "/top.json?page=0&period=daily"


def test_feed_path_period_only_for_top():
    # period is appended for top, ignored for other listings
    assert "period" in _feed_path("top", period="monthly")
    assert "period" not in _feed_path("latest", period="monthly")


def test_feed_path_order_and_limit():
    path = _feed_path("latest", order="views", limit=5)
    assert "order=views" in path
    assert "per_page=5" in path


def test_feed_path_tag_only():
    assert _feed_path("hot", tag="chatgpt") == "/tag/chatgpt/l/hot.json?page=0"


def test_feed_path_category_only():
    cat = _cat(4, "Develop", "develop")
    assert _feed_path("latest", category=cat) == "/c/develop/4/l/latest.json?page=0"


def test_feed_path_subcategory():
    sub = _cat(94, "Cloud Asset", "cloud-asset", parent_id=14, parent_slug="resource")
    assert _feed_path("latest", category=sub).startswith("/c/resource/cloud-asset/94/l/latest.json")


def test_feed_path_tag_and_category():
    cat = _cat(4, "Develop", "develop")
    assert _feed_path("latest", tag="ssl", category=cat) == "/tags/c/develop/4/ssl/l/latest.json?page=0"


# ── category resolution ──────────────────────────────────────────────────────


def test_normalize():
    assert _normalize("  Foo   Bar ") == "foo bar"


def test_match_category_by_id_slug_name():
    cats = [
        _cat(4, "Develop", "develop"),
        _cat(94, "Cloud Asset", "cloud-asset", parent_id=14, parent_slug="resource"),
    ]
    assert _match_category(cats, "4").id == 4
    assert _match_category(cats, "develop").id == 4
    assert _match_category(cats, "Develop").id == 4  # case-insensitive name
    assert _match_category(cats, "resource/cloud-asset").id == 94  # parent path
    assert _match_category(cats, "nonexistent") is None
