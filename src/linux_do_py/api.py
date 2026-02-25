"""Fetch data from linux.do Discourse API via localwebpy (Cloudflare bypass)."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

BASE_URL = "https://linux.do"
LOCALWEBPY_DIR = str(Path.home() / "w" / "localwebpy")


def _find_uv() -> str:
    uv = shutil.which("uv")
    if not uv:
        msg = "uv not found in PATH"
        raise RuntimeError(msg)
    return uv


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


def _fetch_json(path: str) -> dict:
    """Fetch JSON from linux.do via localwebpy browser fallback."""
    url = f"{BASE_URL}{path}"
    result = subprocess.run(
        [
            _find_uv(),
            "run",
            "--directory",
            LOCALWEBPY_DIR,
            "localwebpy",
            "visit",
            url,
            "-c",
            "300",
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        msg = f"Failed to fetch {url}: {result.stderr}"
        raise RuntimeError(msg)

    raw = result.stdout
    # localwebpy outputs metadata lines before JSON — find the JSON start
    for i, line in enumerate(raw.split("\n")):
        stripped = line.strip()
        if stripped.startswith("{"):
            json_text = "\n".join(raw.split("\n")[i:])
            return json.loads(json_text)

    msg = f"No JSON found in response from {url}"
    raise RuntimeError(msg)


def fetch_topics(
    listing: str = "top",
    *,
    page: int = 0,
    period: str = "weekly",
    order: str | None = None,
    category_slug: str | None = None,
    category_id: int | None = None,
) -> list[Topic]:
    """Fetch topic listing. listing: top/hot/latest"""
    if category_slug and category_id:
        path = f"/c/{category_slug}/{category_id}/l/{listing}.json?"
    else:
        path = f"/{listing}.json?"

    params = [f"page={page}"]
    if listing == "top":
        params.append(f"period={period}")
    if order:
        params.append(f"order={order}")
    path += "&".join(params)

    data = _fetch_json(path)
    topics_raw = data.get("topic_list", {}).get("topics", [])
    return [Topic.from_dict(t) for t in topics_raw]


def fetch_topic_detail(topic_id: int, *, page: int = 1) -> dict:
    """Fetch single topic with posts."""
    return _fetch_json(f"/t/{topic_id}.json?page={page}")


def fetch_categories() -> list[Category]:
    """Fetch all categories."""
    data = _fetch_json("/categories.json")
    cats = data.get("category_list", {}).get("categories", [])
    return [
        Category(
            id=c["id"],
            name=c["name"],
            slug=c["slug"],
            topic_count=c.get("topic_count", 0),
            post_count=c.get("post_count", 0),
            description=c.get("description_text", ""),
        )
        for c in cats
    ]
