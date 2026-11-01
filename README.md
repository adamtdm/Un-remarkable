# Un-remarkable

A self-hosted, Dockerized cloud companion, dark mode web reader, and optimization engine purpose-built for **any reMarkable device** (reMarkable Paper Pro, reMarkable 2, and reMarkable 1).

Mirror your entire reMarkable cloud library locally without jailbreaking, modifying, or compromising tablet warranty. Browse notes with perceptual OKLCH dark mode, optimize massive comic EPUBs/PDFs into fast single-layer e-ink documents sized to your screen, search handwritten and typed notes with SQLite FTS5, and connect AI coding assistants directly via the Model Context Protocol (MCP).

---

## Key Features

- **Zero-Jailbreak Cloud Sync (`sync15`):** Continuous background synchronization with the official reMarkable cloud using WebSocket notifications and content-addressed blob storage.
- **Detailed Live Sync Monitor:** Real-time sync drawer with stage indicators, document and file progress, data transfer metrics, and session activity logs.
- **reMarkable Document & Comic Converter:** 5-stop quality slider converting heavy fixed-layout EPUBs, double-spread CBZ comics, and bulky PDFs into lean, single-layer PDFs sized to your device's native screen (Paper Pro Color Canvas, Paper Pro Move, RM2, RM1).
- **Perceptual OKLCH Dark Mode Reader:** Vector SVG renderer inverting background lightness while preserving color hues and highlights for natural night-time reading.
- **Selective Search & OCR Exclusions:** Recursive folder-level and document-level search exclusions so novels and comics don't pollute meeting notes and notebook search queries.
- **Full-Text Search (SQLite FTS5):** Instant full-text search across titles, tags, typed notes, and PDF text with search filtering (Notes only, All documents).
- **AI Assistant Integration (MCP):** Native Model Context Protocol server exposing read and write tools over Streamable HTTP (`/mcp`) and stdio for Claude Desktop, Antigravity, and Cursor.
- **Typed Notebook Editor & Markdown Import:** Create and type native reMarkable v6 `.rm` CRDT documents directly in your browser. Distraction-free Type Folio overlay in the reader and instant Markdown (`.md`) import.
- **Handwriting OCR & Task Intelligence:** Rule-based parser extracting tasks (`*`, `- [ ]`, `TODO:`) and Vision OCR support (Google Gemini / OpenAI / Ollama) consolidating to-dos across notebooks into a synced "Tasks" notebook.
- **Progressive Web App (PWA):** Installable standalone app on iOS, iPadOS, Android, and macOS with service worker offline shell and responsive touch controls.
- **Immutable Content-Addressed Store:** Files are stored by SHA-256 hash in `./data/blobs/`, retaining full version history and point-in-time snapshots.

---

## Supported reMarkable Devices & Specifications

Un-remarkable provides native hardware profiles and screen targets across all reMarkable devices:

| Device | Resolution & PPI | Display Technology | Profile Features |
|---|---|---|---|
| **reMarkable Paper Pro** | 2160 × 1620 (229 PPI) | Canvas Color (Gallery 3 E-Ink) | Full-color conversion, perceptual OKLCH dark mode, 1:1 pixel match |
| **reMarkable Paper Pro (Move / Landscape)** | 1620 × 2160 (229 PPI) | Canvas Color (Gallery 3 E-Ink) | Landscape / spread split orientation |
| **reMarkable 2** | 1872 × 1404 (226 PPI) | Canvas Monochrome E-Ink | High-contrast grayscale optimization, dithered shading, fast paging |
| **reMarkable 1** | 1872 × 1404 (226 PPI) | Canvas Monochrome E-Ink | Lean single-layer grayscale PDFs for original hardware |

All devices store notes using native `.rm` v6 binary stroke trees and typed text blocks in a merge-friendly format.

---

## Quick Start (Docker Compose)

The recommended setup is running the container 24/7 on a local home server or always-on laptop (e.g., Pop!_OS / Ubuntu with Docker).

### 1. Clone the repository
```bash
git clone https://github.com/adamtdm/Un-remarkable.git
cd Un-remarkable
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

## reMarkable Document & Comic Converter Guide

Heavy fixed-layout EPUBs (e.g. *The Boys*) and multi-gigabyte graphic novels often load and turn pages very slowly on e-ink tablets due to on-the-fly image scaling and HTML layout overhead.

The built-in converter optimizes documents into lean, single-layer PDFs matching the target reMarkable screen:

1. Click **⚡ Convert** in the top navigation or on any document card.
2. Select an existing library document or upload an external file (`.pdf`, `.epub`, `.cbz`).
3. Select your target device profile (**reMarkable Paper Pro**, **Paper Pro Move**, **reMarkable 2**, or **reMarkable 1**).
4. Choose your quality stop on the 5-stop slider:
   - **Stop 1 (Smallest):** Max 1600px, JPEG q65 (~75% reduction, fastest paging).
   - **Stop 2 (Compact):** Max 1920px, JPEG q72 (~65% reduction).
   - **Stop 3 (Balanced - Recommended):** 1:1 native device screen match, JPEG q82 (~50% reduction).
   - **Stop 4 (Sharp):** High-resolution rendering, JPEG q88 (~40% reduction, fine line art).
   - **Stop 5 (Best):** Maximum fidelity, JPEG q92 (~10% reduction, archival preservation).
5. Configure optional toggles:
   - **Split two-page spreads into separate pages:** Detects landscape double pages and splits them into two vertical portrait pages.
   - **Manga reading order (right-to-left):** Reverses split order for Japanese manga.
6. Click **Start Conversion**. Download the result directly or send it back to your tablet.

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
- `search`: Full-text search across titles, typed notes, PDF text, and tags.
- `get_document`: Inspect document details, tags, versions, and page manifests.
- `render_page`: Render any notebook page to vector SVG (with dark mode support).
- `get_sync_status`: Check current sync generation, progress, and blob store statistics.
- `list_tasks`: Query open or completed tasks consolidated from notebooks.
- `complete_task`: Mark an action item or task as completed.
- `create_notebook`: Create a new native reMarkable notebook with initial typed text.
- `append_task`: Add a task checkbox item to the synced "Tasks" notebook.
- `update_page_text`: Update or replace typed text on a specific page.
- `quick_capture`: Instantly capture an action item or dated note entry to your tablet.
- `list_folders`: Browse nested folder hierarchies with full breadcrumb paths and depth.
- `create_folder`: Create a new folder or nested subfolder in the library.
- `move_document`: Move any document or folder into any destination folder (with cycle prevention).
- `delete_document`: Delete any document or recursively delete a folder and all its contents.

---

## Nested Folder Management & File Organization

Organize documents with an authentic reMarkable folder structure:
- **Nested Subfolders:** Create folders inside folders to arbitrary depth (e.g. `Work > Projects > Q4`).
- **Ellipsis Menu & Mobile Bottom Action Sheet:** Tap or click the `•••` button on any notebook, PDF, or folder card to open the actions menu. On mobile, this smoothly slides up from the bottom as a native action sheet.
- **Move to Folder:** Select **📁 Add to Folder...** to move any item into any target folder via an interactive folder tree with real-time search. Cycle detection prevents moving a folder into itself or its own subfolders.
- **Delete / Trash:** Safely soft-delete files or entire nested folder trees with one click.

---

## Fullscreen Distraction-Free Reading Mode

Immerse yourself in documents and notes without toolbars or distractions:
- **Toggle Fullscreen:** Press <kbd>F</kbd> on desktop, click **⛶ Fullscreen** in the reader toolbar, or tap **⛶ Fullscreen Reading Mode** in the mobile options tray.
- **Auto-Hiding HUD:** The navigation header and page controls automatically glide off-screen after 2.5 seconds of inactivity. Moving your mouse or tapping the center reveals them instantly.
- **Edge Tap Navigation:**
  - **Left 25%:** Go to previous page.
  - **Middle 50%:** Toggle header HUD and controls.
  - **Right 25%:** Go to next page.
- **Instant Exit:** Press <kbd>Esc</kbd> or click the floating **✕ Exit Fullscreen** pill.

---

## Quick Capture (Desktop, Mobile & AI)

Never lose a fleeting thought or meeting to-do:
- **Global Shortcut:** Press <kbd>C</kbd> anywhere in the app (or click **⚡ Quick Capture** in the header) to open the capture modal.
- **Two Capture Modes:**
  - **☑ Task:** Formats the entry as an action item (`- [ ] ...`), saves it in the database, and appends it to your synced tablet "Tasks" notebook.
  - **📝 Quick Note:** Appends a timestamped note entry directly into your "Quick Notes" notebook.
- **Quick Submission:** Press <kbd>Ctrl</kbd>+<kbd>Enter</kbd> (or <kbd>Cmd</kbd>+<kbd>Enter</kbd>) to save immediately without leaving your current view.
- **Via MCP:** AI assistants can capture tasks and notes on your behalf using the `quick_capture` tool.

---

## Creation Split Button & Multi-File Bulk Import

Quickly create or upload content into your library:
- **Consolidated Creation Split Button:** Click **New Note** directly to start typing, or open the split arrow dropdown for **New Folder** and **Bulk Import Files**.
- **Multi-File Bulk Import:** Upload batches of PDF, EPUB, CBZ, and Markdown documents at once.
- **Hardware Optimization Target:** Choose your destination device profile during bulk import:
  - **reMarkable Paper Pro:** 2160×1620, Color Canvas canvas with 229 PPI resolution.
  - **reMarkable 2:** 1872×1404, Monochrome high-contrast grayscale.
  - **reMarkable 1:** 1872×1404, Monochrome.
  - **No conversion:** Preserves original file untouched.
- **Target Destination:** Choose any root or nested folder for the imported files.

---

## Universal Command Palette (Cmd+K / Ctrl+K)

Navigate and operate your companion with keyboard speed:
- Press <kbd>Cmd</kbd>+<kbd>K</kbd> (macOS) or <kbd>Ctrl</kbd>+<kbd>K</kbd> (Linux/Windows) anywhere in the application.
- **Instant Actions:** Trigger New Note, New Folder, Bulk Import, Quick Capture, Task Drawer, Sync Logs, Dark/Light Theme toggle, or Settings.
- **Real-Time Library Search:** Type any file or folder name to jump straight to it.
- **Keyboard Navigation:** Navigate results with <kbd>↑</kbd> and <kbd>↓</kbd>, hit <kbd>Enter</kbd> to execute, or press <kbd>Esc</kbd> to dismiss.

---

## Grid & List Views, Sorting and Folder Exports

- **View Mode Switching:** Toggle between thumbnail **Grid View** (`[ ⊞ ]`) and dense **List View** (`[ ☰ ]`) from the main toolbar.
- **List View Details:** View document type icons, titles, page counts, file sizes, last modified timestamps, and optimization badges in a clean responsive row layout.
- **Heavy File Indicators:** Files larger than 30MB or 150 pages display a `⚡ Needs Optimization` badge.
- **Folder ZIP Export:** Click the ellipsis `•••` on any folder (or tap on mobile) and select **Download Folder (ZIP)**. The companion recursively packages the folder and all subfolders into an archival ZIP archive in seconds.
- **Document PDF Export:** Download annotated vector PDFs with handwritten strokes or original documents directly.

---

## Blazing Fast Homepage Loading & Smart Thumbnail Caching

- **Dedicated Lightweight Thumbnails:** Generates ultra-compact 320×426 PNG previews (~15–25 KB) instead of downloading multi-megabyte full-resolution SVGs or high-DPI PDF pages.
- **Pre-Warmed Cache:** Whenever the background sync engine downloads a document from the cloud, it pre-renders both light and dark mode thumbnails to disk.
- **Immutable Content-Addressed ETags:** Thumbnails are versioned by document SHA-256 hash (`?h=...`), allowing browsers to cache them permanently (`Cache-Control: immutable`) and respond in < 1ms with HTTP 304 Not Modified.

---

## Typed Notebook Editor & Markdown Import

reMarkable Companion provides full native typing support generating authentic `.rm` v6 binary stroke and CRDT text trees:

1. **Creating a Notebook:**
   - Click **+ New Note** in the top navigation bar.
   - Enter a title and optional parent folder.
   - Type or paste notes or Markdown. Use `---` on a line by itself to create multi-page notebooks.
   - Click **Create Notebook**. The document is saved directly into the content-addressed blob store and indexed for search and task extraction.
2. **Distraction-Free Type Folio Overlay:**
   - When reading any notebook in the document reader, click **⌨ Type**.
   - An authentic typing panel opens alongside the page.
   - Type or edit notes freely. Click **Save & Apply** to re-render the page vector SVG and persist changes back to the reMarkable document tree.
3. **Importing Markdown Files:**
   - In the **+ New Note** modal, click **Choose .md file...** to load any Markdown document.
   - Markdown headers (`#`, `##`), bullet lists (`*`, `-`), and task checkboxes (`- [ ]`, `- [x]`) are preserved.

---

## Task Intelligence & Vision OCR

reMarkable Companion automatically finds action items and to-dos in your notebooks:

- **Rule-Based Extraction:** Scans typed text for checkboxes (`- [ ]`, `[ ]`), asterisks (`*`), and `TODO:` / `FIXME:` tags.
- **Vision OCR for Handwriting:** Connect Google Gemini (`gemini-2.0-flash` recommended) or OpenAI/Ollama compatible endpoints in **⚙️ Settings** to transcribe handwritten margin notes, starred action items, and circled tasks.
- **Task Consolidation:**
  - Click **☑ Tasks** in the header to review all discovered open and completed tasks across all documents.
  - Click **📓 Sync to 'Tasks' Notebook** to automatically assemble a master checklist notebook that syncs to your tablet.
  - Add quick tasks directly using the top input field.

---

## Mobile PWA & Remote Access (Tailscale)

### Install as a Mobile App (PWA)
reMarkable Companion is a Progressive Web App with service worker caching:
- **iPhone / iPad:** Open the web UI in Safari, tap **Share (square with arrow)**, and tap **Add to Home Screen**.
- **Android:** Open in Chrome and tap the **Install app** or **Add to Home screen** banner.
- **Desktop (macOS / Windows / Linux):** Click the install icon in Chrome or Edge address bar to run as a standalone window.

### Remote Access via Tailscale (Zero Port-Forwarding)
To securely access your companion and sync from outside your home without exposing ports to the public internet:

1. Install Tailscale on the host machine running reMarkable Companion:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
2. Install the Tailscale app on your iPhone, iPad, Android phone, or laptop and log into the same account.
3. Access your companion directly via your host's Tailscale IP or MagicDNS hostname:
   ```
   http://remarkable-server.your-tailnet.ts.net:8099
   ```
4. All traffic is end-to-end encrypted with WireGuard.

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
