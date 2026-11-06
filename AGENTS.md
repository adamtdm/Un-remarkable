# Un-remarkable (remarkable)

Self-hosted cloud companion, dark mode web reader, and optimization engine for reMarkable devices (Paper Pro, RM2, RM1).
See [README.md](README.md) for full architecture and user docs.

## Tech Stack & Architecture
- **Backend**: Python 3.11+, FastAPI / Uvicorn, asyncio
- **Sync Engine**: `sync15` WebSocket & REST sync with official reMarkable cloud (`internal.cloud.remarkable.com`)
- **Storage**: Content-addressed SHA-256 blob storage (`./data/blobs/`) and SQLite with FTS5 search
- **Document Engine**: PyMuPDF (`fitz`), OKLCH perceptual dark mode vector SVG renderer, native `.rm` v6 binary stroke parser
- **AI Integration**: Native Model Context Protocol (MCP) server running on `/mcp` and stdio
- **Deployment**: Docker / Docker Compose (`docker compose up -d`)

## Development & Test Commands
- **Run Locally**: `.venv/bin/rmcompanion run` (http://localhost:8099; data in `./data`)
- **Deploy changes to the Docker instance**: `docker compose up -d --build` (the image copies `src/` at build time)
- **Run Tests**: `.venv/bin/pytest tests/`
- **Format / Lint**: `.venv/bin/ruff check src tests`
- **Frontend cache busting**: bump the `?v=` query on `app.js` / `style.css` in `web/static/index.html` after editing them
