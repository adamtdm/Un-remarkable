# reMarkable Companion

A self-hosted, Dockerized companion for the **reMarkable Paper Pro** (and reMarkable 2).

- **Continuous Cloud Sync:** Mirrors your library locally without jailbreaking or modifying the tablet.
- **Immutable Version History:** Keeps full historical snapshots of documents and past revisions using content hashes.
- **Smart Dark Mode Reader:** High-contrast reading with perceptual color mapping (lightness inverted in OKLCH, vibrant hues preserved, photos and figures untouched).
- **Model Context Protocol (MCP):** Connect Claude, Antigravity, or other AI assistants directly to your notebooks, handwritten notes, and PDFs via Streamable HTTP (`/mcp`) or stdio.

---

## Quick Start (Docker)

1. **Start the container:**
   ```bash
   docker compose up -d
   ```

2. **Open the Web UI:**
   Navigate to `http://<laptop-ip>:8099` (or `http://localhost:8099`).

3. **Link your reMarkable account:**
   - Click **Connect** in the top bar.
   - Go to [my.remarkable.com/device/browser/connect](https://my.remarkable.com/device/browser/connect) and generate an 8-character code.
   - Enter the code to pair. Your library will immediately begin syncing.

---

## AI Assistant Integration (MCP)

### Streamable HTTP (Claude Code / Antigravity / Remote)
Connect your AI client to:
```
http://<laptop-ip>:8099/mcp
```

### Claude Desktop (stdio)
Add the following to your `claude_desktop_config.json`:
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
- `list_documents`: Browse folders and list documents.
- `search`: Search across notebook titles, typed text, tags, and PDF text.
- `get_document`: View document metadata and pages.
- `get_page_text`: Read typed notes or text layers.
- `get_page_image`: Render high-resolution PNG of a handwritten page for AI vision inspection and handwriting OCR.
- `recent_changes`: List recently edited documents.
- `sync_status`: View sync state and generation.

---

## Local Development (without Docker)

```bash
# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Start server
rmcompanion run --port 8099
```
