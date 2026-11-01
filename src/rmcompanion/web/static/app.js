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
  themePreference: localStorage.getItem("rmc_theme_pref") || "auto",
  viewMode: localStorage.getItem("rmc_view_mode") || "grid",
  allDocs: [],
  currentRenderedDocs: [],
  searchOnlyNotes: false,
  syncDrawerOpen: false,
  activeConverterJobId: null,
  converterPollInterval: null,
  currentSort: "modified-desc",
  currentTaskFilter: "open",
  isFullscreen: false,
  hudTimeout: null,
  pageIndicatorTimeout: null,
  qcMode: "task",
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
  btnSyncStatus: document.getElementById("btn-sync-status"),
  syncStatusDot: document.getElementById("sync-status-dot"),
  syncIconSvg: document.getElementById("sync-icon-svg"),
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

  btnNewNotebook: document.getElementById("btn-new-notebook"),
  btnNewDropdownToggle: document.getElementById("btn-new-dropdown-toggle"),
  newItemDropdown: document.getElementById("new-item-dropdown"),
  menuNewNote: document.getElementById("menu-new-note"),
  menuNewFolder: document.getElementById("menu-new-folder"),
  menuBulkImport: document.getElementById("menu-bulk-import"),

  btnViewGrid: document.getElementById("btn-view-grid"),
  btnViewList: document.getElementById("btn-view-list"),

  commandPaletteModal: document.getElementById("command-palette-modal"),
  commandPaletteInput: document.getElementById("command-palette-input"),
  commandPaletteResults: document.getElementById("command-palette-results"),

  bulkImportModal: document.getElementById("bulk-import-modal"),
  btnBulkImportClose: document.getElementById("btn-bulk-import-close"),
  btnBulkImportCancel: document.getElementById("btn-bulk-import-cancel"),
  btnBulkImportSubmit: document.getElementById("btn-bulk-import-submit"),
  bulkImportFiles: document.getElementById("bulk-import-files"),
  bulkImportDevice: document.getElementById("bulk-import-device"),
  bulkImportFolder: document.getElementById("bulk-import-folder"),
  bulkImportFileCount: document.getElementById("bulk-import-file-count"),
  bulkImportStatus: document.getElementById("bulk-import-status"),

  themeChoiceAuto: document.getElementById("theme-choice-auto"),
  themeChoiceDark: document.getElementById("theme-choice-dark"),
  themeChoiceLight: document.getElementById("theme-choice-light"),
  btnCopyMcpConfig: document.getElementById("btn-copy-mcp-config"),
  btnCopyMcpUrl: document.getElementById("btn-copy-mcp-url"),

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
  btnSearchClear: document.getElementById("btn-search-clear"),
  searchDropdown: document.getElementById("search-dropdown"),
  brandHome: document.getElementById("brand-home"),
  selectSort: document.getElementById("select-sort"),

  // Reader elements
  readerView: document.getElementById("reader-view"),
  readerHeader: document.getElementById("reader-header"),
  readerNav: document.getElementById("reader-nav"),
  readerTitle: document.getElementById("reader-title"),
  readerExcludeBadge: document.getElementById("reader-exclude-badge"),
  readerPageIndicator: document.getElementById("reader-page-indicator"),
  btnPagePrev: document.getElementById("btn-page-prev"),
  btnPageNext: document.getElementById("btn-page-next"),
  btnReaderClose: document.getElementById("btn-reader-close"),
  btnReaderCloseText: document.getElementById("btn-reader-close-text"),
  btnReaderExcludeToggle: document.getElementById("btn-reader-exclude-toggle"),
  btnReaderConvert: document.getElementById("btn-reader-convert"),
  btnFitToggle: document.getElementById("btn-fit-toggle"),
  btnPageDarkToggle: document.getElementById("btn-page-dark-toggle"),
  btnExportPdf: document.getElementById("btn-export-pdf"),
  btnReaderFullscreen: document.getElementById("btn-reader-fullscreen"),
  btnFullscreenLabel: document.getElementById("btn-fullscreen-label"),
  readerCanvasWrapper: document.getElementById("reader-canvas-wrapper"),
  readerClickZones: document.getElementById("reader-click-zones"),
  zonePrev: document.getElementById("zone-prev"),
  zoneCenter: document.getElementById("zone-center"),
  zoneNext: document.getElementById("zone-next"),

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

  // Tasks elements
  btnTasksToggle: document.getElementById("btn-tasks-toggle"),
  tasksBadge: document.getElementById("tasks-badge"),
  tasksModal: document.getElementById("tasks-modal"),
  btnTasksClose: document.getElementById("btn-tasks-close"),
  btnTasksDone: document.getElementById("btn-tasks-done"),
  tasksCountPill: document.getElementById("tasks-count-pill"),
  tasksList: document.getElementById("tasks-list"),
  btnTasksScanAll: document.getElementById("btn-tasks-scan-all"),
  taskFilterPills: document.querySelectorAll("[data-task-filter]"),

  // Settings elements
  btnSettingsToggle: document.getElementById("btn-settings-toggle"),
  settingsModal: document.getElementById("settings-modal"),
  btnSettingsClose: document.getElementById("btn-settings-close"),
  settingsProvider: document.getElementById("settings-provider"),
  settingsModel: document.getElementById("settings-model"),
  settingsApiKey: document.getElementById("settings-api-key"),
  settingsBaseUrlGroup: document.getElementById("settings-base-url-group"),
  settingsBaseUrl: document.getElementById("settings-base-url"),
  settingsKeyStatus: document.getElementById("settings-key-status"),
  settingsTestResult: document.getElementById("settings-test-result"),
  btnSettingsTest: document.getElementById("btn-settings-test"),
  btnSettingsSave: document.getElementById("btn-settings-save"),

  // New notebook & typed editor elements
  btnNewNotebook: document.getElementById("btn-new-notebook"),
  newNotebookModal: document.getElementById("new-notebook-modal"),
  btnNewNotebookClose: document.getElementById("btn-new-notebook-close"),
  btnNewNotebookCancel: document.getElementById("btn-new-notebook-cancel"),
  btnNewNotebookSubmit: document.getElementById("btn-new-notebook-submit"),
  newNotebookTitle: document.getElementById("new-notebook-title"),
  newNotebookParent: document.getElementById("new-notebook-parent"),
  newNotebookContent: document.getElementById("new-notebook-content"),
  btnImportFileTrigger: document.getElementById("btn-import-file-trigger"),
  mdFileInput: document.getElementById("md-file-input"),

  btnReaderTypeToggle: document.getElementById("btn-reader-type-toggle"),
  readerTypingPane: document.getElementById("reader-typing-pane"),
  typingPaneTextarea: document.getElementById("typing-pane-textarea"),
  btnTypingDiscard: document.getElementById("btn-typing-discard"),
  btnTypingSave: document.getElementById("btn-typing-save"),

  btnSyncTasksNotebook: document.getElementById("btn-sync-tasks-notebook"),
  taskQuickAddForm: document.getElementById("task-quick-add-form"),
  taskQuickInput: document.getElementById("task-quick-input"),
  btnTaskQuickAdd: document.getElementById("btn-task-quick-add"),

  // Mobile Action Tray elements
  mobileActionTray: document.getElementById("mobile-action-tray"),
  trayDocIcon: document.getElementById("tray-doc-icon"),
  trayDocTitle: document.getElementById("tray-doc-title"),
  trayDocMeta: document.getElementById("tray-doc-meta"),
  trayBtnOpen: document.getElementById("tray-btn-open"),
  trayBtnReadTab: document.getElementById("tray-btn-read-tab"),
  trayLabelOpen: document.getElementById("tray-label-open"),
  trayBtnType: document.getElementById("tray-btn-type"),
  trayBtnOptimize: document.getElementById("tray-btn-optimize"),
  trayBtnExport: document.getElementById("tray-btn-export"),
  trayBtnExclude: document.getElementById("tray-btn-exclude"),
  trayIconExclude: document.getElementById("tray-icon-exclude"),
  trayLabelExclude: document.getElementById("tray-label-exclude"),
  trayDescExclude: document.getElementById("tray-desc-exclude"),
  trayBtnMove: document.getElementById("tray-btn-move"),
  trayBtnDelete: document.getElementById("tray-btn-delete"),
  trayBtnCancel: document.getElementById("tray-btn-cancel"),

  // Folder management elements
  btnNewFolder: document.getElementById("btn-new-folder"),
  newFolderModal: document.getElementById("new-folder-modal"),
  btnNewFolderClose: document.getElementById("btn-new-folder-close"),
  btnNewFolderCancel: document.getElementById("btn-new-folder-cancel"),
  formNewFolder: document.getElementById("form-new-folder"),
  inputNewFolderName: document.getElementById("input-new-folder-name"),
  newFolderLocationHint: document.getElementById("new-folder-location-hint"),

  moveFolderModal: document.getElementById("move-folder-modal"),
  btnMoveFolderClose: document.getElementById("btn-move-folder-close"),
  btnMoveFolderCancel: document.getElementById("btn-move-folder-cancel"),
  btnMoveFolderSubmit: document.getElementById("btn-move-folder-submit"),
  moveModalDocTitle: document.getElementById("move-modal-doc-title"),
  formQuickNewFolder: document.getElementById("form-quick-new-folder"),
  inputQuickNewFolder: document.getElementById("input-quick-new-folder"),
  inputFolderSearch: document.getElementById("input-folder-search"),
  folderTreeContainer: document.getElementById("folder-tree-container"),

  // Mobile Reader Options elements
  btnReaderTypeMobile: document.getElementById("btn-reader-type-mobile"),
  btnReaderMoreMobile: document.getElementById("btn-reader-more-mobile"),
  btnReaderFullscreenMobile: document.getElementById("btn-reader-fullscreen-mobile"),
  readerOptionsTray: document.getElementById("reader-options-tray"),
  trayReaderFullscreen: document.getElementById("tray-reader-fullscreen"),
  trayReaderFullscreenLabel: document.getElementById("tray-reader-fullscreen-label"),
  trayReaderDarkToggle: document.getElementById("tray-reader-dark-toggle"),
  trayReaderDarkLabel: document.getElementById("tray-reader-dark-label"),
  trayReaderFitToggle: document.getElementById("tray-reader-fit-toggle"),
  trayReaderFitLabel: document.getElementById("tray-reader-fit-label"),
  trayReaderConvert: document.getElementById("tray-reader-convert"),
  trayReaderExclude: document.getElementById("tray-reader-exclude"),
  trayReaderExcludeLabel: document.getElementById("tray-reader-exclude-label"),
  trayReaderExport: document.getElementById("tray-reader-export"),
  trayReaderClose: document.getElementById("tray-reader-close"),

  // Quick Capture elements
  btnQuickCapture: document.getElementById("btn-quick-capture"),
  quickCaptureModal: document.getElementById("quick-capture-modal"),
  btnModalQcClose: document.getElementById("btn-modal-qc-close"),
  btnModalQcCancel: document.getElementById("btn-modal-qc-cancel"),
  btnModalQcSave: document.getElementById("btn-modal-qc-save"),
  qcInput: document.getElementById("qc-input"),
  qcModeTask: document.getElementById("qc-mode-task"),
  qcModeNote: document.getElementById("qc-mode-note"),
  qcNoteOptions: document.getElementById("qc-note-options"),
  qcNotebookTitle: document.getElementById("qc-notebook-title"),
};

// --- Theme Management ---
function getEffectiveTheme(pref) {
  if (pref === "auto") {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return pref === "light" ? "light" : "dark";
}

function applyAppTheme(pref) {
  state.themePreference = pref;
  localStorage.setItem("rmc_theme_pref", pref);
  const effectiveTheme = getEffectiveTheme(pref);
  state.appTheme = effectiveTheme;
  document.documentElement.setAttribute("data-theme", effectiveTheme);
  localStorage.setItem("rmc_theme", effectiveTheme);

  if (el.themeChoiceAuto) el.themeChoiceAuto.checked = pref === "auto";
  if (el.themeChoiceDark) el.themeChoiceDark.checked = pref === "dark";
  if (el.themeChoiceLight) el.themeChoiceLight.checked = pref === "light";
}

if (window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (state.themePreference === "auto") {
      applyAppTheme("auto");
    }
  });
}

if (el.themeChoiceAuto) el.themeChoiceAuto.addEventListener("change", () => applyAppTheme("auto"));
if (el.themeChoiceDark) el.themeChoiceDark.addEventListener("change", () => applyAppTheme("dark"));
if (el.themeChoiceLight) el.themeChoiceLight.addEventListener("change", () => applyAppTheme("light"));

if (el.btnThemeToggle) {
  el.btnThemeToggle.addEventListener("click", () => {
    // Cycle auto -> dark -> light -> auto
    const next = state.themePreference === "auto" ? "dark" : (state.themePreference === "dark" ? "light" : "auto");
    applyAppTheme(next);
  });
}
applyAppTheme(state.themePreference);

// --- Sync Progress Drawer ---
function setSyncDrawer(open) {
  state.syncDrawerOpen = open;
  if (el.syncDrawer) el.syncDrawer.style.display = open ? "block" : "none";
}

if (el.btnSyncStatus) {
  el.btnSyncStatus.addEventListener("click", () => setSyncDrawer(!state.syncDrawerOpen));
}
if (el.btnSyncDrawerToggle) {
  el.btnSyncDrawerToggle.addEventListener("click", () => setSyncDrawer(!state.syncDrawerOpen));
}
if (el.syncBadge) {
  el.syncBadge.addEventListener("click", () => setSyncDrawer(!state.syncDrawerOpen));
}
if (el.btnSyncDrawerClose) {
  el.btnSyncDrawerClose.addEventListener("click", () => setSyncDrawer(false));
}

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

  if (el.syncDrawerStage) el.syncDrawerStage.textContent = p.stage || sync.status || "idle";

  if (isSyncing) {
    const total = p.total_docs || 0;
    const current = p.current_doc_idx || 0;
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;

    if (el.syncProgressBar) el.syncProgressBar.style.width = `${pct}%`;
    if (el.syncProgressText) el.syncProgressText.textContent = total > 0 ? `${current} of ${total} items (${pct}%)` : "Checking cloud...";
    if (el.syncBytesText) el.syncBytesText.textContent = `Transferred: ${formatBytes(p.bytes_downloaded)}`;

    if (p.current_file || p.current_doc_name) {
      if (el.syncActiveFile) {
        el.syncActiveFile.style.display = "block";
        el.syncActiveFile.textContent = `Syncing: ${p.current_doc_name || ""} ${p.current_file ? `(${p.current_file})` : ""}`;
      }
    } else {
      if (el.syncActiveFile) el.syncActiveFile.style.display = "none";
    }
  } else {
    if (el.syncProgressBar) el.syncProgressBar.style.width = "100%";
    if (el.syncProgressText) el.syncProgressText.textContent = `Completed (Gen ${sync.last_generation})`;
    if (el.syncBytesText) el.syncBytesText.textContent = `Transferred: ${formatBytes(p.bytes_downloaded)}`;
    if (el.syncActiveFile) el.syncActiveFile.style.display = "none";
  }

  if (el.syncUpdatedCounter) el.syncUpdatedCounter.textContent = `${p.docs_updated || 0} items updated`;

  // Render recent activity feed
  const activity = p.recent_activity || [];
  if (el.syncActivityList) {
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
}

// --- Status & Polling ---
let pollTimer = null;

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();
    const sync = data.sync;

    if (el.syncBadge) el.syncBadge.className = `sync-badge ${sync.status}`;
    if (!sync.is_authenticated) {
      if (el.syncBadge) el.syncBadge.className = "sync-badge unauth";
      if (el.syncText) el.syncText.textContent = "Unlinked";
      if (el.authBanner) el.authBanner.style.display = "flex";
      if (el.btnAuthOpen) el.btnAuthOpen.style.display = "inline-flex";
      if (el.syncStatusDot) el.syncStatusDot.className = "sync-status-dot unauth";
      if (el.btnSyncStatus) {
        el.btnSyncStatus.classList.remove("is-syncing");
        el.btnSyncStatus.title = "Not connected to reMarkable Cloud (Click to view logs)";
      }
    } else {
      if (el.authBanner) el.authBanner.style.display = "none";
      if (el.btnAuthOpen) el.btnAuthOpen.style.display = "none";
      if (sync.status === "syncing") {
        const p = sync.progress || {};
        const pct = p.total_docs > 0 ? Math.round((p.current_doc_idx / p.total_docs) * 100) : 0;
        if (el.syncText) el.syncText.textContent = `Syncing (${pct}%)`;
        if (el.syncStatusDot) el.syncStatusDot.className = "sync-status-dot syncing";
        if (el.btnSyncStatus) {
          el.btnSyncStatus.classList.add("is-syncing");
          el.btnSyncStatus.title = `Syncing with reMarkable Cloud (${pct}%) - Click for logs`;
        }
      } else if (sync.status === "error") {
        if (el.syncText) el.syncText.textContent = "Sync Error";
        if (el.syncStatusDot) el.syncStatusDot.className = "sync-status-dot error";
        if (el.btnSyncStatus) {
          el.btnSyncStatus.classList.remove("is-syncing");
          el.btnSyncStatus.title = "Sync Error (Click to view logs)";
        }
      } else {
        if (el.syncText) el.syncText.textContent = `Synced (Gen ${sync.last_generation})`;
        if (el.syncStatusDot) el.syncStatusDot.className = "sync-status-dot synced";
        if (el.btnSyncStatus) {
          el.btnSyncStatus.classList.remove("is-syncing");
          el.btnSyncStatus.title = `Synced with reMarkable Cloud (Gen ${sync.last_generation}) - Click for logs`;
        }
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
if (el.btnSyncNow) {
  el.btnSyncNow.addEventListener("click", async () => {
    el.btnSyncNow.disabled = true;
    if (el.syncBadge) {
      el.syncBadge.className = "sync-badge syncing";
      if (el.syncText) el.syncText.textContent = "Syncing...";
    }
    if (el.syncStatusDot) el.syncStatusDot.className = "sync-status-dot syncing";
    if (el.btnSyncStatus) el.btnSyncStatus.classList.add("is-syncing");
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
}

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

function formatModifiedDate(ts) {
  if (!ts) return "";
  const num = Number(ts);
  const d = isNaN(num) ? new Date(ts) : new Date(num > 1e11 ? num : num * 1000);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } else if (diffDays === 1) {
    return "Yesterday";
  } else if (diffDays < 7) {
    return `${diffDays}d ago`;
  } else {
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }
}

// --- Document Listing & View Modes ---
function setViewMode(mode) {
  state.viewMode = mode;
  localStorage.setItem("rmc_view_mode", mode);
  if (el.btnViewGrid) el.btnViewGrid.classList.toggle("active", mode === "grid");
  if (el.btnViewList) el.btnViewList.classList.toggle("active", mode === "list");
  if (el.docGrid) {
    el.docGrid.className = mode === "grid" ? "doc-grid" : "doc-list";
  }
  renderDocumentGrid(state.currentRenderedDocs || []);
}

if (el.btnViewGrid) el.btnViewGrid.addEventListener("click", () => setViewMode("grid"));
if (el.btnViewList) el.btnViewList.addEventListener("click", () => setViewMode("list"));

async function fetchDocuments() {
  try {
    const url = new URL("/api/documents", window.location.origin);
    url.searchParams.set("parent_id", state.currentFolder);
    if (state.currentFilter && state.currentFilter !== "excluded") {
      url.searchParams.set("file_type", state.currentFilter);
    }

    const res = await fetch(url);
    if (!res.ok) return;
    let docs = await res.json();

    // Cache items for command palette search
    if (state.currentFolder === "" && (!state.currentFilter || state.currentFilter === "all")) {
      state.allDocs = docs;
    } else if (state.allDocs.length === 0) {
      // Lazy fetch all documents for command palette
      fetch("/api/documents").then(r => r.json()).then(all => { state.allDocs = all; }).catch(() => {});
    }

    // Filter by excluded if that tab is active
    if (state.currentFilter === "excluded") {
      docs = docs.filter((d) => d.exclude_from_search);
    }

    // Sort documents (folders stay first for natural navigation)
    docs.sort((a, b) => {
      const isFolderA = a.type === "CollectionType";
      const isFolderB = b.type === "CollectionType";
      if (isFolderA !== isFolderB) {
        return isFolderA ? -1 : 1;
      }

      switch (state.currentSort) {
        case "name-asc":
          return (a.visible_name || "").localeCompare(b.visible_name || "");
        case "name-desc":
          return (b.visible_name || "").localeCompare(a.visible_name || "");
        case "pages-desc":
          return (b.page_count || 0) - (a.page_count || 0);
        case "modified-asc":
          return (a.last_modified || "").localeCompare(b.last_modified || "");
        case "modified-desc":
        default:
          return (b.last_modified || "").localeCompare(a.last_modified || "");
      }
    });

    state.currentRenderedDocs = docs;
    renderDocumentGrid(docs);
  } catch (e) {
    console.error("Failed to load documents", e);
  }
}

function renderDocumentGrid(docs) {
  if (!el.docGrid) return;
  el.docGrid.innerHTML = "";
  el.docGrid.className = state.viewMode === "list" ? "doc-list" : "doc-grid";

  if (docs.length === 0) {
    el.docGrid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1rem; color: var(--text-muted);">
        <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">No documents in this view</p>
        <p style="font-size: 0.85rem;">Items synced from your reMarkable tablet will appear here.</p>
      </div>
    `;
    return;
  }

  docs.forEach((doc) => {
    const isFolder = doc.type === "CollectionType";
    const isExcluded = Boolean(doc.exclude_from_search || doc.effective_exclude);
    const badgeText = isFolder ? "Folder" : (doc.file_type || "Note").toUpperCase();
    const pageText = isFolder ? "" : `${doc.page_count} ${doc.page_count === 1 ? 'page' : 'pages'}`;
    const optimizeBadge = doc.needs_optimization ? `<span class="doc-badge doc-badge-optimize" title="Large file (>30MB or >150 pages). Optimize for Paper Pro.">⚡ Heavy File</span>` : "";

    const element = document.createElement("div");

    const menuHtml = `
      <div class="card-menu-wrapper">
        <button class="btn-card-menu" title="Options" aria-label="Options">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="1.5"></circle>
            <circle cx="12" cy="5" r="1.5"></circle>
            <circle cx="12" cy="19" r="1.5"></circle>
          </svg>
        </button>
        <div class="card-menu-dropdown" style="display: none;">
          <div class="menu-status-badge ${isExcluded ? 'status-excluded' : 'status-indexed'}">
            <span class="status-indicator"></span>
            <span>Status: ${isExcluded ? 'Excluded' : 'Indexed'}</span>
          </div>
          <button class="menu-item menu-item-open">
            ${isFolder ? '📂 Open Folder' : '📖 Open & Read'}
          </button>
          ${!isFolder ? `<a href="/?read=${doc.id}" target="_blank" rel="noopener" class="menu-item menu-item-read-tab" style="text-decoration: none; color: inherit;">↗ Read in New Tab</a>` : ""}
          <button class="menu-item menu-item-move">📁 Add to Folder...</button>
          ${!isFolder ? `<button class="menu-item menu-item-optimize">⚡ Optimize for Paper Pro</button>` : ""}
          <button class="menu-item menu-item-exclude">
            ${isExcluded ? '✓ Include in Search & Tasks' : '🚫 Exclude from Search & Tasks'}
          </button>
          ${isFolder ? `<a href="/api/documents/${doc.id}/export/zip" download class="menu-item menu-item-export" style="text-decoration: none; color: inherit;">📥 Download Folder (ZIP)</a>` : `<a href="/api/documents/${doc.id}/export/pdf?dark=${state.appTheme === 'dark'}" download class="menu-item menu-item-export" style="text-decoration: none; color: inherit;">📥 Download PDF</a>`}
          <button class="menu-item menu-item-copy-id">📋 Copy ID</button>
          <button class="menu-item menu-item-delete">🗑 Delete</button>
        </div>
      </div>
    `;

    if (state.viewMode === "list") {
      element.className = "doc-list-item";
      let listIcon = "📓";
      if (isFolder) listIcon = "📁";
      else if (doc.file_type === "pdf") listIcon = "📄";
      else if (doc.file_type === "epub") listIcon = "📚";

      element.innerHTML = `
        <div class="doc-list-icon">${listIcon}</div>
        <div class="doc-list-title-col">
          <div class="doc-list-title" title="${escapeHtml(doc.visible_name)}">${escapeHtml(doc.visible_name)}</div>
        </div>
        <div class="doc-list-meta-col">
          <span class="doc-badge">${badgeText}</span>
          ${optimizeBadge}
          <span>${pageText}</span>
          <span class="doc-list-date">${formatModifiedDate(doc.last_modified)}</span>
          ${menuHtml}
        </div>
      `;
    } else {
      element.className = "doc-card";
      let iconHtml = "";
      if (isFolder) {
        iconHtml = `
          <svg class="folder-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
        `;
      } else {
        const thumbUrl = `/api/documents/${doc.id}/thumbnail?h=${encodeURIComponent(doc.doc_hash || "")}&dark=${state.appTheme === "dark"}`;
        iconHtml = `<img src="${thumbUrl}" alt="${escapeHtml(doc.visible_name)} preview" loading="lazy" width="320" height="426">`;
      }

      element.innerHTML = `
        <div class="doc-card-thumb">${iconHtml}</div>
        <div class="doc-card-body">
          <div class="card-header-row">
            <div class="doc-card-title" title="${escapeHtml(doc.visible_name)}">${escapeHtml(doc.visible_name)}</div>
            ${menuHtml}
          </div>
          <div class="doc-card-meta">
            <span class="doc-badge">${badgeText}</span>
            ${optimizeBadge}
            <span>${pageText}</span>
          </div>
        </div>
      `;
    }

    // Click on item body opens folder / document
    element.addEventListener("click", (e) => {
      if (e.target.closest(".card-menu-wrapper")) return;
      if (isFolder) {
        state.folderPath.push({ id: doc.id, name: doc.visible_name });
        navigateToFolder(doc.id);
      } else {
        openReader(doc.id);
      }
    });

    // Ellipsis Menu Toggle
    const btnMenu = element.querySelector(".btn-card-menu");
    const menuDropdown = element.querySelector(".card-menu-dropdown");
    btnMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      if (window.innerWidth <= 768) {
        openMobileActionTray(doc);
      } else {
        const isOpen = menuDropdown.style.display === "block";
        document.querySelectorAll(".card-menu-dropdown").forEach((d) => (d.style.display = "none"));
        menuDropdown.style.display = isOpen ? "none" : "block";
      }
    });

    // Long-press affordance on touch devices
    let touchTimer = null;
    element.addEventListener("touchstart", (e) => {
      if (e.target.closest(".card-menu-wrapper")) return;
      touchTimer = setTimeout(() => {
        if (navigator.vibrate) navigator.vibrate(25);
        openMobileActionTray(doc);
      }, 500);
    }, { passive: true });
    element.addEventListener("touchend", () => clearTimeout(touchTimer));
    element.addEventListener("touchmove", () => clearTimeout(touchTimer));

    // Menu Actions
    const mOpen = element.querySelector(".menu-item-open");
    if (mOpen) {
      mOpen.addEventListener("click", (e) => {
        e.stopPropagation();
        menuDropdown.style.display = "none";
        if (isFolder) {
          state.folderPath.push({ id: doc.id, name: doc.visible_name });
          navigateToFolder(doc.id);
        } else {
          openReader(doc.id);
        }
      });
    }

    const mReadTab = element.querySelector(".menu-item-read-tab");
    if (mReadTab) {
      mReadTab.addEventListener("click", (e) => {
        e.stopPropagation();
        menuDropdown.style.display = "none";
      });
    }

    const mExport = element.querySelector(".menu-item-export");
    if (mExport) {
      mExport.addEventListener("click", (e) => {
        e.stopPropagation();
        menuDropdown.style.display = "none";
      });
    }

    const mOpt = element.querySelector(".menu-item-optimize");
    if (mOpt) {
      mOpt.addEventListener("click", (e) => {
        e.stopPropagation();
        menuDropdown.style.display = "none";
        openConverterModal(doc.id, doc.visible_name);
      });
    }

    const mEx = element.querySelector(".menu-item-exclude");
    if (mEx) {
      mEx.addEventListener("click", async (e) => {
        e.stopPropagation();
        menuDropdown.style.display = "none";
        try {
          await fetch(`/api/documents/${doc.id}/indexing-toggle`, { method: "POST" });
          fetchDocuments();
        } catch (err) {
          console.error("Failed to toggle exclusion", err);
        }
      });
    }

    const mCopy = element.querySelector(".menu-item-copy-id");
    if (mCopy) {
      mCopy.addEventListener("click", (e) => {
        e.stopPropagation();
        menuDropdown.style.display = "none";
        navigator.clipboard.writeText(doc.id).then(() => {
          mCopy.textContent = "✓ Copied!";
          setTimeout(() => {
            mCopy.textContent = "📋 Copy ID";
          }, 1500);
        });
      });
    }

    const mMove = element.querySelector(".menu-item-move");
    if (mMove) {
      mMove.addEventListener("click", (e) => {
        e.stopPropagation();
        menuDropdown.style.display = "none";
        openMoveFolderModal(doc);
      });
    }

    const mDelete = element.querySelector(".menu-item-delete");
    if (mDelete) {
      mDelete.addEventListener("click", (e) => {
        e.stopPropagation();
        menuDropdown.style.display = "none";
        confirmDeleteDocument(doc);
      });
    }

    el.docGrid.appendChild(element);
  });
}

// Close card menus on outside click
document.addEventListener("click", (e) => {
  if (!e.target.closest(".card-menu-wrapper")) {
    document.querySelectorAll(".card-menu-dropdown").forEach((d) => (d.style.display = "none"));
  }
});

// --- Mobile Action Tray Controller ---
let selectedMobileDoc = null;

function openMobileActionTray(doc) {
  if (!el.mobileActionTray) return;
  selectedMobileDoc = doc;

  const isFolder = doc.type === "CollectionType";
  const isExcluded = doc.exclude_from_search || doc.effective_exclude;
  const pageCount = doc.page_count || 0;

  if (isFolder) {
    el.trayDocIcon.textContent = "📁";
  } else if (doc.file_type === "pdf") {
    el.trayDocIcon.textContent = "📄";
  } else if (doc.file_type === "epub") {
    el.trayDocIcon.textContent = "📚";
  } else {
    el.trayDocIcon.textContent = "📓";
  }

  el.trayDocTitle.textContent = doc.visible_name;
  const statusStr = isExcluded ? "Excluded from Search" : "Indexed";
  el.trayDocMeta.textContent = isFolder 
    ? `Folder • ${statusStr}` 
    : `${doc.file_type === "notebook" ? "Notebook" : (doc.file_type || "Document").toUpperCase()} • ${pageCount} ${pageCount === 1 ? "page" : "pages"} • ${statusStr}`;

  el.trayLabelOpen.textContent = isFolder ? "Open Folder" : "Open & Read";

  if (el.trayBtnReadTab) {
    if (isFolder) {
      el.trayBtnReadTab.style.display = "none";
    } else {
      el.trayBtnReadTab.style.display = "flex";
      el.trayBtnReadTab.href = `/?read=${doc.id}`;
      el.trayBtnReadTab.onclick = () => closeMobileActionTray();
    }
  }

  if (el.trayBtnType) {
    el.trayBtnType.style.display = !isFolder && (doc.file_type === "notebook" || !doc.file_type) ? "flex" : "none";
  }

  if (el.trayBtnOptimize) {
    el.trayBtnOptimize.style.display = !isFolder ? "flex" : "none";
  }

  if (el.trayBtnExport) {
    el.trayBtnExport.style.display = "flex";
    const exportLabel = el.trayBtnExport.querySelector(".tray-btn-text strong");
    const exportDesc = el.trayBtnExport.querySelector(".tray-btn-text span");
    if (exportLabel && exportDesc) {
      if (isFolder) {
        exportLabel.textContent = "Download Folder (ZIP)";
        exportDesc.textContent = "Download complete folder contents recursively";
      } else {
        exportLabel.textContent = "Download Annotated PDF";
        exportDesc.textContent = "Download vector PDF with handwriting";
      }
    }
  }

  if (el.trayBtnExclude) {
    if (isExcluded) {
      el.trayIconExclude.textContent = "✓";
      el.trayLabelExclude.textContent = "Include in Search & Tasks";
      el.trayDescExclude.textContent = "Include in search and task aggregation";
    } else {
      el.trayIconExclude.textContent = "🚫";
      el.trayLabelExclude.textContent = "Exclude from Search & Tasks";
      el.trayDescExclude.textContent = "Hide from search and exclude tasks from task list";
    }
  }

  el.mobileActionTray.style.display = "flex";
  requestAnimationFrame(() => {
    el.mobileActionTray.classList.add("active");
  });
}

function closeMobileActionTray() {
  if (!el.mobileActionTray) return;
  el.mobileActionTray.classList.remove("active");
  setTimeout(() => {
    if (!el.mobileActionTray.classList.contains("active")) {
      el.mobileActionTray.style.display = "none";
    }
  }, 240);
}

if (el.trayBtnCancel) {
  el.trayBtnCancel.addEventListener("click", closeMobileActionTray);
}

if (el.mobileActionTray) {
  el.mobileActionTray.addEventListener("click", (e) => {
    if (e.target === el.mobileActionTray) {
      closeMobileActionTray();
    }
  });
}

if (el.trayBtnOpen) {
  el.trayBtnOpen.addEventListener("click", () => {
    if (!selectedMobileDoc) return;
    const doc = selectedMobileDoc;
    closeMobileActionTray();
    if (doc.type === "CollectionType") {
      state.folderPath.push({ id: doc.id, name: doc.visible_name });
      navigateToFolder(doc.id);
    } else {
      openReader(doc.id);
    }
  });
}

if (el.trayBtnType) {
  el.trayBtnType.addEventListener("click", async () => {
    if (!selectedMobileDoc) return;
    const doc = selectedMobileDoc;
    closeMobileActionTray();
    await openReader(doc.id);
    if (el.btnReaderTypeToggle) {
      el.btnReaderTypeToggle.click();
    }
  });
}

if (el.trayBtnOptimize) {
  el.trayBtnOptimize.addEventListener("click", () => {
    if (!selectedMobileDoc) return;
    const doc = selectedMobileDoc;
    closeMobileActionTray();
    openConverterModal(doc.id, doc.visible_name);
  });
}

if (el.trayBtnExport) {
  el.trayBtnExport.addEventListener("click", () => {
    if (!selectedMobileDoc) return;
    const doc = selectedMobileDoc;
    closeMobileActionTray();
    if (doc.type === "CollectionType") {
      window.open(`/api/documents/${doc.id}/export/zip`, "_blank");
    } else {
      window.open(`/api/documents/${doc.id}/export/pdf?dark=${state.appTheme === "dark"}`, "_blank");
    }
  });
}

if (el.trayBtnExclude) {
  el.trayBtnExclude.addEventListener("click", async () => {
    if (!selectedMobileDoc) return;
    const doc = selectedMobileDoc;
    closeMobileActionTray();
    try {
      await fetch(`/api/documents/${doc.id}/indexing-toggle`, { method: "POST" });
      fetchDocuments();
    } catch (err) {
      console.error("Failed to toggle exclusion", err);
    }
  });
}

if (el.trayBtnMove) {
  el.trayBtnMove.addEventListener("click", () => {
    if (!selectedMobileDoc) return;
    const doc = selectedMobileDoc;
    closeMobileActionTray();
    openMoveFolderModal(doc);
  });
}

if (el.trayBtnDelete) {
  el.trayBtnDelete.addEventListener("click", () => {
    if (!selectedMobileDoc) return;
    const doc = selectedMobileDoc;
    closeMobileActionTray();
    confirmDeleteDocument(doc);
  });
}

// --- Folder Management & Move / Add to Folder Controller ---
let docBeingMoved = null;
let selectedTargetFolderId = null;
let allLibraryFolders = [];

async function openMoveFolderModal(doc) {
  if (!el.moveFolderModal) return;
  docBeingMoved = doc;
  selectedTargetFolderId = null;
  el.btnMoveFolderSubmit.disabled = true;
  el.btnMoveFolderSubmit.textContent = "Move Here";
  el.moveModalDocTitle.textContent = doc.visible_name;
  if (el.inputQuickNewFolder) el.inputQuickNewFolder.value = "";
  if (el.inputFolderSearch) el.inputFolderSearch.value = "";

  el.moveFolderModal.style.display = "flex";

  try {
    const res = await fetch("/api/folders");
    if (!res.ok) return;
    allLibraryFolders = await res.json();
    renderFolderTree();
  } catch (err) {
    console.error("Failed to load folders", err);
  }
}

function closeMoveFolderModal() {
  if (el.moveFolderModal) el.moveFolderModal.style.display = "none";
  docBeingMoved = null;
  selectedTargetFolderId = null;
}

function renderFolderTree() {
  if (!el.folderTreeContainer) return;
  el.folderTreeContainer.innerHTML = "";

  const q = (el.inputFolderSearch ? el.inputFolderSearch.value : "").trim().toLowerCase();

  const rootItem = {
    id: "",
    visible_name: "Home (Root Library)",
    path: "Home",
    depth: 0,
    parent_id: null,
  };

  const isMovingCollection = docBeingMoved && docBeingMoved.type === "CollectionType";
  const movingDocId = docBeingMoved ? docBeingMoved.id : null;
  const currentParentId = docBeingMoved ? (docBeingMoved.parent_id || "") : "";

  // If moving a collection, prevent moving into itself or its descendants
  const invalidFolderIds = new Set();
  if (isMovingCollection && movingDocId) {
    invalidFolderIds.add(movingDocId);
    let added = true;
    while (added) {
      added = false;
      allLibraryFolders.forEach((f) => {
        if (!invalidFolderIds.has(f.id) && invalidFolderIds.has(f.parent_id)) {
          invalidFolderIds.add(f.id);
          added = true;
        }
      });
    }
  }

  const itemsToRender = [rootItem, ...allLibraryFolders].filter((item) => {
    if (!q) return true;
    return item.visible_name.toLowerCase().includes(q) || item.path.toLowerCase().includes(q);
  });

  itemsToRender.forEach((item) => {
    const isCurrent = currentParentId === item.id;
    const isDisabled = isMovingCollection && invalidFolderIds.has(item.id);
    const isSelected = selectedTargetFolderId === item.id;

    const row = document.createElement("div");
    row.className = `folder-tree-item${isSelected ? " selected" : ""}${isDisabled ? " disabled" : ""}`;

    const indentPx = Math.min(item.depth * 18, 120);
    row.style.paddingLeft = `${indentPx + 12}px`;

    const icon = item.id === "" ? "🏠" : "📁";
    let badge = "";
    if (isCurrent) {
      badge = `<span class="folder-tree-badge">Current Location</span>`;
    } else if (isDisabled) {
      badge = `<span class="folder-tree-badge">Cannot move into itself</span>`;
    }

    row.innerHTML = `
      <span>${icon}</span>
      <span class="folder-tree-name" title="${escapeHtml(item.path)}">${escapeHtml(item.visible_name)}</span>
      ${badge}
    `;

    if (!isDisabled) {
      row.addEventListener("click", () => {
        selectedTargetFolderId = item.id;
        el.btnMoveFolderSubmit.disabled = false;
        el.btnMoveFolderSubmit.textContent = item.id === "" ? "Move to Home" : `Move to "${item.visible_name}"`;
        document.querySelectorAll(".folder-tree-item").forEach((r) => r.classList.remove("selected"));
        row.classList.add("selected");
      });
    }

    el.folderTreeContainer.appendChild(row);
  });
}

if (el.btnMoveFolderClose) {
  el.btnMoveFolderClose.addEventListener("click", closeMoveFolderModal);
}

if (el.btnMoveFolderCancel) {
  el.btnMoveFolderCancel.addEventListener("click", closeMoveFolderModal);
}

if (el.moveFolderModal) {
  el.moveFolderModal.addEventListener("click", (e) => {
    if (e.target === el.moveFolderModal) closeMoveFolderModal();
  });
}

if (el.inputFolderSearch) {
  el.inputFolderSearch.addEventListener("input", renderFolderTree);
}

if (el.btnMoveFolderSubmit) {
  el.btnMoveFolderSubmit.addEventListener("click", async () => {
    if (!docBeingMoved || selectedTargetFolderId === null) return;
    try {
      el.btnMoveFolderSubmit.disabled = true;
      el.btnMoveFolderSubmit.textContent = "Moving...";
      const res = await fetch(`/api/documents/${docBeingMoved.id}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parent_id: selectedTargetFolderId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to move item");
        return;
      }
      closeMoveFolderModal();
      await fetchDocuments();
    } catch (err) {
      console.error("Failed to move item", err);
      alert("Error moving item");
    } finally {
      if (el.btnMoveFolderSubmit) el.btnMoveFolderSubmit.disabled = false;
    }
  });
}

if (el.formQuickNewFolder) {
  el.formQuickNewFolder.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = (el.inputQuickNewFolder.value || "").trim();
    if (!name) return;
    try {
      const parentId = selectedTargetFolderId !== null ? selectedTargetFolderId : (docBeingMoved ? docBeingMoved.parent_id : "");
      const res = await fetch("/api/folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, parent_id: parentId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to create folder");
        return;
      }
      const data = await res.json();
      el.inputQuickNewFolder.value = "";
      const treeRes = await fetch("/api/folders");
      allLibraryFolders = await treeRes.json();
      selectedTargetFolderId = data.folder.id;
      renderFolderTree();
      el.btnMoveFolderSubmit.disabled = false;
      el.btnMoveFolderSubmit.textContent = `Move to "${data.folder.visible_name}"`;
    } catch (err) {
      console.error("Failed to create folder", err);
    }
  });
}

// Standalone New Folder Modal
function openNewFolderModal() {
  if (!el.newFolderModal) return;
  if (el.inputNewFolderName) el.inputNewFolderName.value = "";
  const currentFolderName = state.folderPath.length > 0 ? state.folderPath[state.folderPath.length - 1].name : "Home";
  if (el.newFolderLocationHint) {
    el.newFolderLocationHint.textContent = `Location: ${currentFolderName}`;
  }
  el.newFolderModal.style.display = "flex";
  if (el.inputNewFolderName) el.inputNewFolderName.focus();
}

function closeNewFolderModal() {
  if (el.newFolderModal) el.newFolderModal.style.display = "none";
}

if (el.btnNewFolder) {
  el.btnNewFolder.addEventListener("click", openNewFolderModal);
}

if (el.btnNewFolderClose) {
  el.btnNewFolderClose.addEventListener("click", closeNewFolderModal);
}

if (el.btnNewFolderCancel) {
  el.btnNewFolderCancel.addEventListener("click", closeNewFolderModal);
}

if (el.newFolderModal) {
  el.newFolderModal.addEventListener("click", (e) => {
    if (e.target === el.newFolderModal) closeNewFolderModal();
  });
}

if (el.formNewFolder) {
  el.formNewFolder.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = (el.inputNewFolderName.value || "").trim();
    if (!name) return;
    try {
      const res = await fetch("/api/folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, parent_id: state.currentFolder }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to create folder");
        return;
      }
      closeNewFolderModal();
      await fetchDocuments();
    } catch (err) {
      console.error("Failed to create folder", err);
    }
  });
}

// Confirmation and Document Deletion
async function confirmDeleteDocument(doc) {
  const isFolder = doc.type === "CollectionType";
  const confirmMsg = isFolder
    ? `Delete folder "${doc.visible_name}" and all its contents?\n\nThis will remove all nested documents and subfolders from your library.`
    : `Are you sure you want to delete "${doc.visible_name}"?`;

  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch(`/api/documents/${doc.id}`, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || "Failed to delete item");
      return;
    }
    await fetchDocuments();
  } catch (err) {
    console.error("Failed to delete item", err);
    alert("Error deleting item");
  }
}

// --- Mobile Reader Options Controller ---
function openReaderOptionsTray() {
  if (!el.readerOptionsTray || !state.currentDoc) return;

  if (el.trayReaderDarkLabel) {
    el.trayReaderDarkLabel.textContent = `Inverted Dark Mode: ${state.pageDarkMode ? "On" : "Off"}`;
  }
  if (el.trayReaderFitLabel) {
    el.trayReaderFitLabel.textContent = `Fit Mode: ${state.fitMode === "width" ? "Fit Width" : "Fit Page"}`;
  }
  if (el.trayReaderExcludeLabel) {
    const isExcluded = state.currentDoc.exclude_from_search || state.currentDoc.effective_exclude;
    el.trayReaderExcludeLabel.textContent = isExcluded ? "✓ Include in Search" : "🚫 Exclude from Search";
  }

  el.readerOptionsTray.style.display = "flex";
  requestAnimationFrame(() => {
    el.readerOptionsTray.classList.add("active");
  });
}

function closeReaderOptionsTray() {
  if (!el.readerOptionsTray) return;
  el.readerOptionsTray.classList.remove("active");
  setTimeout(() => {
    if (!el.readerOptionsTray.classList.contains("active")) {
      el.readerOptionsTray.style.display = "none";
    }
  }, 240);
}

if (el.btnReaderMoreMobile) {
  el.btnReaderMoreMobile.addEventListener("click", openReaderOptionsTray);
}

if (el.btnReaderTypeMobile) {
  el.btnReaderTypeMobile.addEventListener("click", () => {
    if (el.btnReaderTypeToggle) el.btnReaderTypeToggle.click();
  });
}

if (el.trayReaderDarkToggle) {
  el.trayReaderDarkToggle.addEventListener("click", () => {
    closeReaderOptionsTray();
    if (el.btnPageDarkToggle) el.btnPageDarkToggle.click();
  });
}

if (el.trayReaderFitToggle) {
  el.trayReaderFitToggle.addEventListener("click", () => {
    closeReaderOptionsTray();
    if (el.btnFitToggle) el.btnFitToggle.click();
  });
}

if (el.trayReaderConvert) {
  el.trayReaderConvert.addEventListener("click", () => {
    closeReaderOptionsTray();
    if (state.currentDoc) openConverterModal(state.currentDoc.id, state.currentDoc.visible_name);
  });
}

if (el.trayReaderExclude) {
  el.trayReaderExclude.addEventListener("click", () => {
    closeReaderOptionsTray();
    if (el.btnReaderExcludeToggle) el.btnReaderExcludeToggle.click();
  });
}

if (el.trayReaderExport) {
  el.trayReaderExport.addEventListener("click", () => {
    closeReaderOptionsTray();
    if (el.btnExportPdf) el.btnExportPdf.click();
  });
}

if (el.trayReaderClose) {
  el.trayReaderClose.addEventListener("click", closeReaderOptionsTray);
}

if (el.readerOptionsTray) {
  el.readerOptionsTray.addEventListener("click", (e) => {
    if (e.target === el.readerOptionsTray) closeReaderOptionsTray();
  });
}

// Sort Selector
if (el.selectSort) {
  el.selectSort.addEventListener("change", (e) => {
    state.currentSort = e.target.value;
    fetchDocuments();
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

    try {
      const url = new URL(window.location.href);
      url.searchParams.set("read", docId);
      if (initialPageIdx > 0) url.searchParams.set("page", initialPageIdx);
      else url.searchParams.delete("page");
      window.history.replaceState({ docId, pageIdx: initialPageIdx }, "", url.toString());
    } catch (_) {}
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
  if (state.isFullscreen) {
    toggleFullscreenMode(false);
  }
  el.readerView.style.display = "none";
  if (el.readerTypingPane) el.readerTypingPane.style.display = "none";
  if (el.btnReaderTypeToggle) {
    el.btnReaderTypeToggle.classList.remove("active");
    el.btnReaderTypeToggle.textContent = "⌨ Type";
  }
  state.currentDoc = null;
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete("read");
    url.searchParams.delete("page");
    url.searchParams.delete("doc");
    window.history.replaceState({}, "", url.pathname + (url.search ? url.search : ""));
  } catch (_) {}
}

el.btnReaderClose.addEventListener("click", () => {
  if (state.isFullscreen) {
    toggleFullscreenMode(false);
  } else {
    closeReader();
  }
});

async function loadCurrentPage() {
  if (!state.currentDoc) return;
  const pages = (state.currentDoc.pages || []).filter((p) => !p.deleted);
  const totalPages = Math.max(pages.length, 1);
  const pageIdx = Math.min(state.currentPageIdx, totalPages - 1);
  state.currentPageIdx = pageIdx;

  el.readerPageIndicator.textContent = `Page ${pageIdx + 1} of ${totalPages}`;
  el.btnPagePrev.disabled = pageIdx <= 0;
  el.btnPageNext.disabled = pageIdx >= totalPages - 1;

  if (state.isFullscreen) {
    flashPageIndicator();
  }

  try {
    const url = new URL(window.location.href);
    if (url.searchParams.get("read") === state.currentDoc.id) {
      if (pageIdx > 0) url.searchParams.set("page", pageIdx);
      else url.searchParams.delete("page");
      window.history.replaceState({ docId: state.currentDoc.id, pageIdx }, "", url.toString());
    }
  } catch (_) {}

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

// --- Fullscreen Reading Mode Controller ---
function flashPageIndicator() {
  if (!state.isFullscreen || !el.readerNav) return;
  el.readerNav.classList.add("flash-visible");
  if (state.pageIndicatorTimeout) clearTimeout(state.pageIndicatorTimeout);
  state.pageIndicatorTimeout = setTimeout(() => {
    if (el.readerNav) el.readerNav.classList.remove("flash-visible");
  }, 1800);
}

function toggleFullscreenMode(forceState = null) {
  const next = forceState !== null ? forceState : !state.isFullscreen;
  state.isFullscreen = next;

  if (state.isFullscreen) {
    el.readerView.classList.add("is-fullscreen");
    el.readerView.classList.remove("show-hud");
    if (el.readerClickZones) el.readerClickZones.style.display = "flex";

    try {
      if (!document.fullscreenElement && el.readerView.requestFullscreen) {
        el.readerView.requestFullscreen().catch(() => {});
      }
    } catch (_) {}

    flashPageIndicator();
  } else {
    el.readerView.classList.remove("is-fullscreen", "show-hud");
    if (el.readerNav) el.readerNav.classList.remove("flash-visible");
    if (el.readerClickZones) el.readerClickZones.style.display = "none";

    try {
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
    } catch (_) {}

    if (state.hudTimeout) {
      clearTimeout(state.hudTimeout);
      state.hudTimeout = null;
    }
  }

  if (el.btnFullscreenLabel) {
    el.btnFullscreenLabel.textContent = state.isFullscreen ? "Exit Fullscreen" : "Fullscreen";
  }
  if (el.trayReaderFullscreenLabel) {
    el.trayReaderFullscreenLabel.textContent = state.isFullscreen ? "Exit Fullscreen" : "Fullscreen Reading Mode";
  }
  if (el.btnReaderCloseText) {
    el.btnReaderCloseText.textContent = state.isFullscreen ? "Exit Fullscreen" : "Library";
  }
}

function showHud() {
  if (!state.isFullscreen) return;
  el.readerView.classList.add("show-hud");
  scheduleHudHide();
}

function scheduleHudHide() {
  if (state.hudTimeout) clearTimeout(state.hudTimeout);
  state.hudTimeout = setTimeout(() => {
    if (state.isFullscreen && el.readerView) {
      el.readerView.classList.remove("show-hud");
    }
  }, 3000);
}

function toggleHud() {
  if (!state.isFullscreen) return;
  if (el.readerView.classList.contains("show-hud")) {
    el.readerView.classList.remove("show-hud");
    if (state.hudTimeout) clearTimeout(state.hudTimeout);
  } else {
    showHud();
  }
}

if (el.btnReaderFullscreen) {
  el.btnReaderFullscreen.addEventListener("click", () => toggleFullscreenMode());
}

if (el.btnReaderFullscreenMobile) {
  el.btnReaderFullscreenMobile.addEventListener("click", () => toggleFullscreenMode());
}

if (el.trayReaderFullscreen) {
  el.trayReaderFullscreen.addEventListener("click", () => {
    closeReaderOptionsTray();
    toggleFullscreenMode();
  });
}

if (el.readerView) {
  el.readerView.addEventListener("mousemove", (e) => {
    if (!state.isFullscreen) return;
    if (e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents) return;
    if (e.clientY < 60 || e.clientY > window.innerHeight - 60) {
      showHud();
    }
  });
}

if (el.zonePrev) {
  el.zonePrev.addEventListener("click", (e) => {
    e.stopPropagation();
    if (state.currentPageIdx > 0) {
      state.currentPageIdx--;
      loadCurrentPage();
    }
  });
}

if (el.zoneNext) {
  el.zoneNext.addEventListener("click", (e) => {
    e.stopPropagation();
    const pages = (state.currentDoc?.pages || []).filter((p) => !p.deleted);
    if (state.currentPageIdx < pages.length - 1) {
      state.currentPageIdx++;
      loadCurrentPage();
    }
  });
}

if (el.zoneCenter) {
  el.zoneCenter.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleHud();
  });
}

document.addEventListener("fullscreenchange", () => {
  if (!document.fullscreenElement && state.isFullscreen) {
    toggleFullscreenMode(false);
  }
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

if (el.btnOpenConverter) {
  el.btnOpenConverter.addEventListener("click", () => {
    if (el.newItemDropdown) el.newItemDropdown.style.display = "none";
    openConverterModal();
  });
}
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

// --- Search Implementation ---
let searchDebounce = null;

function triggerSearch() {
  clearTimeout(searchDebounce);
  const q = el.searchInput.value.trim();
  if (el.btnSearchClear) {
    el.btnSearchClear.style.display = q.length > 0 ? "block" : "none";
  }
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

// Search clear button
if (el.btnSearchClear) {
  el.btnSearchClear.addEventListener("click", () => {
    el.searchInput.value = "";
    el.btnSearchClear.style.display = "none";
    el.searchDropdown.style.display = "none";
    el.searchInput.focus();
  });
}

// --- Keyboard Shortcuts ---
window.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== el.searchInput && el.readerView.style.display !== "flex") {
    e.preventDefault();
    el.searchInput.focus();
    el.searchInput.select();
    return;
  }

  if (el.authModal.style.display === "flex") {
    if (e.key === "Escape") closeAuthModal();
    return;
  }
  if (el.converterModal.style.display === "flex") {
    if (e.key === "Escape") closeConverterModal();
    return;
  }
  if (el.quickCaptureModal && el.quickCaptureModal.style.display === "flex") {
    if (e.key === "Escape") closeQuickCapture();
    return;
  }

  if ((e.key === "c" || e.key === "C") && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA" && el.readerView.style.display !== "flex") {
    e.preventDefault();
    openQuickCapture();
    return;
  }

  if (el.readerView.style.display === "flex") {
    if (e.key === "Escape") {
      if (state.isFullscreen) {
        toggleFullscreenMode(false);
      } else {
        closeReader();
      }
    } else if (e.key === "f" || e.key === "F") {
      if (e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
        e.preventDefault();
        toggleFullscreenMode();
      }
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

// --- Tasks Controller ---
function openTasksModal() {
  if (el.tasksModal) el.tasksModal.style.display = "flex";
  fetchTasks();
}

function closeTasksModal() {
  if (el.tasksModal) el.tasksModal.style.display = "none";
}

if (el.btnTasksToggle) el.btnTasksToggle.addEventListener("click", openTasksModal);
if (el.btnTasksClose) el.btnTasksClose.addEventListener("click", closeTasksModal);
if (el.btnTasksDone) el.btnTasksDone.addEventListener("click", closeTasksModal);

el.taskFilterPills.forEach((pill) => {
  pill.addEventListener("click", () => {
    el.taskFilterPills.forEach((p) => p.classList.remove("active"));
    pill.classList.add("active");
    state.currentTaskFilter = pill.getAttribute("data-task-filter") || "open";
    fetchTasks();
  });
});

async function fetchTasks() {
  try {
    const url = new URL("/api/tasks", window.location.origin);
    if (state.currentTaskFilter !== "all") {
      url.searchParams.set("status", state.currentTaskFilter);
    }
    const res = await fetch(url);
    if (!res.ok) return;
    const tasks = await res.json();

    let openCount = 0;
    if (state.currentTaskFilter === "open") {
      openCount = tasks.length;
    } else {
      const openRes = await fetch("/api/tasks?status=open");
      if (openRes.ok) {
        const openTasks = await openRes.json();
        openCount = openTasks.length;
      }
    }

    if (el.tasksBadge) {
      el.tasksBadge.textContent = openCount;
      el.tasksBadge.style.display = openCount > 0 ? "inline-block" : "none";
    }
    if (el.tasksCountPill) {
      el.tasksCountPill.textContent = `${openCount} Open`;
    }

    renderTasks(tasks);
  } catch (err) {
    console.error("Failed to fetch tasks", err);
  }
}

function renderTasks(tasks) {
  if (!el.tasksList) return;
  el.tasksList.innerHTML = "";

  if (tasks.length === 0) {
    el.tasksList.innerHTML = `
      <div class="tasks-empty">
        <p style="font-size: 1.1rem; margin-bottom: 0.4rem;">No tasks found</p>
        <p style="font-size: 0.82rem; color: var(--text-muted);">
          Mark items in your notebooks with <code style="color: var(--accent);">*</code> or checkboxes <code style="color: var(--accent);">[ ]</code> to consolidate them here.
        </p>
      </div>
    `;
    return;
  }

  tasks.forEach((t) => {
    const isDone = t.status === "completed";
    const item = document.createElement("div");
    item.className = `task-item ${isDone ? "task-completed" : ""}`;

    const markerIcon = t.marker_type === "star" ? "★" : (t.marker_type === "todo" ? "⚡" : "☐");

    item.innerHTML = `
      <input type="checkbox" class="task-checkbox" ${isDone ? "checked" : ""} aria-label="Toggle task completion">
      <div class="task-content">
        <div class="task-text">${escapeHtml(t.clean_text || t.raw_text)}</div>
        <div class="task-meta">
          <span title="Detected via ${t.marker_type}">${markerIcon}</span>
          <span>From:</span>
          <span class="task-source-link" title="Open source page">${escapeHtml(t.doc_name || "Document")} (p. ${t.page_idx + 1})</span>
        </div>
      </div>
      <button class="btn-task-delete" title="Delete task">✕</button>
    `;

    // Checkbox toggle
    const chk = item.querySelector(".task-checkbox");
    chk.addEventListener("change", async () => {
      const newStatus = chk.checked ? "completed" : "open";
      await fetch(`/api/tasks/${t.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      fetchTasks();
    });

    // Jump to source page in reader
    const link = item.querySelector(".task-source-link");
    link.addEventListener("click", () => {
      closeTasksModal();
      openReader(t.doc_id, t.page_idx);
    });

    // Delete
    const btnDel = item.querySelector(".btn-task-delete");
    btnDel.addEventListener("click", async () => {
      await fetch(`/api/tasks/${t.id}`, { method: "DELETE" });
      fetchTasks();
    });

    el.tasksList.appendChild(item);
  });
}

if (el.btnTasksScanAll) {
  el.btnTasksScanAll.addEventListener("click", async () => {
    el.btnTasksScanAll.disabled = true;
    el.btnTasksScanAll.textContent = "Scanning...";
    try {
      const res = await fetch("/api/tasks/scan-all", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        alert(`Task scan complete! Found ${data.tasks_found} tasks.`);
        fetchTasks();
      }
    } catch (e) {
      alert(`Scan failed: ${e.message}`);
    } finally {
      el.btnTasksScanAll.disabled = false;
      el.btnTasksScanAll.textContent = "⚡ Scan Documents for Tasks";
    }
  });
}

// --- Vision Settings Controller ---
function openSettingsModal() {
  if (el.settingsModal) el.settingsModal.style.display = "flex";
  loadVisionSettings();
}

function closeSettingsModal() {
  if (el.settingsModal) el.settingsModal.style.display = "none";
}

if (el.btnSettingsToggle) el.btnSettingsToggle.addEventListener("click", openSettingsModal);
if (el.btnSettingsClose) el.btnSettingsClose.addEventListener("click", closeSettingsModal);

if (el.settingsProvider) {
  el.settingsProvider.addEventListener("change", () => {
    const isOllama = el.settingsProvider.value === "openai";
    if (el.settingsBaseUrlGroup) {
      el.settingsBaseUrlGroup.style.display = isOllama ? "block" : "none";
    }
    if (el.settingsModel && !el.settingsModel.value) {
      el.settingsModel.value = isOllama ? "gpt-4o-mini" : "gemini-2.0-flash";
    }
  });
}

async function loadVisionSettings() {
  try {
    const res = await fetch("/api/settings/vision");
    if (!res.ok) return;
    const conf = await res.json();

    if (el.settingsProvider) el.settingsProvider.value = conf.provider || "gemini";
    if (el.settingsModel) el.settingsModel.value = conf.model || "gemini-2.0-flash";
    if (el.settingsBaseUrl) el.settingsBaseUrl.value = conf.base_url || "";
    if (el.settingsBaseUrlGroup) {
      el.settingsBaseUrlGroup.style.display = conf.provider === "openai" ? "block" : "none";
    }

    if (el.settingsKeyStatus) {
      if (conf.api_key_set) {
        el.settingsKeyStatus.textContent = `✓ Key saved: ${conf.api_key_masked}`;
        el.settingsKeyStatus.style.color = "var(--success)";
      } else {
        el.settingsKeyStatus.textContent = "No API key configured (cloud handwriting OCR inactive)";
        el.settingsKeyStatus.style.color = "var(--text-muted)";
      }
    }
  } catch (e) {
    console.error("Failed to load vision settings", e);
  }
}

if (el.btnSettingsSave) {
  el.btnSettingsSave.addEventListener("click", async () => {
    const payload = {
      provider: el.settingsProvider ? el.settingsProvider.value : "gemini",
      model: el.settingsModel ? el.settingsModel.value.trim() : "gemini-2.0-flash",
      api_key: el.settingsApiKey ? el.settingsApiKey.value.trim() : "",
      base_url: el.settingsBaseUrl ? el.settingsBaseUrl.value.trim() : "",
    };

    try {
      const res = await fetch("/api/settings/vision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        if (el.settingsApiKey) el.settingsApiKey.value = "";
        await loadVisionSettings();
        alert("Vision settings saved successfully!");
        closeSettingsModal();
      } else {
        alert("Failed to save settings");
      }
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  });
}

if (el.btnSettingsTest) {
  el.btnSettingsTest.addEventListener("click", async () => {
    el.btnSettingsTest.disabled = true;
    el.btnSettingsTest.textContent = "Testing...";
    if (el.settingsTestResult) {
      el.settingsTestResult.style.display = "block";
      el.settingsTestResult.style.backgroundColor = "var(--bg-tertiary)";
      el.settingsTestResult.style.color = "var(--text-secondary)";
      el.settingsTestResult.textContent = "Sending test image to vision provider...";
    }

    const payload = {
      provider: el.settingsProvider ? el.settingsProvider.value : "gemini",
      model: el.settingsModel ? el.settingsModel.value.trim() : "gemini-2.0-flash",
      api_key: el.settingsApiKey ? el.settingsApiKey.value.trim() : "",
      base_url: el.settingsBaseUrl ? el.settingsBaseUrl.value.trim() : "",
    };

    try {
      const res = await fetch("/api/settings/vision/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok) {
        el.settingsTestResult.style.backgroundColor = "rgba(34, 197, 94, 0.15)";
        el.settingsTestResult.style.color = "var(--success)";
        el.settingsTestResult.textContent = `✓ Success! Connected in ${data.latency_s}s. Reply: "${data.reply}"`;
      } else {
        el.settingsTestResult.style.backgroundColor = "var(--danger-bg)";
        el.settingsTestResult.style.color = "var(--danger)";
        el.settingsTestResult.textContent = `✕ Connection test failed: ${data.detail || "Error"}`;
      }
    } catch (e) {
      if (el.settingsTestResult) {
        el.settingsTestResult.style.backgroundColor = "var(--danger-bg)";
        el.settingsTestResult.style.color = "var(--danger)";
        el.settingsTestResult.textContent = `✕ Error: ${e.message}`;
      }
    } finally {
      el.btnSettingsTest.disabled = false;
      el.btnSettingsTest.textContent = "Test Connection";
    }
  });
}

// --- Phase 4: Typed Notebook Editor & Markdown Import ---
async function loadTypingPaneText() {
  if (!state.currentDoc) return;
  const pageIdx = state.currentPageIdx || 0;
  if (!el.typingPaneTextarea) return;

  try {
    const res = await fetch(`/api/documents/${state.currentDoc.id}/pages/${pageIdx}/text`);
    if (res.ok) {
      const data = await res.json();
      el.typingPaneTextarea.value = data.text || "";
    } else {
      el.typingPaneTextarea.value = "";
    }
  } catch (e) {
    console.error("Failed to fetch page text", e);
  }
}

if (el.btnReaderTypeToggle) {
  el.btnReaderTypeToggle.addEventListener("click", () => {
    if (!el.readerTypingPane) return;
    const isVisible = el.readerTypingPane.style.display !== "none";
    if (isVisible) {
      el.readerTypingPane.style.display = "none";
      el.btnReaderTypeToggle.classList.remove("active");
      el.btnReaderTypeToggle.textContent = "⌨ Type";
    } else {
      el.readerTypingPane.style.display = "flex";
      el.btnReaderTypeToggle.classList.add("active");
      el.btnReaderTypeToggle.textContent = "✕ Close";
      loadTypingPaneText();
      if (el.typingPaneTextarea) el.typingPaneTextarea.focus();
    }
  });
}

if (el.btnTypingDiscard) {
  el.btnTypingDiscard.addEventListener("click", () => {
    if (el.readerTypingPane) el.readerTypingPane.style.display = "none";
    if (el.btnReaderTypeToggle) {
      el.btnReaderTypeToggle.classList.remove("active");
      el.btnReaderTypeToggle.textContent = "⌨ Type";
    }
  });
}

if (el.btnTypingSave) {
  el.btnTypingSave.addEventListener("click", async () => {
    if (!state.currentDoc || !el.typingPaneTextarea) return;
    const pageIdx = state.currentPageIdx || 0;
    const newText = el.typingPaneTextarea.value;

    el.btnTypingSave.disabled = true;
    el.btnTypingSave.textContent = "Saving...";

    try {
      const res = await fetch(`/api/documents/${state.currentDoc.id}/pages/${pageIdx}/text`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: newText }),
      });
      if (res.ok) {
        // Refresh page SVG render
        await loadCurrentPage();
        fetchTasks();
        if (el.readerTypingPane) el.readerTypingPane.style.display = "none";
        if (el.btnReaderTypeToggle) {
          el.btnReaderTypeToggle.classList.remove("active");
          el.btnReaderTypeToggle.textContent = "⌨ Type";
        }
      } else {
        alert("Failed to save typed text");
      }
    } catch (e) {
      alert(`Error saving text: ${e.message}`);
    } finally {
      el.btnTypingSave.disabled = false;
      el.btnTypingSave.textContent = "Save & Apply";
    }
  });
}

// New Notebook Modal
function openNewNotebookModal() {
  if (!el.newNotebookModal) return;
  if (el.newNotebookTitle) el.newNotebookTitle.value = "";
  if (el.newNotebookContent) el.newNotebookContent.value = "";

  // Populate folder selector
  if (el.newNotebookParent) {
    el.newNotebookParent.innerHTML = '<option value="">(Root Library)</option>';
    const folders = (state.allDocuments || []).filter((d) => d.type === "CollectionType" && !d.deleted);
    for (const f of folders) {
      const opt = document.createElement("option");
      opt.value = f.id;
      opt.textContent = `📁 ${f.visible_name}`;
      if (f.id === state.currentFolderId) {
        opt.selected = true;
      }
      el.newNotebookParent.appendChild(opt);
    }
  }

  el.newNotebookModal.style.display = "flex";
  if (el.newNotebookTitle) el.newNotebookTitle.focus();
}

function closeNewNotebookModal() {
  if (el.newNotebookModal) el.newNotebookModal.style.display = "none";
}

if (el.btnNewNotebook) {
  el.btnNewNotebook.addEventListener("click", openNewNotebookModal);
}
if (el.btnNewNotebookClose) {
  el.btnNewNotebookClose.addEventListener("click", closeNewNotebookModal);
}
if (el.btnNewNotebookCancel) {
  el.btnNewNotebookCancel.addEventListener("click", closeNewNotebookModal);
}

// Import .md file into new notebook
if (el.btnImportFileTrigger && el.mdFileInput) {
  el.btnImportFileTrigger.addEventListener("click", () => el.mdFileInput.click());
  el.mdFileInput.addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      if (el.newNotebookContent) el.newNotebookContent.value = evt.target.result;
      if (el.newNotebookTitle && !el.newNotebookTitle.value.trim()) {
        el.newNotebookTitle.value = file.name.replace(/\.[^/.]+$/, "");
      }
    };
    reader.readAsText(file);
  });
}

// Submit New Notebook
if (el.btnNewNotebookSubmit) {
  el.btnNewNotebookSubmit.addEventListener("click", async () => {
    const title = el.newNotebookTitle ? el.newNotebookTitle.value.trim() : "";
    const parentId = el.newNotebookParent ? el.newNotebookParent.value : "";
    const content = el.newNotebookContent ? el.newNotebookContent.value : "";

    el.btnNewNotebookSubmit.disabled = true;
    el.btnNewNotebookSubmit.textContent = "Creating...";

    try {
      const res = await fetch("/api/documents/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title || "Untitled Notebook",
          parent_id: parentId,
          initial_text: content,
        }),
      });

      if (res.ok) {
        const newDoc = await res.json();
        closeNewNotebookModal();
        await fetchDocuments();
        fetchTasks();
        openReader(newDoc.id, 0);
      } else {
        alert("Failed to create notebook");
      }
    } catch (e) {
      alert(`Error creating notebook: ${e.message}`);
    } finally {
      el.btnNewNotebookSubmit.disabled = false;
      el.btnNewNotebookSubmit.textContent = "Create Notebook";
    }
  });
}

// Tasks Quick Add Form
if (el.taskQuickAddForm) {
  el.taskQuickAddForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!el.taskQuickInput) return;
    const text = el.taskQuickInput.value.trim();
    if (!text) return;

    if (el.btnTaskQuickAdd) {
      el.btnTaskQuickAdd.disabled = true;
      el.btnTaskQuickAdd.textContent = "Adding...";
    }

    try {
      const res = await fetch("/api/tasks/create-item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, notebook_title: "Tasks" }),
      });
      if (res.ok) {
        el.taskQuickInput.value = "";
        await fetchTasks();
      } else {
        alert("Failed to add task");
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      if (el.btnTaskQuickAdd) {
        el.btnTaskQuickAdd.disabled = false;
        el.btnTaskQuickAdd.textContent = "Add Task";
      }
    }
  });
}

// Consolidate All Open Tasks to 'Tasks' Notebook
if (el.btnSyncTasksNotebook) {
  el.btnSyncTasksNotebook.addEventListener("click", async () => {
    el.btnSyncTasksNotebook.disabled = true;
    el.btnSyncTasksNotebook.textContent = "Consolidating...";

    try {
      const res = await fetch("/api/tasks/export-to-notebook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notebook_title: "Tasks" }),
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Successfully synced ${data.result.task_count} tasks to 'Tasks' notebook!`);
        fetchDocuments();
      } else {
        alert("Failed to sync tasks to notebook");
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      el.btnSyncTasksNotebook.disabled = false;
      el.btnSyncTasksNotebook.textContent = "📓 Sync to 'Tasks' Notebook";
    }
  });
}

// --- Quick Capture Controller ---
function openQuickCapture(mode = "task") {
  state.qcMode = mode;
  updateQcModeUI();
  if (el.qcInput) {
    el.qcInput.value = "";
  }
  if (el.quickCaptureModal) {
    el.quickCaptureModal.style.display = "flex";
    setTimeout(() => {
      if (el.qcInput) el.qcInput.focus();
    }, 60);
  }
}

function closeQuickCapture() {
  if (el.quickCaptureModal) {
    el.quickCaptureModal.style.display = "none";
  }
}

function updateQcModeUI() {
  if (el.qcModeTask && el.qcModeNote) {
    if (state.qcMode === "task") {
      el.qcModeTask.classList.add("btn-primary");
      el.qcModeNote.classList.remove("btn-primary");
      if (el.qcNoteOptions) el.qcNoteOptions.style.display = "none";
      if (el.qcInput) el.qcInput.placeholder = "What's on your mind? (Press Ctrl+Enter to save to 'Tasks' notebook)";
    } else {
      el.qcModeNote.classList.add("btn-primary");
      el.qcModeTask.classList.remove("btn-primary");
      if (el.qcNoteOptions) el.qcNoteOptions.style.display = "block";
      if (el.qcInput) el.qcInput.placeholder = "Write a quick note... (Press Ctrl+Enter to save to 'Quick Notes')";
    }
  }
}

async function handleQuickCaptureSubmit() {
  if (!el.qcInput) return;
  const text = el.qcInput.value.trim();
  if (!text) return;

  const isTask = state.qcMode === "task";
  const notebookTitle = isTask
    ? "Tasks"
    : (el.qcNotebookTitle ? el.qcNotebookTitle.value.trim() || "Quick Notes" : "Quick Notes");

  if (el.btnModalQcSave) {
    el.btnModalQcSave.disabled = true;
    el.btnModalQcSave.textContent = "Saving...";
  }

  try {
    const res = await fetch("/api/notes/quick-capture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        is_task: isTask,
        notebook_title: notebookTitle,
      }),
    });
    if (res.ok) {
      closeQuickCapture();
      if (isTask) {
        await fetchTasks();
      } else {
        await fetchDocuments();
      }
    } else {
      const err = await res.json().catch(() => ({}));
      alert(`Capture failed: ${err.detail || "Server error"}`);
    }
  } catch (err) {
    alert(`Capture error: ${err.message}`);
  } finally {
    if (el.btnModalQcSave) {
      el.btnModalQcSave.disabled = false;
      el.btnModalQcSave.textContent = "Save to Tablet";
    }
  }
}

if (el.btnQuickCapture) {
  el.btnQuickCapture.addEventListener("click", () => openQuickCapture("task"));
}
if (el.btnModalQcClose) {
  el.btnModalQcClose.addEventListener("click", closeQuickCapture);
}
if (el.btnModalQcCancel) {
  el.btnModalQcCancel.addEventListener("click", closeQuickCapture);
}
if (el.btnModalQcSave) {
  el.btnModalQcSave.addEventListener("click", handleQuickCaptureSubmit);
}
if (el.qcModeTask) {
  el.qcModeTask.addEventListener("click", () => {
    state.qcMode = "task";
    updateQcModeUI();
    if (el.qcInput) el.qcInput.focus();
  });
}
if (el.qcModeNote) {
  el.qcModeNote.addEventListener("click", () => {
    state.qcMode = "note";
    updateQcModeUI();
    if (el.qcInput) el.qcInput.focus();
  });
}
if (el.qcInput) {
  el.qcInput.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleQuickCaptureSubmit();
    }
  });
}

// --- Split Button for Creation ---
if (el.btnNewDropdownToggle && el.newItemDropdown) {
  el.btnNewDropdownToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    const isVisible = el.newItemDropdown.style.display === "flex";
    el.newItemDropdown.style.display = isVisible ? "none" : "flex";
  });
}

document.addEventListener("click", (e) => {
  if (el.newItemDropdown && !e.target.closest("#new-item-split-btn")) {
    el.newItemDropdown.style.display = "none";
  }
});

if (el.menuNewNote) {
  el.menuNewNote.addEventListener("click", () => {
    if (el.newItemDropdown) el.newItemDropdown.style.display = "none";
    if (el.btnNewNotebook) el.btnNewNotebook.click();
  });
}

if (el.menuNewFolder) {
  el.menuNewFolder.addEventListener("click", () => {
    if (el.newItemDropdown) el.newItemDropdown.style.display = "none";
    if (el.btnNewFolder) el.btnNewFolder.click();
  });
}

if (el.menuBulkImport) {
  el.menuBulkImport.addEventListener("click", () => {
    if (el.newItemDropdown) el.newItemDropdown.style.display = "none";
    openBulkImportModal();
  });
}

// --- Bulk Import Controller ---
async function openBulkImportModal() {
  if (!el.bulkImportModal) return;
  if (el.bulkImportFiles) el.bulkImportFiles.value = "";
  if (el.bulkImportFileCount) el.bulkImportFileCount.textContent = "0 files selected";
  if (el.bulkImportStatus) el.bulkImportStatus.style.display = "none";
  if (el.btnBulkImportSubmit) el.btnBulkImportSubmit.disabled = true;

  if (el.bulkImportFolder) {
    el.bulkImportFolder.innerHTML = `<option value="">(Home / Root)</option>`;
    try {
      const res = await fetch("/api/folders");
      if (res.ok) {
        const folders = await res.json();
        folders.forEach((f) => {
          const opt = document.createElement("option");
          opt.value = f.id;
          const prefix = f.depth > 0 ? "— ".repeat(f.depth) : "";
          opt.textContent = `${prefix}${f.name}`;
          if (f.id === state.currentFolder) opt.selected = true;
          el.bulkImportFolder.appendChild(opt);
        });
      }
    } catch (err) {
      console.debug("Failed to load folders for bulk import", err);
    }
  }

  el.bulkImportModal.style.display = "flex";
}

function closeBulkImportModal() {
  if (!el.bulkImportModal) return;
  el.bulkImportModal.style.display = "none";
}

if (el.btnBulkImportClose) el.btnBulkImportClose.addEventListener("click", closeBulkImportModal);
if (el.btnBulkImportCancel) el.btnBulkImportCancel.addEventListener("click", closeBulkImportModal);
if (el.bulkImportModal) {
  el.bulkImportModal.addEventListener("click", (e) => {
    if (e.target === el.bulkImportModal) closeBulkImportModal();
  });
}

if (el.bulkImportFiles) {
  el.bulkImportFiles.addEventListener("change", () => {
    const count = el.bulkImportFiles.files ? el.bulkImportFiles.files.length : 0;
    if (el.bulkImportFileCount) {
      el.bulkImportFileCount.textContent = count === 1 ? "1 file selected" : `${count} files selected`;
    }
    if (el.btnBulkImportSubmit) {
      el.btnBulkImportSubmit.disabled = count === 0;
    }
  });
}

if (el.btnBulkImportSubmit) {
  el.btnBulkImportSubmit.addEventListener("click", async () => {
    const files = el.bulkImportFiles.files;
    if (!files || files.length === 0) return;

    el.btnBulkImportSubmit.disabled = true;
    if (el.bulkImportStatus) {
      el.bulkImportStatus.style.display = "block";
      el.bulkImportStatus.style.color = "var(--text-primary)";
      el.bulkImportStatus.textContent = `Importing ${files.length} file(s)... This may take a moment for conversions.`;
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }
    formData.append("device", el.bulkImportDevice ? el.bulkImportDevice.value : "none");
    formData.append("parent_id", el.bulkImportFolder ? el.bulkImportFolder.value : "");

    try {
      const res = await fetch("/api/documents/bulk-import", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        if (el.bulkImportStatus) {
          el.bulkImportStatus.style.color = "var(--accent)";
          el.bulkImportStatus.textContent = `✓ Successfully imported ${data.imported_count} file(s)!`;
        }
        await fetchDocuments();
        setTimeout(() => {
          closeBulkImportModal();
        }, 1200);
      } else {
        const errMsg = data.detail || (data.errors && data.errors[0]?.error) || "Import failed";
        if (el.bulkImportStatus) {
          el.bulkImportStatus.style.color = "var(--danger)";
          el.bulkImportStatus.textContent = `Error: ${errMsg}`;
        }
        el.btnBulkImportSubmit.disabled = false;
      }
    } catch (err) {
      if (el.bulkImportStatus) {
        el.bulkImportStatus.style.color = "var(--danger)";
        el.bulkImportStatus.textContent = `Network error: ${err.message}`;
      }
      el.btnBulkImportSubmit.disabled = false;
    }
  });
}

// --- Command Palette Controller (Cmd+K / Ctrl+K) ---
const APP_COMMANDS = [
  {
    id: "new-note",
    icon: "📝",
    title: "New Notebook",
    desc: "Create a blank note or import Markdown",
    action: () => { if (el.btnNewNotebook) el.btnNewNotebook.click(); },
  },
  {
    id: "new-folder",
    icon: "📁",
    title: "New Folder",
    desc: "Create a new folder in current location",
    action: () => { if (el.btnNewFolder) el.btnNewFolder.click(); },
  },
  {
    id: "bulk-import",
    icon: "📥",
    title: "Bulk Import Files",
    desc: "Upload multiple PDF, EPUB, or Markdown files",
    action: () => openBulkImportModal(),
  },
  {
    id: "quick-capture",
    icon: "⚡",
    title: "Quick Capture",
    desc: "Instantly capture an action item or note",
    action: () => { if (el.btnQuickCapture) el.btnQuickCapture.click(); },
  },
  {
    id: "sync-now",
    icon: "🔄",
    title: "Sync with Cloud",
    desc: "Trigger live background synchronization",
    action: () => { if (el.btnSyncNow) el.btnSyncNow.click(); },
  },
  {
    id: "open-tasks",
    icon: "📋",
    title: "Open Tasks",
    desc: "View consolidated action items across notebooks",
    action: () => { if (el.btnTasksToggle) el.btnTasksToggle.click(); },
  },
  {
    id: "settings",
    icon: "⚙️",
    title: "Settings & AI OCR",
    desc: "Configure Vision providers and MCP integrations",
    action: () => { if (el.btnSettingsToggle) el.btnSettingsToggle.click(); },
  },
  {
    id: "toggle-theme",
    icon: "🌓",
    title: "Toggle Theme (Dark / Light / Auto)",
    desc: "Switch between dark, light, or auto system theme",
    action: () => { if (el.btnThemeToggle) el.btnThemeToggle.click(); },
  },
  {
    id: "optimize-pro",
    icon: "⚡",
    title: "Optimize for Paper Pro",
    desc: "Convert a comic or heavy document for Paper Pro",
    action: () => { if (el.btnOpenConverter) el.btnOpenConverter.click(); },
  },
  {
    id: "view-grid",
    icon: "⊞",
    title: "Grid View",
    desc: "Switch library display to grid view",
    action: () => setViewMode("grid"),
  },
  {
    id: "view-list",
    icon: "☰",
    title: "List View",
    desc: "Switch library display to compact list view",
    action: () => setViewMode("list"),
  },
];

let commandPaletteItems = [];
let commandPaletteSelectedIndex = 0;

function openCommandPalette() {
  if (!el.commandPaletteModal) return;
  el.commandPaletteModal.style.display = "flex";
  if (el.commandPaletteInput) {
    el.commandPaletteInput.value = "";
    el.commandPaletteInput.focus();
  }
  renderCommandPaletteResults("");
}

function closeCommandPalette() {
  if (!el.commandPaletteModal) return;
  el.commandPaletteModal.style.display = "none";
}

function renderCommandPaletteResults(query) {
  if (!el.commandPaletteResults) return;
  const q = (query || "").trim().toLowerCase();

  const matchedCommands = APP_COMMANDS.filter((cmd) =>
    !q || cmd.title.toLowerCase().includes(q) || cmd.desc.toLowerCase().includes(q)
  );

  const allDocs = state.allDocs || [];
  const matchedDocs = q ? allDocs.filter((d) =>
    (d.visible_name || "").toLowerCase().includes(q)
  ).slice(0, 15) : allDocs.slice(0, 8);

  commandPaletteItems = [];
  let html = "";

  if (matchedCommands.length > 0) {
    html += `<div class="command-section-title">Commands & Actions</div>`;
    matchedCommands.forEach((cmd) => {
      const idx = commandPaletteItems.length;
      commandPaletteItems.push({ type: "command", data: cmd });
      html += `
        <div class="command-item ${idx === 0 ? 'selected' : ''}" data-idx="${idx}">
          <div class="command-item-left">
            <span style="font-size: 1.1rem;">${cmd.icon}</span>
            <div style="display: flex; flex-direction: column;">
              <span class="command-item-title">${escapeHtml(cmd.title)}</span>
              <span class="command-item-desc">${escapeHtml(cmd.desc)}</span>
            </div>
          </div>
          <span style="font-size: 0.75rem; color: var(--text-muted);">Action</span>
        </div>
      `;
    });
  }

  if (matchedDocs.length > 0) {
    html += `<div class="command-section-title">Documents & Notebooks</div>`;
    matchedDocs.forEach((doc) => {
      const idx = commandPaletteItems.length;
      commandPaletteItems.push({ type: "doc", data: doc });
      const isFolder = doc.type === "CollectionType";
      const icon = isFolder ? "📁" : (doc.file_type === "pdf" ? "📄" : (doc.file_type === "epub" ? "📚" : "📓"));
      const meta = isFolder ? "Folder" : `${doc.page_count || 1} pages`;
      html += `
        <div class="command-item ${idx === 0 && matchedCommands.length === 0 ? 'selected' : ''}" data-idx="${idx}">
          <div class="command-item-left">
            <span style="font-size: 1.1rem;">${icon}</span>
            <div style="display: flex; flex-direction: column;">
              <span class="command-item-title">${escapeHtml(doc.visible_name)}</span>
              <span class="command-item-desc">${meta}</span>
            </div>
          </div>
          <span style="font-size: 0.75rem; color: var(--text-muted);">${isFolder ? 'Open Folder' : 'Open Reader'}</span>
        </div>
      `;
    });
  }

  if (commandPaletteItems.length === 0) {
    html = `<div style="padding: 2rem 1rem; text-align: center; color: var(--text-muted); font-size: 0.88rem;">No matching commands or files found</div>`;
  }

  el.commandPaletteResults.innerHTML = html;
  commandPaletteSelectedIndex = 0;

  el.commandPaletteResults.querySelectorAll(".command-item").forEach((itemEl) => {
    itemEl.addEventListener("click", () => {
      const idx = parseInt(itemEl.getAttribute("data-idx"), 10);
      executeCommandPaletteItem(idx);
    });
  });
}

function updateCommandPaletteHighlight() {
  if (!el.commandPaletteResults) return;
  const items = el.commandPaletteResults.querySelectorAll(".command-item");
  items.forEach((itemEl, idx) => {
    itemEl.classList.toggle("selected", idx === commandPaletteSelectedIndex);
    if (idx === commandPaletteSelectedIndex) {
      itemEl.scrollIntoView({ block: "nearest" });
    }
  });
}

function executeCommandPaletteItem(idx) {
  const item = commandPaletteItems[idx];
  if (!item) return;
  closeCommandPalette();
  if (item.type === "command") {
    item.data.action();
  } else if (item.type === "doc") {
    const doc = item.data;
    if (doc.type === "CollectionType") {
      state.folderPath.push({ id: doc.id, name: doc.visible_name });
      navigateToFolder(doc.id);
    } else {
      openReader(doc.id);
    }
  }
}

// Global keyboard shortcut
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (el.commandPaletteModal && el.commandPaletteModal.style.display === "flex") {
      closeCommandPalette();
    } else {
      openCommandPalette();
    }
    return;
  }

  if (el.commandPaletteModal && el.commandPaletteModal.style.display === "flex") {
    if (e.key === "Escape") {
      e.preventDefault();
      closeCommandPalette();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (commandPaletteItems.length > 0) {
        commandPaletteSelectedIndex = (commandPaletteSelectedIndex + 1) % commandPaletteItems.length;
        updateCommandPaletteHighlight();
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (commandPaletteItems.length > 0) {
        commandPaletteSelectedIndex = (commandPaletteSelectedIndex - 1 + commandPaletteItems.length) % commandPaletteItems.length;
        updateCommandPaletteHighlight();
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      executeCommandPaletteItem(commandPaletteSelectedIndex);
    }
  }
});

if (el.commandPaletteInput) {
  el.commandPaletteInput.addEventListener("input", (e) => {
    renderCommandPaletteResults(e.target.value);
  });
}

if (el.commandPaletteModal) {
  el.commandPaletteModal.addEventListener("click", (e) => {
    if (e.target === el.commandPaletteModal) closeCommandPalette();
  });
}

// --- MCP Copy Buttons ---
if (el.btnCopyMcpConfig) {
  el.btnCopyMcpConfig.addEventListener("click", () => {
    const snippet = document.getElementById("mcp-config-snippet").innerText;
    navigator.clipboard.writeText(snippet).then(() => {
      el.btnCopyMcpConfig.textContent = "✓ Copied!";
      setTimeout(() => { el.btnCopyMcpConfig.textContent = "📋 Copy Config"; }, 1500);
    });
  });
}

if (el.btnCopyMcpUrl) {
  el.btnCopyMcpUrl.addEventListener("click", () => {
    const url = document.getElementById("mcp-http-url").innerText;
    navigator.clipboard.writeText(url).then(() => {
      el.btnCopyMcpUrl.textContent = "✓ Copied!";
      setTimeout(() => { el.btnCopyMcpUrl.textContent = "📋 Copy URL"; }, 1500);
    });
  });
}

// --- Initialization ---
setViewMode(state.viewMode);
fetchStatus();
fetchTasks();
fetchDocuments();

// Check for deep-link / read in new tab parameter
try {
  const urlParams = new URLSearchParams(window.location.search);
  const readDocId = urlParams.get("read") || urlParams.get("doc");
  if (readDocId) {
    const pageIdx = parseInt(urlParams.get("page") || "0", 10);
    openReader(readDocId, isNaN(pageIdx) ? 0 : pageIdx);
  }
} catch (e) {
  console.error("Deep-link read error", e);
}
