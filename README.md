# ldo

CLI for [linux.do](https://linux.do) forum.

## Setup

```bash
uv sync
```

## Usage

```bash
uv run ldo top                   # weekly top topics
uv run ldo top -p daily -n 10    # daily top, 10 items
uv run ldo hot                   # hot topics
uv run ldo latest                # latest by activity
uv run ldo latest -o views       # latest by views
uv run ldo categories            # list categories (incl. subcategories)
uv run ldo tags                  # list tags by topic count
uv run ldo read 482293           # read topic posts (original markdown)
uv run ldo read 482293 --page 2  # page 2

# Filter any feed by tag or category (id / slug / name)
uv run ldo latest --tag chatgpt
uv run ldo hot --category develop
uv run ldo top --category resource/cloud-asset --tag ssl

# JSON output (each row includes a `url`)
uv run ldo --json hot -n 5
```

## Notes

- **No login required** — uses `curl_cffi` Chrome impersonation for public read access.
- **Original markdown** — `read` requests Discourse `raw` posts, falling back to HTML→markdown.
- **Rate limits** — anonymous access is throttled; on HTTP 429 the CLI prints a clear
  message and exits `75` (instead of a traceback). Auth-walled content exits `77`.
- **Caching** — `categories`/`tags` metadata is cached under `~/.cache/linux-do-py/`
  for 24h (also speeds up `--category` resolution).

## Development

```bash
uv run ruff format . && uv run ruff check --fix .
uv run pytest
```
