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
  searchOnlyNotes: true,
  syncDrawerOpen: false,
  activeConverterJobId: null,
  converterPollInterval: null,
};

// 5-stop slider profiles
const CONVERTER_PROFILES = {
  1: {
    name: "Stop 1: Smallest (~75% reduction)",
    desc: "Max 1600px height, JPEG q65. Ultra-lightweight, fastest page turn latency, minimal memory usage. Great for large 400+ page comic volumes.",
  },
  2: {
    name: "Stop 2: Compact (~65% reduction)",
    desc: "Max 1920px height, JPEG q72. Snappy paging with sharp comic legibility. ~120-150 MB for full omnibuses.",
  },
  3: {
    name: "Stop 3: Balanced - Recommended",
    desc: "1:1 native Paper Pro pixel match (2160x1620 portrait at 229 PPI, JPEG q82). Optimal balance of razor-sharp art and smooth e-ink caching.",
  },
  4: {
    name: "Stop 4: Sharp (~40% reduction)",
    desc: "Max 2560px height, JPEG q88. Extra fine fidelity for high-detail line work and complex technical diagrams.",
  },
  5: {
    name: "Stop 5: Best (~10% reduction)",
    desc: "Max 3000px height, JPEG q92. Maximum archival fidelity preserving full original scan data.",
  },
};

// --- DOM Elements ---
const el = {
  syncBadge: document.getElementById("sync-badge"),
  syncText: document.getElementById("sync-text"),
  btnSyncNow: document.getElementById("btn-sync-now"),
  btnSyncDrawerToggle: document.getElementById("btn-sync-drawer-toggle"),
  syncDrawer: document.getElementById("sync-drawer"),
  btnSyncDrawerClose: document.getElementById("btn-sync-drawer-close"),
  syncDrawerStage: document.getElementById("sync-drawer-stage"),
  syncProgressBar: document.getElementById("sync-progress-bar"),
  syncProgressText: document.getElementById("sync-progress-text"),
  syncBytesText: document.getElementById("sync-bytes-text"),
  syncActiveFile: document.getElementById("sync-active-file"),
  syncUpdatedCounter: document.getElementById("sync-updated-counter"),
  syncActivityList: document.getElementById("sync-activity-list"),

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
  btnFolderExclude: document.getElementById("btn-folder-exclude"),
  folderExcludeLabel: document.getElementById("folder-exclude-label"),
  folderExcludeIcon: document.getElementById("folder-exclude-icon"),
  btnOpenConverter: document.getElementById("btn-open-converter"),

  searchInput: document.getElementById("search-input"),
  searchDropdown: document.getElementById("search-dropdown"),
  pillSearchNotes: document.getElementById("pill-search-notes"),
  pillSearchAll: document.getElementById("pill-search-all"),
  brandHome: document.getElementById("brand-home"),

  // Reader elements
  readerView: document.getElementById("reader-view"),
  readerTitle: document.getElementById("reader-title"),
  readerExcludeBadge: document.getElementById("reader-exclude-badge"),
  readerPageIndicator: document.getElementById("reader-page-indicator"),
  btnPagePrev: document.getElementById("btn-page-prev"),
  btnPageNext: document.getElementById("btn-page-next"),
  btnReaderClose: document.getElementById("btn-reader-close"),
  btnReaderExcludeToggle: document.getElementById("btn-reader-exclude-toggle"),
  btnReaderConvert: document.getElementById("btn-reader-convert"),
  btnFitToggle: document.getElementById("btn-fit-toggle"),
  btnPageDarkToggle: document.getElementById("btn-page-dark-toggle"),
  btnExportPdf: document.getElementById("btn-export-pdf"),
  readerCanvasWrapper: document.getElementById("reader-canvas-wrapper"),

  // Converter elements
  converterModal: document.getElementById("converter-modal"),
  btnConverterClose: document.getElementById("btn-converter-close"),
  btnConverterCancel: document.getElementById("btn-converter-cancel"),
  btnConverterStart: document.getElementById("btn-converter-start"),
  converterDocName: document.getElementById("converter-doc-name"),
  converterDocId: document.getElementById("converter-doc-id"),
  btnConverterUploadTrigger: document.getElementById("btn-converter-upload-trigger"),
  converterFileInput: document.getElementById("converter-file-input"),
  qualitySlider: document.getElementById("quality-slider"),
  sliderStopName: document.getElementById("slider-stop-name"),
  sliderDescription: document.getElementById("slider-description"),
  chkSplitSpreads: document.getElementById("chk-split-spreads"),
  chkMangaMode: document.getElementById("chk-manga-mode"),
  converterProgressArea: document.getElementById("converter-progress-area"),
  converterProgressBar: document.getElementById("converter-progress-bar"),
  converterProgressText: document.getElementById("converter-progress-text"),
  converterResultArea: document.getElementById("converter-result-area"),
  converterResultStats: document.getElementById("converter-result-stats"),
  btnConverterDownload: document.getElementById("btn-converter-download"),
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

// --- Sync Progress Drawer ---
function setSyncDrawer(open) {
  state.syncDrawerOpen = open;
  el.syncDrawer.style.display = open ? "block" : "none";
}

el.btnSyncDrawerToggle.addEventListener("click", () => setSyncDrawer(!state.syncDrawerOpen));
el.syncBadge.addEventListener("click", () => setSyncDrawer(!state.syncDrawerOpen));
el.btnSyncDrawerClose.addEventListener("click", () => setSyncDrawer(false));

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 MB";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(2)} GB`;
  }
  return `${mb.toFixed(1)} MB`;
}

function renderSyncProgress(sync) {
  const p = sync.progress || {};
  const isSyncing = sync.status === "syncing" || p.is_syncing;

  el.syncDrawerStage.textContent = p.stage || sync.status || "idle";

  if (isSyncing) {
    const total = p.total_docs || 0;
    const current = p.current_doc_idx || 0;
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;

    el.syncProgressBar.style.width = `${pct}%`;
    el.syncProgressText.textContent = total > 0 ? `${current} of ${total} items (${pct}%)` : "Checking cloud...";
    el.syncBytesText.textContent = `Transferred: ${formatBytes(p.bytes_downloaded)}`;

    if (p.current_file || p.current_doc_name) {
      el.syncActiveFile.style.display = "block";
      el.syncActiveFile.textContent = `Syncing: ${p.current_doc_name || ""} ${p.current_file ? `(${p.current_file})` : ""}`;
    } else {
      el.syncActiveFile.style.display = "none";
    }
  } else {
    el.syncProgressBar.style.width = "100%";
    el.syncProgressText.textContent = `Completed (Gen ${sync.last_generation})`;
    el.syncBytesText.textContent = `Transferred: ${formatBytes(p.bytes_downloaded)}`;
    el.syncActiveFile.style.display = "none";
  }

  el.syncUpdatedCounter.textContent = `${p.docs_updated || 0} items updated`;

  // Render recent activity feed
  const activity = p.recent_activity || [];
  if (activity.length === 0) {
    el.syncActivityList.innerHTML = `<div class="sync-empty-log">No sync events in this session</div>`;
  } else {
    el.syncActivityList.innerHTML = activity
      .slice(0, 15)
      .map((item) => {
        const timeStr = new Date(item.timestamp * 1000).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        const pageText = item.pages > 0 ? `(${item.pages} p)` : "";
        return `
          <div class="sync-activity-item">
            <span class="item-name" title="${escapeHtml(item.name)}">✓ ${escapeHtml(item.name)} ${pageText}</span>
            <span class="item-meta">${timeStr}</span>
          </div>
        `;
      })
      .join("");
  }
}

// --- Status & Polling ---
let pollTimer = null;

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
        const p = sync.progress || {};
        const pct = p.total_docs > 0 ? Math.round((p.current_doc_idx / p.total_docs) * 100) : 0;
        el.syncText.textContent = `Syncing (${pct}%)`;
      } else if (sync.status === "error") {
        el.syncText.textContent = "Sync Error";
      } else {
        el.syncText.textContent = `Synced (Gen ${sync.last_generation})`;
      }
    }

    renderSyncProgress(sync);

    // Dynamic poll interval: poll faster when active
    const nextInterval = sync.status === "syncing" ? 1500 : 7000;
    clearTimeout(pollTimer);
    pollTimer = setTimeout(fetchStatus, nextInterval);
  } catch (e) {
    console.debug("Status check error", e);
    clearTimeout(pollTimer);
    pollTimer = setTimeout(fetchStatus, 7000);
  }
}

// --- Sync Trigger ---
el.btnSyncNow.addEventListener("click", async () => {
  el.btnSyncNow.disabled = true;
  el.syncBadge.className = "sync-badge syncing";
  el.syncText.textContent = "Syncing...";
  setSyncDrawer(true);
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
  const code = el.authCodeInput.value.trim().toLowerCase();
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

// --- Breadcrumbs & Navigation ---
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

async function navigateToFolder(folderId, pathIndex = null) {
  state.currentFolder = folderId;
  if (pathIndex !== null) {
    state.folderPath = state.folderPath.slice(0, pathIndex + 1);
  }
  renderBreadcrumbs();
  updateFolderExclusionButton();
  fetchDocuments();
}

el.brandHome.addEventListener("click", (e) => {
  e.preventDefault();
  closeReader();
  navigateToFolder("", 0);
});

// --- Folder Exclusion Toolbar Button ---
async function updateFolderExclusionButton() {
  if (!state.currentFolder) {
    el.btnFolderExclude.style.display = "none";
    return;
  }

  try {
    const res = await fetch(`/api/documents/${state.currentFolder}`);
    if (!res.ok) {
      el.btnFolderExclude.style.display = "none";
      return;
    }
    const folder = await res.json();
    const isExcluded = folder.exclude_from_search || folder.effective_exclude;

    el.btnFolderExclude.style.display = "inline-flex";
    if (isExcluded) {
      el.folderExcludeIcon.textContent = "✓";
      el.folderExcludeLabel.textContent = "Folder Excluded (Click to Include)";
      el.btnFolderExclude.classList.add("btn-accent");
    } else {
      el.folderExcludeIcon.textContent = "🚫";
      el.folderExcludeLabel.textContent = "Exclude Folder from Search";
      el.btnFolderExclude.classList.remove("btn-accent");
    }
  } catch (e) {
    el.btnFolderExclude.style.display = "none";
  }
}

el.btnFolderExclude.addEventListener("click", async () => {
  if (!state.currentFolder) return;
  try {
    await fetch(`/api/documents/${state.currentFolder}/indexing-toggle`, { method: "POST" });
    await updateFolderExclusionButton();
    await fetchDocuments();
  } catch (e) {
    console.error("Failed to toggle folder exclusion", e);
  }
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
    const isExcluded = doc.exclude_from_search;
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
      const thumbUrl = `/api/documents/${doc.id}/pages/0/png?dark=${state.appTheme === "dark"}`;
      iconHtml = `<img src="${thumbUrl}" alt="Page 1 preview" loading="lazy">`;
    }

    const badgeText = isFolder ? "Folder" : (doc.file_type || "Note");
    const pageText = isFolder ? "" : `${doc.page_count} ${doc.page_count === 1 ? 'page' : 'pages'}`;
    const excludePill = isExcluded ? `<span class="doc-badge doc-badge-excluded" title="Excluded from full-text search & OCR">Excluded</span>` : "";

    card.innerHTML = `
      <div class="doc-card-thumb">${iconHtml}</div>
      <div class="doc-card-body">
        <div class="doc-card-title" title="${escapeHtml(doc.visible_name)}">${escapeHtml(doc.visible_name)}</div>
        <div class="doc-card-meta">
          <span class="doc-badge">${badgeText}</span>
          ${excludePill}
          <span>${pageText}</span>
        </div>
        <div class="doc-card-actions" style="margin-top: 0.5rem; display: flex; gap: 0.4rem; justify-content: flex-end;">
          ${!isFolder ? `<button class="btn btn-sm btn-doc-optimize" title="Optimize for Paper Pro" style="font-size: 0.72rem; padding: 2px 6px;">⚡ Optimize</button>` : ""}
          <button class="btn btn-sm btn-card-exclude" title="Toggle Search/OCR Exclusion" style="font-size: 0.72rem; padding: 2px 6px;">${isExcluded ? '✓ Included' : '🚫 Exclude'}</button>
        </div>
      </div>
    `;

    // Click on card body opens folder / document
    card.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      if (isFolder) {
        state.folderPath.push({ id: doc.id, name: doc.visible_name });
        navigateToFolder(doc.id);
      } else {
        openReader(doc.id);
      }
    });

    // Optimize button
    const btnOpt = card.querySelector(".btn-doc-optimize");
    if (btnOpt) {
      btnOpt.addEventListener("click", (e) => {
        e.stopPropagation();
        openConverterModal(doc.id, doc.visible_name);
      });
    }

    // Exclude toggle
    const btnEx = card.querySelector(".btn-card-exclude");
    if (btnEx) {
      btnEx.addEventListener("click", async (e) => {
        e.stopPropagation();
        try {
          await fetch(`/api/documents/${doc.id}/indexing-toggle`, { method: "POST" });
          fetchDocuments();
        } catch (err) {
          console.error("Failed to toggle exclusion", err);
        }
      });
    }

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

    updateReaderExclusionState();
    el.readerView.style.display = "flex";
    updatePageDarkToggle();
    loadCurrentPage();
  } catch (e) {
    console.error("Failed to open document", e);
  }
}

function updateReaderExclusionState() {
  if (!state.currentDoc) return;
  const isExcluded = state.currentDoc.exclude_from_search || state.currentDoc.effective_exclude;
  if (isExcluded) {
    el.readerExcludeBadge.style.display = "inline-block";
    el.btnReaderExcludeToggle.textContent = "✓ Include in Search";
  } else {
    el.readerExcludeBadge.style.display = "none";
    el.btnReaderExcludeToggle.textContent = "🚫 Exclude from Search";
  }
}

el.btnReaderExcludeToggle.addEventListener("click", async () => {
  if (!state.currentDoc) return;
  try {
    const res = await fetch(`/api/documents/${state.currentDoc.id}/indexing-toggle`, { method: "POST" });
    if (res.ok) {
      state.currentDoc.exclude_from_search = !state.currentDoc.exclude_from_search;
      state.currentDoc.effective_exclude = state.currentDoc.exclude_from_search;
      updateReaderExclusionState();
      fetchDocuments();
    }
  } catch (e) {
    console.error("Failed to toggle exclusion", e);
  }
});

el.btnReaderConvert.addEventListener("click", () => {
  if (!state.currentDoc) return;
  openConverterModal(state.currentDoc.id, state.currentDoc.visible_name);
});

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

// --- Converter Modal ---
function updateSliderUI() {
  const val = parseInt(el.qualitySlider.value, 10);
  const profile = CONVERTER_PROFILES[val] || CONVERTER_PROFILES[3];
  el.sliderStopName.textContent = profile.name;
  el.sliderDescription.textContent = profile.desc;
}

el.qualitySlider.addEventListener("input", updateSliderUI);

function openConverterModal(docId = null, docName = null) {
  el.converterProgressArea.style.display = "none";
  el.converterResultArea.style.display = "none";
  el.btnConverterStart.disabled = false;
  el.btnConverterStart.textContent = "Start Optimization";
  el.qualitySlider.value = "3";
  updateSliderUI();

  if (docId) {
    el.converterDocId.value = docId;
    el.converterDocName.value = docName || "Library Document";
  } else {
    el.converterDocId.value = "";
    el.converterDocName.value = "";
  }
  el.converterFileInput.value = "";

  el.converterModal.style.display = "flex";
}

function closeConverterModal() {
  el.converterModal.style.display = "none";
  if (state.converterPollInterval) {
    clearInterval(state.converterPollInterval);
    state.converterPollInterval = null;
  }
}

el.btnOpenConverter.addEventListener("click", () => openConverterModal());
el.btnConverterClose.addEventListener("click", closeConverterModal);
el.btnConverterCancel.addEventListener("click", closeConverterModal);

el.btnConverterUploadTrigger.addEventListener("click", () => {
  el.converterFileInput.click();
});

el.converterFileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) {
    el.converterDocId.value = "";
    el.converterDocName.value = file.name;
  }
});

el.btnConverterStart.addEventListener("click", async () => {
  const qualityStop = parseInt(el.qualitySlider.value, 10);
  const splitSpreads = el.chkSplitSpreads.checked;
  const mangaMode = el.chkMangaMode.checked;
  const docId = el.converterDocId.value;
  const uploadedFile = el.converterFileInput.files[0];

  if (!docId && !uploadedFile) {
    alert("Please select a document or upload a file first.");
    return;
  }

  el.btnConverterStart.disabled = true;
  el.converterProgressArea.style.display = "block";
  el.converterProgressBar.style.width = "0%";
  el.converterProgressText.textContent = "Starting conversion job...";

  try {
    let jobId = null;

    // Convert existing document
    if (docId) {
      const res = await fetch(`/api/documents/${docId}/convert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quality_stop: qualityStop,
          split_spreads: splitSpreads,
          manga_mode: mangaMode,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start conversion");
      }
      const data = await res.json();
      jobId = data.job_id;
    }
    // Convert uploaded file
    else if (uploadedFile) {
      const formData = new FormData();
      formData.append("file", uploadedFile);
      formData.append("quality_stop", qualityStop);
      formData.append("split_spreads", splitSpreads);
      formData.append("manga_mode", mangaMode);

      const res = await fetch("/api/converter/upload", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to upload file");
      }
      const data = await res.json();
      jobId = data.job_id;
    }

    state.activeConverterJobId = jobId;

    // Poll job status
    state.converterPollInterval = setInterval(async () => {
      try {
        const jRes = await fetch(`/api/converter/jobs/${jobId}`);
        if (!jRes.ok) return;
        const job = await jRes.json();

        if (job.status === "processing") {
          const pct = job.progress_percent || 0;
          el.converterProgressBar.style.width = `${pct}%`;
          el.converterProgressText.textContent = `Processing page ${job.current_page} of ${job.total_pages} (${pct}%)...`;
        } else if (job.status === "done") {
          clearInterval(state.converterPollInterval);
          state.converterPollInterval = null;
          el.converterProgressBar.style.width = "100%";
          el.converterProgressArea.style.display = "none";
          el.converterResultArea.style.display = "block";

          const origMb = (job.original_size / (1024 * 1024)).toFixed(1);
          const resMb = (job.result_size / (1024 * 1024)).toFixed(1);
          const redText =
            job.reduction_percent >= 0
              ? `${job.reduction_percent}% reduction`
              : `+${Math.abs(job.reduction_percent)}% (upscaled)`;
          el.converterResultStats.innerHTML = `
            <strong>Pages:</strong> ${job.total_pages} &nbsp;|&nbsp;
            <strong>Original:</strong> ${origMb} MB &nbsp;➔&nbsp;
            <strong>Optimized:</strong> ${resMb} MB
            (${redText})<br>
            <span style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.25rem; display: block;">
              Single-layer linearized PDF formatted at 229 PPI native screen size. Loads instantly on Paper Pro.
            </span>
          `;
          el.btnConverterDownload.href = `/api/converter/jobs/${jobId}/download`;
        } else if (job.status === "error") {
          clearInterval(state.converterPollInterval);
          state.converterPollInterval = null;
          el.converterProgressArea.style.display = "none";
          alert(`Conversion error: ${job.error}`);
          el.btnConverterStart.disabled = false;
        }
      } catch (err) {
        console.error("Job poll error", err);
      }
    }, 600);
  } catch (err) {
    el.converterProgressArea.style.display = "none";
    alert(`Failed to start job: ${err.message}`);
    el.btnConverterStart.disabled = false;
  }
});

// --- Search Filter Pills ---
el.pillSearchNotes.addEventListener("click", () => {
  state.searchOnlyNotes = true;
  el.pillSearchNotes.classList.add("active");
  el.pillSearchAll.classList.remove("active");
  triggerSearch();
});

el.pillSearchAll.addEventListener("click", () => {
  state.searchOnlyNotes = false;
  el.pillSearchAll.classList.add("active");
  el.pillSearchNotes.classList.remove("active");
  triggerSearch();
});

// --- Search Implementation ---
let searchDebounce = null;

function triggerSearch() {
  clearTimeout(searchDebounce);
  const q = el.searchInput.value.trim();
  if (q.length < 2) {
    el.searchDropdown.style.display = "none";
    return;
  }

  searchDebounce = setTimeout(async () => {
    try {
      const url = new URL("/api/search", window.location.origin);
      url.searchParams.set("q", q);
      url.searchParams.set("limit", "15");
      url.searchParams.set("only_notes", state.searchOnlyNotes ? "true" : "false");
      url.searchParams.set("include_excluded", "false");

      const res = await fetch(url);
      if (!res.ok) return;
      const results = await res.json();
      renderSearchResults(results);
    } catch (err) {
      console.error("Search failed", err);
    }
  }, 250);
}

el.searchInput.addEventListener("input", triggerSearch);

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
      <div style="font-weight: 600; font-size: 0.9rem; margin-bottom: 0.2rem; display: flex; justify-content: space-between;">
        <span>${escapeHtml(r.visible_name)}</span>
        <span style="font-size: 0.72rem; color: var(--text-muted);">${r.file_type || r.type}</span>
      </div>
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

// --- Keyboard Shortcuts ---
window.addEventListener("keydown", (e) => {
  if (el.authModal.style.display === "flex") {
    if (e.key === "Escape") closeAuthModal();
    return;
  }
  if (el.converterModal.style.display === "flex") {
    if (e.key === "Escape") closeConverterModal();
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

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

// --- Initialization ---
fetchStatus();
fetchDocuments();
