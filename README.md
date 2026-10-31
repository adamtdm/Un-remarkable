# reMarkable Companion

A self-hosted, Dockerized cloud companion, dark mode web reader, and optimization engine purpose-built for the **reMarkable Paper Pro** (and reMarkable 2).

Mirror your entire reMarkable cloud library locally without jailbreaking, modifying, or compromising tablet warranty. Browse notes with perceptual OKLCH dark mode, optimize massive comic EPUBs/PDFs into fast single-layer 229 PPI e-ink documents, search handwritten and typed notes with SQLite FTS5, and connect AI coding assistants directly via the Model Context Protocol (MCP).

---

## Key Features

- **Zero-Jailbreak Cloud Sync (`sync15`):** Continuous background synchronization with the official reMarkable cloud using WebSocket notifications and content-addressed blob storage.
- **Detailed Live Sync Monitor:** Real-time sync drawer with stage indicators, document and file progress, data transfer metrics, and session activity logs.
- **Paper Pro Document & Comic Converter:** 5-stop quality slider converting heavy fixed-layout EPUBs, double-spread CBZ comics, and bulky PDFs into lean, single-layer 2160×1620 PDFs sized exactly to the Paper Pro's 229 PPI screen.
- **Perceptual OKLCH Dark Mode Reader:** Vector SVG renderer inverting background lightness while preserving color hues and highlights for natural night-time reading.
- **Selective Search & OCR Exclusions:** Recursive folder-level and document-level search exclusions so novels and comics don't pollute meeting notes and notebook search queries.
- **Full-Text Search (SQLite FTS5):** Instant full-text search across titles, tags, typed notes, and PDF text with search filtering (Notes only, All documents).
- **AI Assistant Integration (MCP):** Native Model Context Protocol server exposing read tools over Streamable HTTP (`/mcp`) and stdio for Claude Desktop, Antigravity, and Cursor.
- **Immutable Content-Addressed Store:** Files are stored by SHA-256 hash in `./data/blobs/`, retaining full version history and point-in-time snapshots.

---

## Paper Pro Screen Specifications

| Parameter | Specification | Why it matters |
|---|---|---|
| **Resolution** | 2160 × 1620 pixels (portrait: 1620 × 2160) | 1:1 pixel match ceiling for the converter engine |
| **Density** | 229 PPI (Pixels Per Inch) | Crisp text and comic line art without bloated file size |
| **Color Tech** | Canvas Color (Gallery 3 E-Ink) | Perceptual OKLCH inversion preserves colored inks and highlighters |
| **File Format** | `.rm` v6 binary stroke trees | Stores stroke vectors and typed text blocks in a merge-friendly format |

---

## Quick Start (Docker Compose)

The recommended setup is running the container 24/7 on a local home server or always-on laptop (e.g., Pop!_OS / Ubuntu with Docker).

### 1. Clone the repository
```bash
git clone https://github.com/adamtdm/remarkable.git
cd remarkable
```

### 2. Configure Environment (Optional)
The default configuration works out of the box with persistent storage in `./data`. You can customize settings via `.env`:
```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8099` | Web UI and REST API port |
| `RM_DATA_DIR` | `/data` | Path to data directory (mounted in Docker) |
| `RM_SYNC_INTERVAL_SECONDS` | `120` | Interval between background cloud sync checks |
| `RM_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### 3. Start the Service
```bash
docker compose up -d
```
Check health:
```bash
docker compose ps
curl http://localhost:8099/api/status
```

### 4. Link Your reMarkable Account
1. Open `http://<server-ip>:8099` in your web browser.
2. Click **Connect** in the banner or navigation bar.
3. Open [my.remarkable.com/device/browser/connect](https://my.remarkable.com/device/browser/connect) (or [my.remarkable.com/device/desktop/connect](https://my.remarkable.com/device/desktop/connect)).
4. Generate an 8-character one-time pairing code.
5. Enter the code in the companion web UI and click **Pair Device**.
6. The companion exchanges the code for a device token, initializes the local blob store, and begins mirroring your cloud library.

---

## Paper Pro Converter Guide

Heavy fixed-layout EPUBs (e.g. *The Boys*) and multi-gigabyte graphic novels often load and turn pages very slowly on e-ink tablets due to on-the-fly image scaling and HTML layout overhead.

The built-in converter optimizes documents into lean, single-layer PDFs matching the Paper Pro screen:

1. Click **⚡ Convert** in the top navigation or on any document card.
2. Select an existing library document or upload an external file (`.pdf`, `.epub`, `.cbz`).
3. Choose your quality stop on the 5-stop slider:
   - **Stop 1 (Smallest):** Max 1600px, JPEG q65 (~75% reduction, fastest paging).
   - **Stop 2 (Compact):** Max 1920px, JPEG q72 (~65% reduction).
   - **Stop 3 (Balanced - Recommended):** 1:1 native 2160×1620 match at 229 PPI, JPEG q82 (~50% reduction).
   - **Stop 4 (Sharp):** Max 2560px, JPEG q88 (~40% reduction, fine line art).
   - **Stop 5 (Best):** Max 3000px, JPEG q92 (~10% reduction, archival preservation).
4. Configure optional toggles:
   - **Split two-page spreads into separate pages:** Detects landscape double pages and splits them into two vertical portrait pages.
   - **Manga reading order (right-to-left):** Reverses split order for Japanese manga.
5. Click **Start Conversion**. Download the result directly or send it back to your tablet.

---

## AI Assistant Integration (Model Context Protocol)

reMarkable Companion provides a native MCP server for integration with LLM assistants like Claude, Antigravity, and Cursor.

### Streamable HTTP (Remote / Tailscale / Antigravity)
Add the HTTP endpoint to your MCP configuration:
```
http://<server-ip>:8099/mcp
```

### Claude Desktop (Local or Docker stdio)
Add the server to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "remarkable": {
      "command": "docker",
      "args": ["exec", "-i", "rmcompanion", "rmcompanion", "mcp"]
    }
  }
}
```

### Available MCP Tools
- `list_documents`: Browse folders and list documents with metadata, page counts, and exclusion status.
- `search_library`: Full-text search across titles, typed notes, PDF text, and tags.
- `get_document`: Inspect document details, tags, versions, and page manifests.
- `render_page`: Render any notebook page to vector SVG (with dark mode support).
- `get_sync_status`: Check current sync generation, progress, and blob store statistics.

---

## Architecture & Storage Layout

```
data/
├── blobs/                  # Content-addressed immutable file store
│   └── aa/
│       └── bb/
│           └── aabb...     # SHA-256 hashed files (PDFs, .rm strokes, .content)
├── cache/                  # Temporary rendered previews and converted PDFs
│   └── converted/          # Evicted dynamically (retains last 20 jobs)
└── db/
    └── library.db          # SQLite 3 metadata database + FTS5 search index
```

### Key Components
- `rmcompanion.cloud`: Async HTTP client implementing the reMarkable `sync15` sync protocol, token exchange, and signed download URL resolution.
- `rmcompanion.sync`: Background sync loop with real-time state tracking, Merkle tree root hash verification, and delta updates.
- `rmcompanion.render`: Vector `.rm` v6 stroke parser with OKLCH perceptual dark mode lightness inversion.
- `rmcompanion.converter`: Multi-threaded PyMuPDF comic conversion engine with memory-mapped streaming.
- `rmcompanion.web`: FastAPI REST API, static asset server, and interactive dark web UI.
- `rmcompanion.mcp`: Streamable HTTP and stdio Model Context Protocol server.

---

## Local Development & Testing

### Prerequisites
- Python 3.12+
- `libmupdf-dev` or binary wheels for PyMuPDF

### Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run Test Suite
```bash
pytest -v
```

### Run Server Locally
```bash
rmcompanion run --port 8099
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
