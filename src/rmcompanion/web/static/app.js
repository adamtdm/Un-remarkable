// reMarkable Companion Web UI Client

const state = {
  currentFolder: "",
  folderPath: [{ id: "", name: "Home" }],
  currentFilter: "",
  currentDoc: null,
  currentPageIdx: 0,
  pageDarkMode: true,
  fitMode: "fit-page",
  appTheme: localStorage.getItem("rmc_theme") || "dark",
};

// --- DOM Elements ---
const el = {
  syncBadge: document.getElementById("sync-badge"),
  syncText: document.getElementById("sync-text"),
  btnSyncNow: document.getElementById("btn-sync-now"),
  btnThemeToggle: document.getElementById("btn-theme-toggle"),
  authBanner: document.getElementById("auth-banner"),
  btnAuthOpen: document.getElementById("btn-auth-open"),
  btnBannerConnect: document.getElementById("btn-banner-connect"),
  authModal: document.getElementById("auth-modal"),
  authCodeInput: document.getElementById("auth-code-input"),
  authError: document.getElementById("auth-error"),
  btnAuthSubmit: document.getElementById("btn-auth-submit"),
  btnAuthCancel: document.getElementById("btn-auth-cancel"),
  breadcrumbs: document.getElementById("breadcrumbs"),
  docGrid: document.getElementById("doc-grid"),
  filterTabs: document.querySelectorAll(".filter-tab"),
  searchInput: document.getElementById("search-input"),
  searchDropdown: document.getElementById("search-dropdown"),
  brandHome: document.getElementById("brand-home"),
  // Reader elements
  readerView: document.getElementById("reader-view"),
  readerTitle: document.getElementById("reader-title"),
  readerPageIndicator: document.getElementById("reader-page-indicator"),
  btnPagePrev: document.getElementById("btn-page-prev"),
  btnPageNext: document.getElementById("btn-page-next"),
  btnReaderClose: document.getElementById("btn-reader-close"),
  btnFitToggle: document.getElementById("btn-fit-toggle"),
  btnPageDarkToggle: document.getElementById("btn-page-dark-toggle"),
  btnExportPdf: document.getElementById("btn-export-pdf"),
  readerCanvasWrapper: document.getElementById("reader-canvas-wrapper"),
};

// --- Theme Management ---
function applyAppTheme(theme) {
  state.appTheme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("rmc_theme", theme);
}

el.btnThemeToggle.addEventListener("click", () => {
  applyAppTheme(state.appTheme === "dark" ? "light" : "dark");
});
applyAppTheme(state.appTheme);

// --- Status & Polling ---
async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();
    const sync = data.sync;

    el.syncBadge.className = `sync-badge ${sync.status}`;
    if (!sync.is_authenticated) {
      el.syncBadge.className = "sync-badge unauth";
      el.syncText.textContent = "Unlinked";
      el.authBanner.style.display = "flex";
      el.btnAuthOpen.style.display = "inline-flex";
    } else {
      el.authBanner.style.display = "none";
      el.btnAuthOpen.style.display = "none";
      if (sync.status === "syncing") {
        el.syncText.textContent = "Syncing...";
      } else if (sync.status === "error") {
        el.syncText.textContent = "Sync Error";
      } else {
        el.syncText.textContent = `Synced (Gen ${sync.last_generation})`;
      }
    }
  } catch (e) {
    console.debug("Status check error", e);
  }
}

// --- Sync Trigger ---
el.btnSyncNow.addEventListener("click", async () => {
  el.btnSyncNow.disabled = true;
  el.syncBadge.className = "sync-badge syncing";
  el.syncText.textContent = "Syncing...";
  try {
    await fetch("/api/sync/trigger", { method: "POST" });
    await fetchDocuments();
  } catch (e) {
    console.error("Sync error", e);
  } finally {
    el.btnSyncNow.disabled = false;
    await fetchStatus();
  }
});

// --- Auth Modal ---
function openAuthModal() {
  el.authCodeInput.value = "";
  el.authError.style.display = "none";
  el.authModal.style.display = "flex";
  el.authCodeInput.focus();
}

function closeAuthModal() {
  el.authModal.style.display = "none";
}

el.btnAuthOpen.addEventListener("click", openAuthModal);
el.btnBannerConnect.addEventListener("click", openAuthModal);
el.btnAuthCancel.addEventListener("click", closeAuthModal);

el.btnAuthSubmit.addEventListener("click", async () => {
  const code = el.authCodeInput.value.trim().toUpperCase();
  if (code.length !== 8) {
    el.authError.textContent = "Code must be exactly 8 characters.";
    el.authError.style.display = "block";
    return;
  }

  el.btnAuthSubmit.disabled = true;
  el.btnAuthSubmit.textContent = "Connecting...";
  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Authentication failed");
    }

    closeAuthModal();
    await fetchStatus();
    await fetchDocuments();
  } catch (e) {
    el.authError.textContent = e.message;
    el.authError.style.display = "block";
  } finally {
    el.btnAuthSubmit.disabled = false;
    el.btnAuthSubmit.textContent = "Pair Device";
  }
});

// --- Breadcrumbs ---
function renderBreadcrumbs() {
  el.breadcrumbs.innerHTML = "";
  state.folderPath.forEach((item, index) => {
    if (index > 0) {
      const sep = document.createElement("span");
      sep.textContent = "›";
      sep.style.color = "var(--text-muted)";
      el.breadcrumbs.appendChild(sep);
    }
    const a = document.createElement("a");
    a.href = "#";
    a.textContent = item.name;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      navigateToFolder(item.id, index);
    });
    el.breadcrumbs.appendChild(a);
  });
}

function navigateToFolder(folderId, pathIndex = null) {
  state.currentFolder = folderId;
  if (pathIndex !== null) {
    state.folderPath = state.folderPath.slice(0, pathIndex + 1);
  }
  renderBreadcrumbs();
  fetchDocuments();
}

el.brandHome.addEventListener("click", (e) => {
  e.preventDefault();
  closeReader();
  navigateToFolder("", 0);
});

// --- Document Listing ---
async function fetchDocuments() {
  try {
    const url = new URL("/api/documents", window.location.origin);
    url.searchParams.set("parent_id", state.currentFolder);
    if (state.currentFilter) {
      url.searchParams.set("file_type", state.currentFilter);
    }

    const res = await fetch(url);
    if (!res.ok) return;
    const docs = await res.json();
    renderDocumentGrid(docs);
  } catch (e) {
    console.error("Failed to load documents", e);
  }
}

function renderDocumentGrid(docs) {
  el.docGrid.innerHTML = "";

  if (docs.length === 0) {
    el.docGrid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1rem; color: var(--text-muted);">
        <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">No documents in this folder</p>
        <p style="font-size: 0.85rem;">Items synced from your reMarkable tablet will appear here.</p>
      </div>
    `;
    return;
  }

  docs.forEach((doc) => {
    const isFolder = doc.type === "CollectionType";
    const card = document.createElement("div");
    card.className = "doc-card";

    let iconHtml = "";
    if (isFolder) {
      iconHtml = `
        <svg class="folder-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
      `;
    } else {
      // Document thumbnail
      const thumbUrl = `/api/documents/${doc.id}/pages/0/png?dark=${state.appTheme === "dark"}`;
      iconHtml = `<img src="${thumbUrl}" alt="Page 1 preview" loading="lazy">`;
    }

    const badgeText = isFolder ? "Folder" : (doc.file_type || "Note");
    const pageText = isFolder ? "" : `${doc.page_count} ${doc.page_count === 1 ? 'page' : 'pages'}`;

    card.innerHTML = `
      <div class="doc-card-thumb">${iconHtml}</div>
      <div class="doc-card-body">
        <div class="doc-card-title" title="${escapeHtml(doc.visible_name)}">${escapeHtml(doc.visible_name)}</div>
        <div class="doc-card-meta">
          <span class="doc-badge">${badgeText}</span>
          <span>${pageText}</span>
        </div>
      </div>
    `;

    card.addEventListener("click", () => {
      if (isFolder) {
        state.folderPath.push({ id: doc.id, name: doc.visible_name });
        navigateToFolder(doc.id);
      } else {
        openReader(doc.id);
      }
    });

    el.docGrid.appendChild(card);
  });
}

// --- Filter Tabs ---
el.filterTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    el.filterTabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    state.currentFilter = tab.getAttribute("data-type") || "";
    fetchDocuments();
  });
});

// --- Reader View ---
async function openReader(docId, initialPageIdx = 0) {
  try {
    const res = await fetch(`/api/documents/${docId}`);
    if (!res.ok) return;
    const doc = await res.json();

    state.currentDoc = doc;
    state.currentPageIdx = initialPageIdx;
    el.readerTitle.textContent = doc.visible_name;

    el.readerView.style.display = "flex";
    updatePageDarkToggle();
    loadCurrentPage();
  } catch (e) {
    console.error("Failed to open document", e);
  }
}

function closeReader() {
  el.readerView.style.display = "none";
  state.currentDoc = null;
}

el.btnReaderClose.addEventListener("click", closeReader);

async function loadCurrentPage() {
  if (!state.currentDoc) return;
  const pages = (state.currentDoc.pages || []).filter((p) => !p.deleted);
  const totalPages = Math.max(pages.length, 1);
  const pageIdx = Math.min(state.currentPageIdx, totalPages - 1);
  state.currentPageIdx = pageIdx;

  el.readerPageIndicator.textContent = `Page ${pageIdx + 1} of ${totalPages}`;
  el.btnPagePrev.disabled = pageIdx <= 0;
  el.btnPageNext.disabled = pageIdx >= totalPages - 1;

  el.readerCanvasWrapper.innerHTML = `
    <div style="color: var(--text-muted); padding: 3rem;">Loading page...</div>
  `;

  try {
    const res = await fetch(
      `/api/documents/${state.currentDoc.id}/pages/${pageIdx}/svg?dark=${state.pageDarkMode}`
    );
    if (!res.ok) throw new Error("Failed to render page");
    const svgText = await res.text();

    el.readerCanvasWrapper.innerHTML = svgText;
    const svgEl = el.readerCanvasWrapper.querySelector("svg");
    if (svgEl) {
      svgEl.classList.add("reader-canvas");
    }
  } catch (e) {
    el.readerCanvasWrapper.innerHTML = `
      <div style="color: var(--danger); padding: 2rem;">Error loading page: ${e.message}</div>
    `;
  }
}

el.btnPagePrev.addEventListener("click", () => {
  if (state.currentPageIdx > 0) {
    state.currentPageIdx--;
    loadCurrentPage();
  }
});

el.btnPageNext.addEventListener("click", () => {
  const pages = (state.currentDoc.pages || []).filter((p) => !p.deleted);
  if (state.currentPageIdx < pages.length - 1) {
    state.currentPageIdx++;
    loadCurrentPage();
  }
});

// Fit toggle
el.btnFitToggle.addEventListener("click", () => {
  if (el.readerView.classList.contains("fit-page")) {
    el.readerView.classList.remove("fit-page");
    el.readerView.classList.add("fit-width");
    el.btnFitToggle.textContent = "Fit Page";
  } else {
    el.readerView.classList.remove("fit-width");
    el.readerView.classList.add("fit-page");
    el.btnFitToggle.textContent = "Fit Width";
  }
});

// Document Dark Mode Toggle
function updatePageDarkToggle() {
  el.btnPageDarkToggle.textContent = state.pageDarkMode ? "Dark: On" : "Dark: Off";
  el.readerView.setAttribute("data-page-theme", state.pageDarkMode ? "dark" : "light");
}

el.btnPageDarkToggle.addEventListener("click", () => {
  state.pageDarkMode = !state.pageDarkMode;
  updatePageDarkToggle();
  loadCurrentPage();
});

// PDF Export
el.btnExportPdf.addEventListener("click", () => {
  if (!state.currentDoc) return;
  const url = `/api/documents/${state.currentDoc.id}/export/pdf?dark=${state.pageDarkMode}`;
  window.open(url, "_blank");
});

// --- Keyboard Shortcuts ---
window.addEventListener("keydown", (e) => {
  if (el.authModal.style.display === "flex") {
    if (e.key === "Escape") closeAuthModal();
    return;
  }

  if (el.readerView.style.display === "flex") {
    if (e.key === "Escape") {
      closeReader();
    } else if (e.key === "ArrowLeft" || e.key === "k" || e.key === "p") {
      el.btnPagePrev.click();
    } else if (e.key === "ArrowRight" || e.key === "j" || e.key === "n" || e.key === " ") {
      e.preventDefault();
      el.btnPageNext.click();
    } else if (e.key === "d") {
      el.btnPageDarkToggle.click();
    }
  }
});

// --- Search ---
let searchDebounce = null;
el.searchInput.addEventListener("input", (e) => {
  clearTimeout(searchDebounce);
  const q = e.target.value.trim();
  if (q.length < 2) {
    el.searchDropdown.style.display = "none";
    return;
  }

  searchDebounce = setTimeout(async () => {
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=10`);
      if (!res.ok) return;
      const results = await res.json();
      renderSearchResults(results);
    } catch (err) {
      console.error("Search failed", err);
    }
  }, 250);
});

function renderSearchResults(results) {
  if (results.length === 0) {
    el.searchDropdown.innerHTML = `<div style="padding: 1rem; color: var(--text-muted); text-align: center;">No matches found</div>`;
    el.searchDropdown.style.display = "block";
    return;
  }

  el.searchDropdown.innerHTML = "";
  results.forEach((r) => {
    const item = document.createElement("div");
    item.className = "search-item";
    item.innerHTML = `
      <div style="font-weight: 600; font-size: 0.9rem; margin-bottom: 0.2rem;">${escapeHtml(r.visible_name)}</div>
      <div style="font-size: 0.78rem; color: var(--text-secondary); line-height: 1.3;">
        ${r.source === 'tag' ? 'Tag match: ' : ''}
        ${r.snippet}
      </div>
    `;

    item.addEventListener("click", () => {
      el.searchDropdown.style.display = "none";
      el.searchInput.value = "";
      openReader(r.doc_id, r.page_idx || 0);
    });

    el.searchDropdown.appendChild(item);
  });
  el.searchDropdown.style.display = "block";
}

document.addEventListener("click", (e) => {
  if (!el.searchInput.contains(e.target) && !el.searchDropdown.contains(e.target)) {
    el.searchDropdown.style.display = "none";
  }
});

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

// --- Initialization ---
fetchStatus();
fetchDocuments();
setInterval(fetchStatus, 8000);
