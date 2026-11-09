# Un-remarkable

A self-hosted, Dockerized cloud companion, dark mode web reader, and optimization engine purpose-built for **any reMarkable device** (reMarkable Paper Pro, reMarkable 2, and reMarkable 1).

Mirror your entire reMarkable cloud library locally without jailbreaking, modifying, or compromising tablet warranty. Browse notes with perceptual OKLCH dark mode, optimize massive comic EPUBs/PDFs into fast single-layer e-ink documents sized to your screen, search handwritten and typed notes with SQLite FTS5, and connect AI coding assistants directly via the Model Context Protocol (MCP).

---

## Key Features

- **Zero-Jailbreak Cloud Sync (`sync15`):** Continuous background synchronization with the official reMarkable cloud (polls for changes every 2 minutes by default) with content-addressed blob storage.
- **Detailed Live Sync Monitor:** Real-time sync drawer with stage indicators, document and file progress, data transfer metrics, and session activity logs.
- **reMarkable Document & Comic Converter:** 5-stop quality slider converting heavy fixed-layout EPUBs, double-spread CBZ comics, and bulky PDFs into lean, single-layer PDFs sized to your device's native screen (Paper Pro Color Canvas, Paper Pro Move, RM2, RM1).
- **Perceptual OKLCH Dark Mode Reader:** Vector SVG renderer inverting background lightness while preserving color hues and highlights for natural night-time reading.
- **Reader That Remembers Each Book:** Table of contents, bookmarks, a page scrubber, two-page spreads (with the cover on its own if you like) and right-to-left manga reading, all saved per book. A Continue Reading shelf picks up where you left off on the tablet or in the browser.
- **Highlights:** Everything you highlight on the tablet, per book or across the library, searchable and exportable as Markdown.
- **Selective Search & OCR Exclusions:** Recursive folder-level and document-level search exclusions so novels and comics don't pollute meeting notes and notebook search queries.
- **Full-Text Search (SQLite FTS5):** Instant full-text search across titles, tags, typed notes, and PDF text with search filtering (Notes only, All documents).
- **AI Assistant Integration (MCP):** Native Model Context Protocol server exposing read and write tools over Streamable HTTP (`/mcp`) and stdio for Claude Desktop, Antigravity, and Cursor.
- **Typed Notebook Editor & Markdown Import:** Create and type native reMarkable v6 `.rm` CRDT documents directly in your browser. Distraction-free Type Folio overlay in the reader and instant Markdown (`.md`) import.
- **Handwriting OCR & Task Intelligence:** Rule-based parser extracting tasks (`*`, `- [ ]`, `TODO:`) and Vision OCR support (Google Gemini / OpenAI / Ollama) consolidating to-dos across notebooks into a synced "Tasks" notebook.
- **Progressive Web App (PWA):** Installable standalone app on iOS, iPadOS, Android, and macOS with responsive touch controls.
- **Immutable Content-Addressed Store:** Files are stored by SHA-256 hash in `./data/blobs/`, retaining full version history and point-in-time snapshots.

---

## Feature Comparison: Official reMarkable Web vs. Un-remarkable

| Feature / Capability | Official reMarkable Web (`my.remarkable.com`) | Un-remarkable Companion |
|---|:---:|:---:|
| **Hosting & Data Ownership** | Proprietary cloud (subscription-based Connect plan) | 100% Self-Hosted Docker container; full local data sovereignty |
| **Local Offline Storage** | Temporary browser session cache | Content-addressed immutable blob store (`./data/blobs/`) with point-in-time versioning |
| **Two-Way Cloud Sync (`sync15`)** | Official cloud sync | Direct `sync15` sync with root hash change detection & 2-way notebook pushes |
| **Live Sync Drawer & Transfer Metrics** | Simple spinner icon | Real-time stage indicators, file progress, transfer rates, and session activity logs |
| **Dark Mode Reader** | Light mode only (blinding white background) | Perceptual OKLCH dark mode (inverts lightness while preserving color highlighter hues) |
| **Fullscreen Distraction-Free Mode** | Standard browser view with browser Chrome | Dedicated HUD with auto-hide timer, exit pill, and edge tap zones (Prev / Menu / Next) |
| **Reader Navigation & Quick Page Jump** | Step forward / back buttons | Prev/Next chevrons, interactive click-to-jump pill (`inputmode="numeric"`), and <kbd>g</kbd> shortcut |
| **Comic & Document Optimization Engine** | None (uploads files as-is; heavy files lag on device) | Built-in 5-stop PyMuPDF optimizer for PDF, EPUB, and CBZ tuned for Paper Pro, RM2, and RM1 |
| **Double-Spread Comic Split & Manga RTL** | None | Automatic landscape spread splitting and optional Right-to-Left manga paging order |
| **Hardware Screen Profiles** | None | Native 1:1 hardware targets (Paper Pro 2160×1620 Color, RM2 1872×1404, RM1) |
| **Full-Text Search (FTS5)** | Limited title and cloud OCR search | Instant local SQLite FTS5 search across titles, tags, typed text, and PDF contents |
| **Selective Search & OCR Exclusions** | None (all or nothing) | Recursive folder and document exclusions (exclude comics/novels from body search and OCR) |
| **Native Typed Notebook Creation** | Basic typed text (Connect subscription required) | Native `.rm` v6 binary stroke/CRDT generator; multi-page support using `---` dividers |
| **Markdown (`.md`) Import** | None | Instant `.md` upload preserving headings, bullet points, and task checkboxes |
| **Type Folio Drawer in Reader** | Edit mode switch | Seamless side drawer overlay allowing typing alongside notes with instant SVG preview |
| **Automated Task Extraction** | None | Scans notebooks for checkboxes (`- [ ]`, `[ ]`), asterisks (`*`), and `TODO:` items |
| **Vision OCR for Handwritten Tasks** | Cloud text conversion (full page only) | Multimodal Vision OCR (Gemini 2.0 Flash, OpenAI, Ollama) extracting handwritten tasks |
| **Consolidated "Tasks" Tablet Notebook** | None | One-click or automated sync assembling a master checklist notebook pushed to your tablet |
| **AI Assistant Integration (MCP)** | None | Built-in Model Context Protocol server (stdio & `/mcp` HTTP) for Claude, Antigravity, and Cursor |
| **Automated Digests, RSS & Crosswords** | None (manual upload required) | Built-in configuration guide & delivery triggers for Goosepaper, RSS feeds, and daily crosswords |
| **Folder Organization & Drag-and-Drop** | Basic web move dialogue | Desktop drag-and-drop file organization, nested breadcrumbs, and cycle prevention |
| **Ellipsis Actions & Mobile Sheet** | Standard dropdown menu | Responsive ellipsis menu with native mobile bottom slide-up sheet |
| **Folder ZIP & Document PDF Export** | Single document PDF export | Recursive folder ZIP packaging and single document annotated vector PDF downloads |
| **Universal Command Palette** | None | Global <kbd>Cmd</kbd>+<kbd>K</kbd> / <kbd>Ctrl</kbd>+<kbd>K</kbd> palette for instant navigation, search, and action execution |
| **Thumbnail Performance** | On-demand cloud previews | Pre-warmed 320×426 PNG thumbnails with immutable SHA-256 ETags (< 1ms cache hits) |
| **Mobile & Foldable Display Optimization** | Standard responsive web | PWA standalone app, safe area padding, and responsive scaling tested on Samsung Fold |
| **Secure Remote Access** | Official cloud login | Zero-port-forwarding WireGuard access via Tailscale or local network |

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
| `RMC_PORT` | `8099` | Host port for the web UI, REST API and MCP endpoint |
| `RMC_SYNC_INTERVAL_SECONDS` | `120` | Interval between background cloud sync checks |
| `RMC_MAX_CONCURRENT_DOWNLOADS` | `6` | Parallel blob downloads during sync |
| `RMC_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `OPENAI_BASE_URL` | – | Optional Vision OCR provider keys (can also be set in Settings) |

Data is stored in `./data` next to `docker-compose.yml` (mounted at `/data` in the container).

### Security model
There is no login. Anyone who can reach the port can read and change your library, so only expose it on your home network or tailnet, never the public internet. Other websites you visit cannot use it: the server sends no CORS headers (so other sites can't read responses) and rejects writes that the browser marks as cross-site.

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

Un-remarkable provides a native MCP server for integration with LLM assistants like Claude, Antigravity, and Cursor.

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
- `get_page_text`: Read the typed or indexed text of a page.
- `get_page_image`: Render a page to an image (with dark mode support).
- `recent_changes`: List recently modified documents.
- `sync_status`: Check current sync generation, last sync time, and blob store statistics.
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

Un-remarkable provides full native typing support generating authentic `.rm` v6 binary stroke and CRDT text trees:

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

Write `*` before a task anywhere in your handwritten notes, and it shows up in one **Tasks** notebook on your tablet.

- **Handwritten `*` tasks (Vision OCR):** Connect Google Gemini (`gemini-flash-lite-latest` recommended) or an OpenAI/Ollama-compatible endpoint in **⚙️ Settings**. After each sync, only the pages whose handwriting changed are read, so cost stays proportional to what you write. A task runs from the `*` to the next `*`, the end of the sentence, or the end of the line. Cross a task out on the page and it is marked done on the next sync.
- **Typed tasks:** Typed text is also scanned for `*`, checkboxes (`- [ ]`) and `TODO:`.
- **One Tasks notebook:** Open tasks are written into a single native notebook, grouped under the notebook each task came from, across as many pages as needed. The notebook keeps the same ID, so the tablet copy is updated in place, never duplicated. It is generated: anything you write on it on the tablet is replaced on the next update. To finish a task, tick it in **☑ Tasks** in the web UI (or via MCP), or cross it out where you wrote it.
- **Capture:** Quick Capture and the Tasks drawer input add a task straight to the notebook (under "Captured").
- **First run:** The first sync of a library does not OCR anything. To pick up `*` tasks you already wrote, click **Scan Documents** in the Tasks drawer, then **📓 Sync to 'Tasks' Notebook**.

---

## Mobile PWA & Remote Access (Tailscale)

### Install as a Mobile App (PWA)
Un-remarkable is an installable Progressive Web App:
- **iPhone / iPad:** Open the web UI in Safari, tap **Share (square with arrow)**, and tap **Add to Home Screen**.
- **Android:** Open in Chrome and tap the **Install app** or **Add to Home screen** banner.
- **Desktop (macOS / Windows / Linux):** Click the install icon in Chrome or Edge address bar to run as a standalone window.

### Remote Access via Tailscale (Zero Port-Forwarding)
To securely access your companion and sync from outside your home without exposing ports to the public internet:

1. Install Tailscale on the host machine running Un-remarkable:
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
- `rmcompanion.sync`: Background sync loop with real-time state tracking, root hash change detection, and per-document delta updates.
- `rmcompanion.render`: Vector `.rm` v6 stroke parser with OKLCH perceptual dark mode lightness inversion.
- `rmcompanion.converter`: PyMuPDF conversion engine for PDF, EPUB and CBZ (runs in background jobs).
- `rmcompanion.web`: FastAPI REST API, static asset server, and interactive dark web UI.
- `rmcompanion.mcp`: Streamable HTTP and stdio Model Context Protocol server.

---

## Local Development & Testing

### Prerequisites
- Python 3.11+
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
