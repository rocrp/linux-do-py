# ldo

CLI for [linux.do](https://linux.do) forum.

## Setup

Requires [localwebpy](https://github.com/user/localwebpy) at `~/w/localwebpy` for Cloudflare bypass.

```bash
uv sync
```

## Usage

```bash
uv run ldo top                  # weekly top topics
uv run ldo top -p daily -n 10  # daily top, 10 items
uv run ldo hot                  # hot topics
uv run ldo latest               # latest by activity
uv run ldo latest -o views      # latest by views
uv run ldo categories           # list categories
uv run ldo read 482293          # read topic posts
uv run ldo read 482293 --page 2 # page 2
```
