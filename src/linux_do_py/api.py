"""Fetch data from linux.do (Discourse) JSON endpoints."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests as curl_requests

BASE_URL = "https://linux.do"

# Exit codes (subset of sysexits.h) carried by LinuxDoError → process exit status.
EX_NOINPUT = 66  # not found / empty result
EX_TEMPFAIL = 75  # rate limit / transient — retry later
EX_NOPERM = 77  # auth required

_CACHE_DIR = Path.home() / ".cache" / "linux-do-py"
_METADATA_TTL = 24 * 60 * 60  # categories/tags change slowly; cache for a day


class LinuxDoError(Exception):
    """User-facing error from linux.do (rate limit, auth wall, bad response)."""

    def __init__(self, message: str, *, exit_code: int = 1, hint: str | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.hint = hint


@dataclass(slots=True)
class Topic:
    id: int
    title: str
    slug: str
    category_id: int
    views: int
    posts_count: int
    reply_count: int
    like_count: int
    created_at: str
    last_posted_at: str
    last_poster_username: str
    pinned: bool = False
    excerpt: str = ""
    tags: list[str] | None = None
    op_like_count: int = 0
    has_accepted_answer: bool = False

    @property
    def url(self) -> str:
        return f"{BASE_URL}/t/{self.slug}/{self.id}"

    @classmethod
    def from_dict(cls, d: dict) -> Topic:
        return cls(
            id=d["id"],
            title=d["title"],
            slug=d.get("slug", "topic"),
            category_id=d.get("category_id", 0),
            views=d.get("views", 0),
            posts_count=d.get("posts_count", 0),
            reply_count=d.get("reply_count", 0),
            like_count=d.get("like_count", 0),
            created_at=d.get("created_at", ""),
            last_posted_at=d.get("last_posted_at", ""),
            last_poster_username=d.get("last_poster_username", ""),
            pinned=d.get("pinned", False),
            excerpt=d.get("excerpt", ""),
            tags=[t["name"] if isinstance(t, dict) else t for t in d.get("tags", [])],
            op_like_count=d.get("op_like_count", 0),
            has_accepted_answer=d.get("has_accepted_answer", False),
        )


@dataclass(slots=True)
class Category:
    id: int
    name: str
    slug: str
    topic_count: int
    post_count: int
    description: str = ""
    parent_id: int | None = None
    parent_slug: str | None = None

    @property
    def path_segments(self) -> str:
        """URL path used in /c/<segments> Discourse listings."""
        if self.parent_slug:
            return f"{self.parent_slug}/{self.slug}/{self.id}"
        return f"{self.slug}/{self.id}"


@dataclass(slots=True)
class Tag:
    id: int
    name: str
    slug: str
    count: int = 0

    @property
    def url(self) -> str:
        return f"{BASE_URL}/tag/{self.slug}"


def _fetch_json(path: str) -> dict:
    """Fetch JSON from linux.do, surfacing rate-limit/auth/HTML walls as clean errors."""
    url = f"{BASE_URL}{path}"
    try:
        resp = curl_requests.get(
            url,
            impersonate="chrome",
            headers={"Accept": "application/json"},
            timeout=30,
        )
    except curl_requests.RequestsError as e:
        raise LinuxDoError(f"Network error contacting linux.do: {e}", exit_code=EX_TEMPFAIL) from e

    code = resp.status_code
    if code == 429:
        raise LinuxDoError(
            "linux.do rate-limited the request (HTTP 429).",
            exit_code=EX_TEMPFAIL,
            hint="Anonymous access is throttled — wait a minute and retry.",
        )
    if code in (401, 403):
        raise LinuxDoError(
            f"linux.do denied access (HTTP {code}).",
            exit_code=EX_NOPERM,
            hint="This content likely requires a logged-in session.",
        )
    if code == 404:
        raise LinuxDoError(
            "Not found on linux.do (HTTP 404).",
            exit_code=EX_NOINPUT,
            hint="Check the topic ID, tag, or category slug.",
        )
    if code >= 400:
        raise LinuxDoError(
            f"linux.do request failed (HTTP {code}).",
            exit_code=EX_TEMPFAIL if code >= 500 else 1,
        )

    try:
        return resp.json()
    except ValueError as e:
        raise LinuxDoError(
            "linux.do returned a non-JSON response.",
            exit_code=EX_TEMPFAIL,
            hint="Likely a login wall, rate limit, or Cloudflare challenge — retry shortly.",
        ) from e


def _fetch_json_cached(path: str, name: str, ttl: int = _METADATA_TTL) -> dict:
    """Like _fetch_json but backed by a TTL disk cache (for throttled metadata endpoints)."""
    cache_file = _CACHE_DIR / f"{name}.json"
    try:
        if cache_file.is_file() and (time.time() - cache_file.stat().st_mtime) < ttl:
            return json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass  # corrupt/unreadable cache → refetch

    data = _fetch_json(path)
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # cache write must never block command execution
    return data


def _feed_path(
    listing: str,
    *,
    page: int = 0,
    period: str = "weekly",
    order: str | None = None,
    limit: int | None = None,
    tag: str | None = None,
    category: Category | None = None,
) -> str:
    """Build a Discourse listing URL. Pure function (no I/O) for easy testing."""
    if category and tag:
        base = f"/tags/c/{category.path_segments}/{tag}"
    elif category:
        base = f"/c/{category.path_segments}"
    elif tag:
        base = f"/tag/{tag}"
    else:
        base = None

    path = f"{base}/l/{listing}.json" if base else f"/{listing}.json"

    params = [f"page={page}"]
    if listing == "top":
        params.append(f"period={period}")
    if order:
        params.append(f"order={order}")
    if limit:
        params.append(f"per_page={limit}")
    return f"{path}?{'&'.join(params)}"


def fetch_topics(
    listing: str = "latest",
    *,
    page: int = 0,
    period: str = "weekly",
    order: str | None = None,
    limit: int | None = None,
    tag: str | None = None,
    category: Category | None = None,
) -> list[Topic]:
    """Fetch a topic listing. listing: top/hot/latest, optionally scoped by tag/category."""
    path = _feed_path(listing, page=page, period=period, order=order, limit=limit, tag=tag, category=category)
    data = _fetch_json(path)
    topics_raw = data.get("topic_list", {}).get("topics", [])
    return [Topic.from_dict(t) for t in topics_raw]


def fetch_topic_detail(topic_id: int, *, page: int = 1, include_raw: bool = True) -> dict:
    """Fetch a single topic with posts. include_raw asks Discourse for original markdown."""
    suffix = "&include_raw=true" if include_raw else ""
    return _fetch_json(f"/t/{topic_id}.json?page={page}{suffix}")


def _collect_raw_categories(raw: list[dict], acc: dict[int, dict]) -> None:
    """Flatten Discourse categories, descending into nested subcategory_list."""
    for c in raw:
        acc[c["id"]] = c
        subs = c.get("subcategory_list")
        if isinstance(subs, list):
            _collect_raw_categories(subs, acc)


def fetch_categories() -> list[Category]:
    """Fetch all categories (including subcategories), parent-linked."""
    data = _fetch_json_cached("/categories.json?include_subcategories=true", "categories")
    raw_list = data.get("category_list", {}).get("categories", [])
    acc: dict[int, dict] = {}
    _collect_raw_categories(raw_list, acc)
    return [
        Category(
            id=c["id"],
            name=c.get("name", ""),
            slug=c.get("slug", ""),
            topic_count=c.get("topic_count", 0),
            post_count=c.get("post_count", 0),
            description=c.get("description_text", ""),
            parent_id=(pid := c.get("parent_category_id")),
            parent_slug=acc.get(pid, {}).get("slug") if pid else None,
        )
        for c in acc.values()
    ]


def fetch_tags() -> list[Tag]:
    """Fetch all tags, ordered by topic count (desc)."""
    data = _fetch_json_cached("/tags.json", "tags")
    tags = [
        Tag(id=t["id"], name=t.get("name", str(t["id"])), slug=t.get("slug", ""), count=t.get("count", 0))
        for t in data.get("tags", [])
        if "id" in t
    ]
    tags.sort(key=lambda t: t.count, reverse=True)
    return tags


def _normalize(value: str) -> str:
    return " ".join(value.split()).lower()


def _match_category(cats: list[Category], value: str) -> Category | None:
    """Resolve a category by numeric id, slug, name, or parent/name path. Pure function."""
    raw = value.strip()
    if raw.isdigit():
        return next((c for c in cats if c.id == int(raw)), None)
    norm = _normalize(raw)
    return (
        next((c for c in cats if _normalize(c.slug) == norm), None)
        or next((c for c in cats if _normalize(c.name) == norm), None)
        or next(
            (c for c in cats if c.parent_slug and _normalize(f"{c.parent_slug}/{c.slug}") == norm),
            None,
        )
    )


def resolve_category(value: str) -> Category:
    """Resolve a user-supplied category (id/slug/name) to a Category, or raise."""
    match = _match_category(fetch_categories(), value)
    if not match:
        raise LinuxDoError(
            f"Unknown category: {value!r}.",
            exit_code=2,
            hint="Run `ldo categories` to list available categories.",
        )
    return match
