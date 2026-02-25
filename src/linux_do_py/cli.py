"""CLI for browsing linux.do forum."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated

import typer
from markdownify import markdownify
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .api import fetch_categories, fetch_topic_detail, fetch_topics

app = typer.Typer(help="linux.do CLI — browse the forum from your terminal")
console = Console()


def _relative_time(iso: str) -> str:
    """Convert ISO timestamp to relative time string."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{secs // 60}m"
        if secs < 86400:
            return f"{secs // 3600}h"
        return f"{secs // 86400}d"
    except (ValueError, TypeError):
        return iso[:10]


def _format_count(n: int) -> str:
    if n >= 10000:
        return f"{n / 1000:.1f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _render_topics(topics: list, title: str, limit: int) -> None:
    table = Table(title=title, show_lines=False, pad_edge=False, expand=True)
    table.add_column("ID", style="cyan", width=7, justify="right")
    table.add_column("Title", ratio=3)
    table.add_column("Views", justify="right", width=7)
    table.add_column("Likes", justify="right", width=7, style="red")
    table.add_column("Replies", justify="right", width=7)
    table.add_column("Activity", justify="right", width=8)

    for t in topics[:limit]:
        title_text = Text(t.title, overflow="ellipsis", no_wrap=True)
        if t.pinned:
            title_text.stylize("bold yellow")
        if t.tags:
            tag_str = " ".join(f"[{tag}]" for tag in t.tags[:3])
            title_text.append(f" {tag_str}", style="dim cyan")

        table.add_row(
            str(t.id),
            title_text,
            _format_count(t.views),
            _format_count(t.like_count),
            _format_count(t.reply_count),
            _relative_time(t.last_posted_at),
        )

    console.print(table)
    console.print("\n[dim]Tip: ldo read <ID> to read a topic[/dim]")


@app.command()
def top(
    period: Annotated[
        str, typer.Option("-p", "--period", help="Period: daily/weekly/monthly/quarterly/yearly/all")
    ] = "weekly",
    page: Annotated[int, typer.Option("--page", help="Page number (0-based)")] = 0,
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of topics to show")] = 30,
) -> None:
    """Show top topics."""
    with console.status("Fetching top topics..."):
        topics = fetch_topics("top", page=page, period=period)
    _render_topics(topics, f"Top Topics ({period})", limit)


@app.command()
def hot(
    page: Annotated[int, typer.Option("--page", help="Page number (0-based)")] = 0,
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of topics to show")] = 30,
) -> None:
    """Show hot topics."""
    with console.status("Fetching hot topics..."):
        topics = fetch_topics("hot", page=page)
    _render_topics(topics, "Hot Topics", limit)


@app.command()
def latest(
    order: Annotated[str, typer.Option("-o", "--order", help="Order: created/activity/views/posts/likes")] = "activity",
    page: Annotated[int, typer.Option("--page", help="Page number (0-based)")] = 0,
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of topics to show")] = 30,
) -> None:
    """Show latest topics."""
    with console.status("Fetching latest topics..."):
        topics = fetch_topics("latest", page=page, order=order)
    _render_topics(topics, "Latest Topics", limit)


@app.command()
def categories() -> None:
    """List all categories."""
    with console.status("Fetching categories..."):
        cats = fetch_categories()

    table = Table(title="Categories", expand=True)
    table.add_column("ID", width=5, justify="right")
    table.add_column("Name", ratio=1)
    table.add_column("Slug", ratio=1, style="dim")
    table.add_column("Topics", justify="right", width=8)
    table.add_column("Posts", justify="right", width=10)

    for c in cats:
        table.add_row(
            str(c.id),
            c.name,
            c.slug,
            _format_count(c.topic_count),
            _format_count(c.post_count),
        )

    console.print(table)


@app.command()
def read(
    topic_id: Annotated[int, typer.Argument(help="Topic ID to read")],
    page: Annotated[int, typer.Option("--page", help="Page number (1-based)")] = 1,
    limit: Annotated[int, typer.Option("-n", "--limit", help="Max posts to show")] = 10,
) -> None:
    """Read a topic's posts."""
    with console.status(f"Fetching topic {topic_id}..."):
        data = fetch_topic_detail(topic_id, page=page)

    title = data.get("title", "Unknown")
    posts = data.get("post_stream", {}).get("posts", [])

    console.print(
        Panel(
            f"[bold]{title}[/bold]\n[dim]https://linux.do/t/topic/{topic_id} | Page {page}[/dim]",
            border_style="blue",
        )
    )

    for post in posts[:limit]:
        username = post.get("username", "?")
        created = _relative_time(post.get("created_at", ""))
        post_num = post.get("post_number", 0)
        likes = post.get("like_count", 0)

        cooked = post.get("cooked", "")
        # Convert HTML to readable text
        text = markdownify(cooked, strip=["img"]).strip()
        # Remove leftover image links: [text](url "title") pointing to uploads
        text = re.sub(r"\[([^\]]*?\d+[×x]\d+[^\]]*?)\]\([^)]+\)", r"[image]", text)
        text = re.sub(r"\[\s*\]\([^)]+\)", "", text)
        # Remove bare parenthesized URLs from stripped images
        text = re.sub(r"\n\s*\(https?://linux\.do/uploads/[^)]+\)\s*\n", "\n", text)
        # Collapse excessive newlines
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        header = f"[bold cyan]#{post_num}[/bold cyan] [bold]{username}[/bold] [dim]{created} ago[/dim]"
        if likes:
            header += f" [red]♥ {likes}[/red]"

        console.print(f"\n{header}")
        console.print(text)
        console.print("[dim]─" * min(console.width, 80) + "[/dim]")


if __name__ == "__main__":
    app()
