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
  currentView: "library",
  draggedDoc: null,
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
    desc: "1:1 native reMarkable pixel match. Optimal balance of razor-sharp art and smooth e-ink caching.",
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

// Crisp monochrome vector icons
const ICONS = {
  notebook: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>`,
  pdf: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="9" y1="15" x2="15" y2="15"></line></svg>`,
  epub: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>`,
  folder: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>`,
  open: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>`,
  readTab: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>`,
  move: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path><polyline points="12 11 12 17"></polyline><polyline points="9 14 15 14"></polyline></svg>`,
  optimize: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><circle cx="12" cy="18" r="1"></circle></svg>`,
  exclude: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>`,
  check: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
  download: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`,
  copy: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`,
  delete: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`,
  quickCapture: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>`,
  sync: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"></path><path d="M16 21h5v-5"></path></svg>`,
  tasks: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>`,
  settings: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>`,
  theme: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"></path></svg>`,
  grid: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>`,
  list: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>`,
};

// --- Sleek Scandinavian Toast Notification System ---
function showToast(message, type = "info", duration = 3500) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    container.setAttribute("aria-live", "polite");
    container.setAttribute("aria-atomic", "true");
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  const iconMap = {
    success: `<svg class="toast-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
    error: `<svg class="toast-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`,
    warning: `<svg class="toast-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`,
    info: `<svg class="toast-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`,
  };

  const iconHtml = iconMap[type] || iconMap.info;

  toast.innerHTML = `
    <span class="toast-icon">${iconHtml}</span>
    <span class="toast-message">${escapeHtml(String(message))}</span>
    <button class="toast-close" aria-label="Dismiss">✕</button>
  `;

  let dismissTimeout = null;

  function dismiss() {
    if (dismissTimeout) clearTimeout(dismissTimeout);
    toast.classList.add("toast-exiting");
    toast.addEventListener("animationend", () => {
      toast.remove();
    }, { once: true });
  }

  toast.querySelector(".toast-close").addEventListener("click", (e) => {
    e.stopPropagation();
    dismiss();
  });

  toast.addEventListener("mouseenter", () => {
    if (dismissTimeout) clearTimeout(dismissTimeout);
  });

  toast.addEventListener("mouseleave", () => {
    dismissTimeout = setTimeout(dismiss, 1500);
  });

  container.appendChild(toast);
  dismissTimeout = setTimeout(dismiss, duration);
}

// Seamlessly route standard alerts to sleek toasts
window.alert = (msg) => showToast(String(msg), "info");

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
  menuQuickCapture: document.getElementById("menu-quick-capture"),
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
  btnCopyMcpLocal: document.getElementById("btn-copy-mcp-local"),
  btnCopyMcpSse: document.getElementById("btn-copy-mcp-sse"),
  btnCopyMcpSsh: document.getElementById("btn-copy-mcp-ssh"),
  btnCopyMcpProxy: document.getElementById("btn-copy-mcp-proxy"),
  btnSettingsRescanLibrary: document.getElementById("btn-settings-rescan-library"),
  settingsRescanStatus: document.getElementById("settings-rescan-status"),

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
  folderOptionsContainer: document.getElementById("folder-options-container"),
  btnFolderOptions: document.getElementById("btn-folder-options"),
  folderOptionsMenu: document.getElementById("folder-options-menu"),
  menuFolderExclude: document.getElementById("menu-folder-exclude"),
  menuFolderNewSubfolder: document.getElementById("menu-folder-new-subfolder"),
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
  readerPageDisplay: document.getElementById("reader-page-display"),
  readerPageCurrent: document.getElementById("reader-page-current"),
  readerPageTotal: document.getElementById("reader-page-total"),
  readerPageJumpForm: document.getElementById("reader-page-jump-form"),
  readerPageInput: document.getElementById("reader-page-input"),
  readerPageTotalEdit: document.getElementById("reader-page-total-edit"),
  readerPageSpinner: document.getElementById("reader-page-spinner"),
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
  btnReaderMoreDesktop: document.getElementById("btn-reader-more-desktop"),
  readerMoreMenuDesktop: document.getElementById("reader-more-menu-desktop"),
  btnReaderOpenTab: document.getElementById("btn-reader-open-tab"),
  readerCanvasWrapper: document.getElementById("reader-canvas-wrapper"),
  readerContent: document.getElementById("reader-content"),
  readerClickZones: document.getElementById("reader-click-zones"),
  zonePrev: document.getElementById("zone-prev"),
  zoneCenter: document.getElementById("zone-center"),
  zoneNext: document.getElementById("zone-next"),

  // Converter elements
  converterModal: document.getElementById("converter-modal"),
  converterDevice: document.getElementById("converter-device"),
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
  libraryView: document.getElementById("library-view"),
  settingsView: document.getElementById("settings-view"),
  btnSettingsToggle: document.getElementById("btn-settings-toggle"),
  btnSettingsBack: document.getElementById("btn-settings-back"),
  settingsModal: document.getElementById("settings-view"),
  btnSettingsClose: document.getElementById("btn-settings-back"),
  settingsProvider: document.getElementById("settings-provider"),
  settingsModel: document.getElementById("settings-model"),
  settingsApiKey: document.getElementById("settings-api-key"),
  btnToggleKeyVisibility: document.getElementById("btn-toggle-key-visibility"),
  settingsBaseUrlGroup: document.getElementById("settings-base-url-group"),
  settingsBaseUrl: document.getElementById("settings-base-url"),
  settingsKeyStatus: document.getElementById("settings-key-status"),
  settingsTestResult: document.getElementById("settings-test-result"),
  btnSettingsTest: document.getElementById("btn-settings-test"),
  btnSettingsSave: document.getElementById("btn-settings-save"),
  mcpHttpUrl: document.getElementById("mcp-http-url"),
  btnSettingsSyncTrigger: document.getElementById("btn-settings-sync-trigger"),
  btnSettingsSyncDrawerToggle: document.getElementById("btn-settings-sync-drawer-toggle"),
  btnSettingsLogout: document.getElementById("btn-settings-logout"),
  btnSettingsScanTasks: document.getElementById("btn-settings-scan-tasks"),
  settingsCloudStatusTitle: document.getElementById("settings-cloud-status-title"),
  settingsCloudStatusDesc: document.getElementById("settings-cloud-status-desc"),
  statTotalDocs: document.getElementById("stat-total-docs"),
  statNotebooks: document.getElementById("stat-notebooks"),
  statPdfs: document.getElementById("stat-pdfs"),
  statTasks: document.getElementById("stat-tasks"),

  // Delivery (News & Puzzles) elements
  deliveryNewspaperEnabled: document.getElementById("delivery-newspaper-enabled"),
  deliveryNewspaperTime: document.getElementById("delivery-newspaper-time"),
  deliveryNewspaperFolder: document.getElementById("delivery-newspaper-folder"),
  deliveryIncludeWeather: document.getElementById("delivery-include-weather"),
  deliveryWeatherLocation: document.getElementById("delivery-weather-location"),
  deliveryIncludeWikipedia: document.getElementById("delivery-include-wikipedia"),
  deliveryRssFeeds: document.getElementById("delivery-rss-feeds"),
  btnDeliveryNewspaperNow: document.getElementById("btn-delivery-newspaper-now"),
  deliveryNewspaperStatus: document.getElementById("delivery-newspaper-status"),
  deliveryPuzzlesEnabled: document.getElementById("delivery-puzzles-enabled"),
  deliveryPuzzlesTime: document.getElementById("delivery-puzzles-time"),
  deliveryPuzzlesFolder: document.getElementById("delivery-puzzles-folder"),
  deliveryIncludeQuick: document.getElementById("delivery-include-quick"),
  deliveryIncludeCryptic: document.getElementById("delivery-include-cryptic"),
  deliveryIncludeSudoku: document.getElementById("delivery-include-sudoku"),
  deliverySudokuDifficulty: document.getElementById("delivery-sudoku-difficulty"),
  btnDeliveryPuzzlesNow: document.getElementById("btn-delivery-puzzles-now"),
  deliveryPuzzlesStatus: document.getElementById("delivery-puzzles-status"),
  btnDeliverySave: document.getElementById("btn-delivery-save"),
  deliverySaveStatus: document.getElementById("delivery-save-status"),

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

  const isDark = effectiveTheme === "dark";
  document.querySelectorAll(".doc-card-thumb img[data-doc-id]").forEach((img) => {
    const docId = img.getAttribute("data-doc-id");
    const docHash = img.getAttribute("data-doc-hash") || "";
    img.src = `/api/documents/${docId}/thumbnail?h=${encodeURIComponent(docHash)}&dark=${isDark}&v=4`;
  });

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
  const isDesktop = !window.matchMedia("(pointer: coarse)").matches && window.innerWidth > 768;

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

    // Desktop Drag and drop target for parent/ancestor breadcrumbs
    if (isDesktop && index < state.folderPath.length - 1) {
      a.setAttribute("title", `Drop items here to move into "${item.name}"`);
      a.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = "move";
        a.classList.add("breadcrumb-drop-target");
      });
      a.addEventListener("dragleave", (e) => {
        if (!a.contains(e.relatedTarget)) {
          a.classList.remove("breadcrumb-drop-target");
        }
      });
      a.addEventListener("drop", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        a.classList.remove("breadcrumb-drop-target");
        if (state.draggedDoc && state.draggedDoc.id !== item.id) {
          await moveItemToFolder(state.draggedDoc.id, state.draggedDoc.name, item.id, item.name);
        } else if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          await uploadExternalFiles(e.dataTransfer.files, item.id, item.name);
        }
      });
    }

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
  if (state.currentView === "settings") {
    navigateToView("library", true);
  }
  closeReader();
  navigateToFolder("", 0);
});

// --- Folder Options & Exclusion Controller ---
async function updateFolderExclusionButton() {
  if (!state.currentFolder) {
    if (el.folderOptionsContainer) el.folderOptionsContainer.style.display = "none";
    if (el.btnFolderExclude) el.btnFolderExclude.style.display = "none";
    return;
  }

  if (el.folderOptionsContainer) el.folderOptionsContainer.style.display = "inline-block";

  try {
    const res = await fetch(`/api/documents/${state.currentFolder}`);
    if (!res.ok) return;
    const folder = await res.json();
    const isExcluded = folder.exclude_from_search || folder.effective_exclude;

    if (el.menuFolderExclude) {
      el.menuFolderExclude.innerHTML = `
        ${isExcluded ? ICONS.check : ICONS.exclude}
        <span>${isExcluded ? "Include Folder in Search & Tasks" : "Exclude Folder from Search & Tasks"}</span>
      `;
    }
  } catch (e) {
    console.debug("Failed to check folder state", e);
  }
}

if (el.btnFolderOptions) {
  el.btnFolderOptions.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = el.folderOptionsMenu.style.display === "flex" || el.folderOptionsMenu.style.display === "block";
    el.folderOptionsMenu.style.display = isOpen ? "none" : "flex";
  });
}

if (el.menuFolderExclude) {
  el.menuFolderExclude.addEventListener("click", async () => {
    if (!state.currentFolder) return;
    if (el.folderOptionsMenu) el.folderOptionsMenu.style.display = "none";
    try {
      await fetch(`/api/documents/${state.currentFolder}/indexing-toggle`, { method: "POST" });
      await updateFolderExclusionButton();
      await fetchDocuments();
    } catch (e) {
      console.error("Failed to toggle folder exclusion", e);
    }
  });
}

if (el.menuFolderNewSubfolder) {
  el.menuFolderNewSubfolder.addEventListener("click", () => {
    if (el.folderOptionsMenu) el.folderOptionsMenu.style.display = "none";
    if (el.btnNewFolder) el.btnNewFolder.click();
  });
}

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

      // Always keep the Tasks notebook pinned to the top of notebooks on the main page
      if (state.currentFolderId === "") {
        const isTasksA = (a.visible_name || "").trim().toLowerCase() === "tasks";
        const isTasksB = (b.visible_name || "").trim().toLowerCase() === "tasks";
        if (isTasksA !== isTasksB) {
          return isTasksA ? -1 : 1;
        }
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
    const weightSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 7a3 3 0 0 1 6 0"></path><path d="M6 10h12l1.5 10a2 2 0 0 1-2 2H6.5a2 2 0 0 1-2-2L6 10z"></path><line x1="12" y1="13" x2="12" y2="16"></line><circle cx="12" cy="18.5" r="0.75" fill="currentColor"></circle></svg>`;
    const optimizeBadge = doc.needs_optimization ? `<span class="doc-badge doc-badge-optimize" title="Heavy file (>30MB or >150 pages). Optimize for reMarkable.">${weightSvg}</span>` : "";

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
            ${isFolder ? ICONS.folder : ICONS.open}
            <span>${isFolder ? 'Open Folder' : 'Open & Read'}</span>
          </button>
          ${!isFolder ? `<a href="/?read=${doc.id}" target="_blank" rel="noopener" class="menu-item menu-item-read-tab" style="text-decoration: none; color: inherit;">${ICONS.readTab}<span>Read in New Tab</span></a>` : ""}
          <button class="menu-item menu-item-move">${ICONS.folder}<span>Add to Folder...</span></button>
          ${!isFolder ? `<button class="menu-item menu-item-optimize">${ICONS.optimize}<span>Optimize for reMarkable</span></button>` : ""}
          <button class="menu-item menu-item-exclude">
            ${isExcluded ? ICONS.check : ICONS.exclude}
            <span>${isExcluded ? 'Include in Search & Tasks' : 'Exclude from Search & Tasks'}</span>
          </button>
          ${isFolder ? `<a href="/api/documents/${doc.id}/export/zip" download class="menu-item menu-item-export" style="text-decoration: none; color: inherit;">${ICONS.download}<span>Download Folder (ZIP)</span></a>` : `<a href="/api/documents/${doc.id}/export/pdf?dark=${state.appTheme === 'dark'}" download class="menu-item menu-item-export" style="text-decoration: none; color: inherit;">${ICONS.download}<span>Download PDF</span></a>`}
          <button class="menu-item menu-item-copy-id">${ICONS.copy}<span>Copy ID</span></button>
          <button class="menu-item menu-item-delete" style="color: var(--danger);">${ICONS.delete}<span>Delete</span></button>
        </div>
      </div>
    `;

    if (state.viewMode === "list") {
      element.className = isFolder ? "doc-list-item doc-list-folder" : "doc-list-item";
      let listIcon = "";
      if (isFolder) {
        listIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>`;
      } else if (doc.file_type === "pdf") {
        listIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="9" y1="15" x2="15" y2="15"></line></svg>`;
      } else if (doc.file_type === "epub") {
        listIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>`;
      } else {
        listIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path><line x1="8" y1="7" x2="16" y2="7"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>`;
      }

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
      element.className = isFolder ? "doc-card doc-card-folder" : "doc-card";
      let iconHtml = "";
      if (isFolder) {
        iconHtml = `
          <svg class="folder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
        `;
      } else {
        const isDark = state.appTheme === "dark";
        const thumbUrl = `/api/documents/${doc.id}/thumbnail?h=${encodeURIComponent(doc.doc_hash || "")}&dark=${isDark}&v=4`;
        iconHtml = `<img src="${thumbUrl}" data-doc-id="${escapeHtml(doc.id)}" data-doc-hash="${escapeHtml(doc.doc_hash || "")}" alt="${escapeHtml(doc.visible_name)} preview" loading="lazy" width="320" height="426">`;
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

    // Desktop Drag & Drop file and folder management (strictly ignored on mobile/touch)
    const isDesktop = !window.matchMedia("(pointer: coarse)").matches && window.innerWidth > 768;
    if (isDesktop) {
      element.setAttribute("draggable", "true");

      element.addEventListener("dragstart", (e) => {
        if (e.target.closest(".card-menu-wrapper") || e.target.closest(".btn-card-menu")) {
          e.preventDefault();
          return;
        }
        state.draggedDoc = {
          id: doc.id,
          name: doc.visible_name,
          type: doc.type,
          parent_id: doc.parent_id || state.currentFolder || ""
        };
        element.classList.add("is-dragging");
        e.dataTransfer.setData("application/x-rmcompanion-doc", doc.id);
        e.dataTransfer.setData("text/plain", doc.visible_name);
        e.dataTransfer.effectAllowed = "move";
      });

      element.addEventListener("dragend", () => {
        element.classList.remove("is-dragging");
        state.draggedDoc = null;
        document.querySelectorAll(".drag-over").forEach((d) => d.classList.remove("drag-over"));
        document.querySelectorAll(".breadcrumb-drop-target").forEach((b) => b.classList.remove("breadcrumb-drop-target"));
        if (el.docGrid) el.docGrid.classList.remove("grid-drop-active");
      });

      if (isFolder) {
        element.addEventListener("dragover", (e) => {
          e.preventDefault();
          e.stopPropagation();
          if (state.draggedDoc && state.draggedDoc.id === doc.id) {
            e.dataTransfer.dropEffect = "none";
            return;
          }
          e.dataTransfer.dropEffect = state.draggedDoc ? "move" : "copy";
          element.classList.add("drag-over");
        });

        element.addEventListener("dragleave", (e) => {
          if (!element.contains(e.relatedTarget)) {
            element.classList.remove("drag-over");
          }
        });

        element.addEventListener("drop", async (e) => {
          e.preventDefault();
          e.stopPropagation();
          element.classList.remove("drag-over");

          if (state.draggedDoc) {
            if (state.draggedDoc.id === doc.id) return;
            await moveItemToFolder(state.draggedDoc.id, state.draggedDoc.name, doc.id, doc.visible_name);
          } else if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            await uploadExternalFiles(e.dataTransfer.files, doc.id, doc.visible_name);
          }
        });
      }
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
        document.querySelectorAll(".doc-card, .doc-list-item").forEach((c) => c.classList.remove("is-menu-open"));
        if (!isOpen) {
          menuDropdown.style.display = "block";
          element.classList.add("is-menu-open");
        }
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
          mCopy.innerHTML = `${ICONS.check}<span>Copied!</span>`;
          setTimeout(() => {
            mCopy.innerHTML = `${ICONS.copy}<span>Copy ID</span>`;
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
    document.querySelectorAll(".doc-card, .doc-list-item").forEach((c) => c.classList.remove("is-menu-open"));
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
    el.trayDocIcon.innerHTML = ICONS.folder;
  } else if (doc.file_type === "pdf") {
    el.trayDocIcon.innerHTML = ICONS.pdf;
  } else if (doc.file_type === "epub") {
    el.trayDocIcon.innerHTML = ICONS.epub;
  } else {
    el.trayDocIcon.innerHTML = ICONS.notebook;
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
      el.trayIconExclude.innerHTML = ICONS.check;
      el.trayLabelExclude.textContent = "Include in Search & Tasks";
      el.trayDescExclude.textContent = "Include in search and task aggregation";
    } else {
      el.trayIconExclude.innerHTML = ICONS.exclude;
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

    const icon = item.id === "" ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>` : ICONS.folder;
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
        showToast(err.detail || "Failed to move item", "error");
        return;
      }
      closeMoveFolderModal();
      showToast("Item moved successfully", "success");
      await fetchDocuments();
    } catch (err) {
      console.error("Failed to move item", err);
      showToast("Error moving item", "error");
    } finally {
      if (el.btnMoveFolderSubmit) el.btnMoveFolderSubmit.disabled = false;
    }
  });
}

// --- Desktop Drag & Drop Handlers ---
async function moveItemToFolder(docId, docTitle, targetFolderId, targetFolderName) {
  if (!docId || docId === targetFolderId) return;
  showToast(`Moving "${docTitle}" to "${targetFolderName}"...`, "info");
  try {
    const res = await fetch(`/api/documents/${docId}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parent_id: targetFolderId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || "Failed to move item", "error");
      return;
    }
    showToast(`Moved "${docTitle}" to "${targetFolderName}"`, "success");
    await fetchDocuments();
  } catch (err) {
    console.error("Failed to move item", err);
    showToast("Error moving item", "error");
  }
}

async function uploadExternalFiles(fileList, targetFolderId, targetFolderName) {
  if (!fileList || fileList.length === 0) return;
  const files = Array.from(fileList);

  const allowedExts = [".pdf", ".epub", ".cbz", ".md", ".markdown", ".txt"];
  const validFiles = files.filter((f) => {
    const lower = f.name.toLowerCase();
    return allowedExts.some((ext) => lower.endsWith(ext));
  });

  if (validFiles.length === 0) {
    showToast("Unsupported file type. Drop PDF, EPUB, CBZ, Markdown or TXT files.", "error");
    return;
  }

  showToast(`Importing ${validFiles.length} file(s) into "${targetFolderName}"...`, "info");

  const formData = new FormData();
  validFiles.forEach((f) => formData.append("files", f));
  formData.append("parent_id", targetFolderId || "");
  formData.append("device", "none");
  formData.append("quality_stop", "3");

  try {
    const res = await fetch("/api/documents/bulk-import", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || "Bulk import failed", "error");
      return;
    }
    const data = await res.json();
    const importedCount = data.imported ? data.imported.length : 0;
    const errorCount = data.errors ? data.errors.length : 0;

    if (errorCount > 0) {
      showToast(`Imported ${importedCount} file(s) with ${errorCount} warning(s)`, "warning");
    } else {
      showToast(`Successfully imported ${importedCount} file(s) into "${targetFolderName}"`, "success");
    }
    await fetchDocuments();
  } catch (err) {
    console.error("Failed to import dropped files", err);
    showToast("Failed to import dropped files", "error");
  }
}

// Attach drop listener to the library grid for external files
if (el.docGrid) {
  el.docGrid.addEventListener("dragover", (e) => {
    const isDesktop = !window.matchMedia("(pointer: coarse)").matches && window.innerWidth > 768;
    if (!isDesktop) return;
    if (!state.draggedDoc && e.dataTransfer.types && (e.dataTransfer.types.includes("Files") || e.dataTransfer.types.includes("application/x-moz-file"))) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      el.docGrid.classList.add("grid-drop-active");
    }
  });

  el.docGrid.addEventListener("dragleave", (e) => {
    if (!el.docGrid.contains(e.relatedTarget)) {
      el.docGrid.classList.remove("grid-drop-active");
    }
  });

  el.docGrid.addEventListener("drop", async (e) => {
    const isDesktop = !window.matchMedia("(pointer: coarse)").matches && window.innerWidth > 768;
    if (!isDesktop) return;
    el.docGrid.classList.remove("grid-drop-active");
    if (!state.draggedDoc && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      e.preventDefault();
      e.stopPropagation();
      const currentFolderName = state.folderPath.length > 0 ? state.folderPath[state.folderPath.length - 1].name : "Home";
      await uploadExternalFiles(e.dataTransfer.files, state.currentFolder || "", currentFolderName);
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
        showToast(err.detail || "Failed to create folder", "error");
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
        showToast(err.detail || "Failed to create folder", "error");
        return;
      }
      closeNewFolderModal();
      showToast(`Folder "${name}" created`, "success");
      await fetchDocuments();
    } catch (err) {
      console.error("Failed to create folder", err);
      showToast("Error creating folder", "error");
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
      showToast(err.detail || "Failed to delete item", "error");
      return;
    }
    showToast(isFolder ? `Folder "${doc.visible_name}" deleted` : `"${doc.visible_name}" deleted`, "success");
    await fetchDocuments();
  } catch (err) {
    console.error("Failed to delete item", err);
    showToast("Error deleting item", "error");
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
    el.trayReaderExcludeLabel.textContent = isExcluded ? "Include in Search" : "Exclude from Search";
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

// --- Reader View & Page Preloading ---
const pageSvgCache = new Map();
let preloadTimer = null;

function preloadAdjacentPages(docId, currentPageIdx, totalPages, darkMode) {
  if (!docId || totalPages <= 1) return;
  if (preloadTimer) clearTimeout(preloadTimer);

  preloadTimer = setTimeout(async () => {
    // Sequentially preload next page (+1), then previous (-1) without flooding network/CPU
    const targets = [currentPageIdx + 1, currentPageIdx - 1];
    for (const pIdx of targets) {
      if (pIdx >= 0 && pIdx < totalPages) {
        const key = `${docId}_${pIdx}_${darkMode}`;
        if (!pageSvgCache.has(key)) {
          try {
            const res = await fetch(`/api/documents/${docId}/pages/${pIdx}/svg?dark=${darkMode}&v=4`);
            if (res.ok) {
              const svg = await res.text();
              pageSvgCache.set(key, svg);
            }
          } catch (_) {}
        }
      }
    }
  }, 160);
}

function renderSvgContent(svgText) {
  el.readerCanvasWrapper.innerHTML = svgText;
  const svgEl = el.readerCanvasWrapper.querySelector("svg");
  if (svgEl) {
    svgEl.classList.add("reader-canvas");
  }
}

async function openReader(docId, initialPageIdx = null) {
  try {
    const res = await fetch(`/api/documents/${docId}`);
    if (!res.ok) return;
    const doc = await res.json();

    state.currentDoc = doc;
    // Determine effective starting page: resume at doc.last_opened_page if not explicitly specified
    let startingPage = 0;
    if (initialPageIdx !== null && initialPageIdx !== undefined && !isNaN(initialPageIdx)) {
      startingPage = initialPageIdx;
    } else if (doc.last_opened_page !== undefined && doc.last_opened_page !== null && !isNaN(doc.last_opened_page)) {
      startingPage = doc.last_opened_page;
    }
    const maxPage = (doc.pages && doc.pages.length > 0) ? doc.pages.length - 1 : (doc.page_count ? doc.page_count - 1 : 0);
    startingPage = Math.max(0, Math.min(startingPage, maxPage));

    state.currentPageIdx = startingPage;
    state.currentDoc._savedPageIdx = startingPage;
    el.readerTitle.textContent = doc.visible_name;

    updateReaderExclusionState();
    if (el.btnReaderOpenTab) {
      el.btnReaderOpenTab.href = `/?read=${docId}&page=${startingPage}`;
    }
    el.readerView.style.display = "flex";
    updatePageDarkToggle();
    loadCurrentPage();

    try {
      const url = new URL(window.location.href);
      url.searchParams.set("read", docId);
      if (startingPage > 0) url.searchParams.set("page", startingPage);
      else url.searchParams.delete("page");
      window.history.replaceState({ docId, pageIdx: startingPage }, "", url.toString());
    } catch (_) {}
  } catch (e) {
    console.error("Failed to open document", e);
  }
}

function saveDocumentPosition(docId, pageIdx) {
  if (!docId || pageIdx === undefined || pageIdx === null || isNaN(pageIdx)) return;
  if (state.currentDoc && state.currentDoc.id === docId && state.currentDoc._savedPageIdx === pageIdx) {
    return;
  }
  if (state.currentDoc && state.currentDoc.id === docId) {
    state.currentDoc._savedPageIdx = pageIdx;
  }
  const payload = JSON.stringify({ page_idx: pageIdx });
  try {
    fetch(`/api/documents/${docId}/position`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    }).catch((e) => console.debug("Failed saving document position:", e));
  } catch (e) {
    console.debug("Failed initiating position save:", e);
  }
}

function handlePageUnload() {
  if (state.currentDoc) {
    saveDocumentPosition(state.currentDoc.id, state.currentPageIdx || 0);
  }
}
window.addEventListener("pagehide", handlePageUnload);
window.addEventListener("beforeunload", handlePageUnload);

function updateReaderExclusionState() {
  if (!state.currentDoc) return;
  const isExcluded = state.currentDoc.exclude_from_search || state.currentDoc.effective_exclude;
  if (el.readerExcludeBadge) {
    el.readerExcludeBadge.style.display = "none";
  }
  if (el.btnReaderExcludeToggle) {
    el.btnReaderExcludeToggle.innerHTML = `
      ${isExcluded ? ICONS.check : ICONS.exclude}
      <span>${isExcluded ? "Include in Search & Tasks" : "Exclude from Search & Tasks"}</span>
    `;
  }
  if (el.trayReaderExcludeLabel) {
    el.trayReaderExcludeLabel.textContent = isExcluded ? "Include in Search & Tasks" : "Exclude from Search & Tasks";
  }
}

if (el.btnReaderMoreDesktop) {
  el.btnReaderMoreDesktop.addEventListener("click", (e) => {
    e.stopPropagation();
    if (el.readerMoreMenuDesktop) {
      const isOpen = el.readerMoreMenuDesktop.style.display === "flex" || el.readerMoreMenuDesktop.style.display === "block";
      el.readerMoreMenuDesktop.style.display = isOpen ? "none" : "flex";
    }
  });
}

el.btnReaderExcludeToggle.addEventListener("click", async () => {
  if (!state.currentDoc) return;
  if (el.readerMoreMenuDesktop) el.readerMoreMenuDesktop.style.display = "none";
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
  if (el.readerMoreMenuDesktop) el.readerMoreMenuDesktop.style.display = "none";
  openConverterModal(state.currentDoc.id, state.currentDoc.visible_name);
});

function closeReader() {
  if (state.currentDoc) {
    const docId = state.currentDoc.id;
    const pageIdx = state.currentPageIdx || 0;
    state.currentDoc.last_opened_page = pageIdx;
    if (Array.isArray(state.allDocs)) {
      const item = state.allDocs.find((d) => d.id === docId);
      if (item) item.last_opened_page = pageIdx;
    }
    saveDocumentPosition(docId, pageIdx);
  }
  closePageJumpInput(false);
  resetZoom(false);
  if (state.isFullscreen) {
    toggleFullscreenMode(false);
  }
  if (el.readerMoreMenuDesktop) el.readerMoreMenuDesktop.style.display = "none";
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
  resetZoom(false);
  if (el.readerContent) {
    el.readerContent.scrollTop = 0;
    el.readerContent.scrollLeft = 0;
  }
  const pages = (state.currentDoc.pages || []).filter((p) => !p.deleted);
  const totalPages = Math.max(pages.length, 1);
  const pageIdx = Math.min(state.currentPageIdx, totalPages - 1);
  state.currentPageIdx = pageIdx;

  if (el.readerPageCurrent && el.readerPageTotal) {
    el.readerPageCurrent.textContent = String(pageIdx + 1);
    el.readerPageTotal.textContent = String(totalPages);
    if (el.readerPageTotalEdit) el.readerPageTotalEdit.textContent = String(totalPages);
    if (el.readerPageInput && document.activeElement !== el.readerPageInput) {
      el.readerPageInput.value = String(pageIdx + 1);
      el.readerPageInput.max = String(totalPages);
    }
  } else if (el.readerPageIndicator) {
    el.readerPageIndicator.textContent = `Page ${pageIdx + 1} of ${totalPages}`;
  }
  el.btnPagePrev.disabled = pageIdx <= 0;
  el.btnPageNext.disabled = pageIdx >= totalPages - 1;

  if (state.isFullscreen) {
    flashPageIndicator();
  }

  if (el.btnReaderOpenTab) {
    el.btnReaderOpenTab.href = `/?read=${state.currentDoc.id}&page=${pageIdx}`;
  }

  try {
    const url = new URL(window.location.href);
    if (url.searchParams.get("read") === state.currentDoc.id) {
      if (pageIdx > 0) url.searchParams.set("page", pageIdx);
      else url.searchParams.delete("page");
      window.history.replaceState({ docId: state.currentDoc.id, pageIdx }, "", url.toString());
    }
  } catch (_) {}

  const cacheKey = `${state.currentDoc.id}_${pageIdx}_${state.pageDarkMode}`;
  if (pageSvgCache.has(cacheKey)) {
    if (el.readerPageSpinner) el.readerPageSpinner.style.display = "none";
    if (el.readerCanvasWrapper) el.readerCanvasWrapper.classList.remove("is-page-loading");
    renderSvgContent(pageSvgCache.get(cacheKey));
    preloadAdjacentPages(state.currentDoc.id, pageIdx, totalPages, state.pageDarkMode);
    return;
  }

  // Pre-load / loading indicator feedback in navigation pill & canvas
  if (el.readerPageSpinner) el.readerPageSpinner.style.display = "inline-flex";
  if (el.readerCanvasWrapper) el.readerCanvasWrapper.classList.add("is-page-loading");
  if (state.isFullscreen && el.readerNav) {
    el.readerNav.classList.add("flash-visible");
  }

  const existingSvg = el.readerCanvasWrapper.querySelector("svg");
  if (!existingSvg) {
    el.readerCanvasWrapper.innerHTML = `
      <div style="color: var(--text-muted); padding: 3rem; text-align: center;">Loading page...</div>
    `;
  }

  try {
    const res = await fetch(
      `/api/documents/${state.currentDoc.id}/pages/${pageIdx}/svg?dark=${state.pageDarkMode}&v=4`
    );
    if (!res.ok) throw new Error("Failed to render page");
    const svgText = await res.text();
    pageSvgCache.set(cacheKey, svgText);
    renderSvgContent(svgText);
    preloadAdjacentPages(state.currentDoc.id, pageIdx, totalPages, state.pageDarkMode);
  } catch (e) {
    el.readerCanvasWrapper.innerHTML = `
      <div style="color: var(--danger); padding: 2rem; text-align: center;">Error loading page: ${e.message}</div>
    `;
  } finally {
    if (el.readerPageSpinner) el.readerPageSpinner.style.display = "none";
    if (el.readerCanvasWrapper) el.readerCanvasWrapper.classList.remove("is-page-loading");
  }
}

// --- Reader Page Jump Controller ---
function openPageJumpInput() {
  if (!state.currentDoc) return;
  const pages = (state.currentDoc.pages || []).filter((p) => !p.deleted);
  const totalPages = Math.max(pages.length, 1);

  if (!el.readerPageDisplay || !el.readerPageJumpForm || !el.readerPageInput) return;

  el.readerNav?.classList.add("is-editing");
  el.readerPageDisplay.style.display = "none";
  el.readerPageJumpForm.style.display = "inline-flex";
  el.readerPageInput.value = String(state.currentPageIdx + 1);
  el.readerPageInput.max = String(totalPages);
  if (el.readerPageTotalEdit) el.readerPageTotalEdit.textContent = String(totalPages);

  setTimeout(() => {
    el.readerPageInput.focus();
    el.readerPageInput.select();
  }, 10);
}

function closePageJumpInput(applyJump = false) {
  if (!el.readerPageDisplay || !el.readerPageJumpForm || !el.readerPageInput) return;
  if (el.readerPageJumpForm.style.display === "none") return;

  if (applyJump && state.currentDoc) {
    const pages = (state.currentDoc.pages || []).filter((p) => !p.deleted);
    const totalPages = Math.max(pages.length, 1);
    const val = parseInt(el.readerPageInput.value, 10);
    if (!isNaN(val)) {
      const targetIdx = Math.max(0, Math.min(val - 1, totalPages - 1));
      if (targetIdx !== state.currentPageIdx) {
        state.currentPageIdx = targetIdx;
        loadCurrentPage();
      }
    }
  }

  el.readerPageJumpForm.style.display = "none";
  el.readerPageDisplay.style.display = "inline-flex";
  el.readerNav?.classList.remove("is-editing");
  el.readerPageInput.value = String(state.currentPageIdx + 1);
}

if (el.readerPageIndicator) {
  el.readerPageIndicator.addEventListener("click", (e) => {
    if (e.target.closest("#reader-page-jump-form")) return;
    openPageJumpInput();
  });
  el.readerPageIndicator.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && el.readerPageJumpForm?.style.display === "none") {
      e.preventDefault();
      openPageJumpInput();
    }
  });
}

if (el.readerPageInput) {
  el.readerPageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      closePageJumpInput(true);
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closePageJumpInput(false);
    }
  });

  el.readerPageInput.addEventListener("blur", () => {
    closePageJumpInput(true);
  });
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
  resetZoom(false);
  if (el.readerContent) {
    el.readerContent.scrollTop = 0;
    el.readerContent.scrollLeft = 0;
  }
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
  resetZoom(false);

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
    if (readerZoomState.hasMoved || readerZoomState.scale > 1.05) return;
    if (state.currentPageIdx > 0) {
      state.currentPageIdx--;
      loadCurrentPage();
    }
  });
}

if (el.zoneNext) {
  el.zoneNext.addEventListener("click", (e) => {
    e.stopPropagation();
    if (readerZoomState.hasMoved || readerZoomState.scale > 1.05) return;
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
    if (readerZoomState.hasMoved || readerZoomState.scale > 1.05) return;
    toggleHud();
  });
}

document.addEventListener("fullscreenchange", () => {
  if (!document.fullscreenElement && state.isFullscreen) {
    toggleFullscreenMode(false);
  }
});

// --- Reader Pinch-to-Zoom & Pan Controller ---
const readerZoomState = {
  scale: 1,
  minScale: 1,
  maxScale: 4.5,
  translateX: 0,
  translateY: 0,
  isPinching: false,
  isPanning: false,
  initialDistance: 0,
  initialScale: 1,
  initialTranslateX: 0,
  initialTranslateY: 0,
  pinchCenterX: 0,
  pinchCenterY: 0,
  lastTouchX: 0,
  lastTouchY: 0,
  lastTapTime: 0,
  hasMoved: false,
};

function applyZoomTransform(animate = false) {
  if (!el.readerCanvasWrapper) return;
  if (animate) {
    el.readerCanvasWrapper.style.transition = "transform 0.22s cubic-bezier(0.16, 1, 0.3, 1)";
  } else {
    el.readerCanvasWrapper.style.transition = "none";
  }

  if (
    readerZoomState.scale <= 1.01 &&
    Math.abs(readerZoomState.translateX) < 1 &&
    Math.abs(readerZoomState.translateY) < 1
  ) {
    el.readerCanvasWrapper.style.transform = "none";
    if (el.readerClickZones) {
      el.readerClickZones.style.pointerEvents = state.isFullscreen ? "auto" : "none";
    }
  } else {
    el.readerCanvasWrapper.style.transform = `translate3d(${readerZoomState.translateX}px, ${readerZoomState.translateY}px, 0) scale(${readerZoomState.scale})`;
    if (el.readerClickZones) {
      el.readerClickZones.style.pointerEvents = "none";
    }
  }
}

function clampPanBounds() {
  if (!el.readerCanvasWrapper || !el.readerContent) return;
  const contentRect = el.readerContent.getBoundingClientRect();
  const wrapperRect = el.readerCanvasWrapper.getBoundingClientRect();

  const scaledWidth = (wrapperRect.width / (readerZoomState.scale || 1)) * readerZoomState.scale;
  const scaledHeight = (wrapperRect.height / (readerZoomState.scale || 1)) * readerZoomState.scale;

  const maxPanX = Math.max(0, (scaledWidth - contentRect.width) / 2 + 60);
  const maxPanY = Math.max(0, (scaledHeight - contentRect.height) / 2 + 60);

  readerZoomState.translateX = Math.max(-maxPanX, Math.min(readerZoomState.translateX, maxPanX));
  readerZoomState.translateY = Math.max(-maxPanY, Math.min(readerZoomState.translateY, maxPanY));
}

function resetZoom(animate = true) {
  readerZoomState.scale = 1;
  readerZoomState.translateX = 0;
  readerZoomState.translateY = 0;
  readerZoomState.isPinching = false;
  readerZoomState.isPanning = false;
  readerZoomState.hasMoved = false;

  applyZoomTransform(animate);

  if (el.readerClickZones) {
    el.readerClickZones.style.pointerEvents = state.isFullscreen ? "auto" : "none";
  }

  if (el.readerContent) {
    el.readerContent.scrollTop = 0;
    el.readerContent.scrollLeft = 0;
  }
}

function zoomTo(targetScale, clientX, clientY, animate = true) {
  if (!el.readerContent || !el.readerCanvasWrapper) return;
  const contentRect = el.readerContent.getBoundingClientRect();
  const rectCenter = {
    x: contentRect.left + contentRect.width / 2,
    y: contentRect.top + contentRect.height / 2,
  };

  const oldScale = readerZoomState.scale;
  const newScale = Math.min(
    Math.max(targetScale, readerZoomState.minScale),
    readerZoomState.maxScale
  );

  if (newScale <= 1.05) {
    resetZoom(animate);
    return;
  }

  const focalX = (clientX !== undefined ? clientX : rectCenter.x) - rectCenter.x;
  const focalY = (clientY !== undefined ? clientY : rectCenter.y) - rectCenter.y;

  const scaleRatio = newScale / oldScale;
  readerZoomState.translateX = (readerZoomState.translateX - focalX) * scaleRatio + focalX;
  readerZoomState.translateY = (readerZoomState.translateY - focalY) * scaleRatio + focalY;
  readerZoomState.scale = newScale;

  clampPanBounds();
  applyZoomTransform(animate);
}

if (el.readerContent) {
  el.readerContent.addEventListener(
    "touchstart",
    (e) => {
      if (
        e.target.closest("button") ||
        e.target.closest("input") ||
        e.target.closest("textarea") ||
        e.target.closest("#reader-nav")
      ) {
        return;
      }

      readerZoomState.hasMoved = false;

      if (e.touches.length === 2) {
        readerZoomState.isPinching = true;
        readerZoomState.isPanning = false;
        readerZoomState.hasMoved = true;
        readerZoomState.initialDistance = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        readerZoomState.initialScale = readerZoomState.scale;
        readerZoomState.initialTranslateX = readerZoomState.translateX;
        readerZoomState.initialTranslateY = readerZoomState.translateY;
        readerZoomState.pinchCenterX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        readerZoomState.pinchCenterY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      } else if (e.touches.length === 1 && readerZoomState.scale > 1.05) {
        readerZoomState.isPanning = true;
        readerZoomState.isPinching = false;
        readerZoomState.lastTouchX = e.touches[0].clientX;
        readerZoomState.lastTouchY = e.touches[0].clientY;
      }
    },
    { passive: true }
  );

  el.readerContent.addEventListener(
    "touchmove",
    (e) => {
      if (readerZoomState.isPinching && e.touches.length === 2) {
        if (e.cancelable) e.preventDefault();
        readerZoomState.hasMoved = true;

        const currentDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        if (readerZoomState.initialDistance > 0) {
          const ratio = currentDist / readerZoomState.initialDistance;
          const targetScale = Math.min(
            Math.max(readerZoomState.initialScale * ratio, 0.9),
            readerZoomState.maxScale + 0.5
          );

          const curCenterX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
          const curCenterY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
          const dCenterX = curCenterX - readerZoomState.pinchCenterX;
          const dCenterY = curCenterY - readerZoomState.pinchCenterY;

          readerZoomState.scale = targetScale;
          readerZoomState.translateX = readerZoomState.initialTranslateX + dCenterX;
          readerZoomState.translateY = readerZoomState.initialTranslateY + dCenterY;
          applyZoomTransform(false);
        }
      } else if (
        readerZoomState.isPanning &&
        e.touches.length === 1 &&
        readerZoomState.scale > 1.05
      ) {
        const dx = e.touches[0].clientX - readerZoomState.lastTouchX;
        const dy = e.touches[0].clientY - readerZoomState.lastTouchY;

        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
          readerZoomState.hasMoved = true;
          if (e.cancelable) e.preventDefault();

          readerZoomState.translateX += dx;
          readerZoomState.translateY += dy;
          clampPanBounds();
          applyZoomTransform(false);

          readerZoomState.lastTouchX = e.touches[0].clientX;
          readerZoomState.lastTouchY = e.touches[0].clientY;
        }
      }
    },
    { passive: false }
  );

  el.readerContent.addEventListener(
    "touchend",
    (e) => {
      if (readerZoomState.isPinching && e.touches.length < 2) {
        readerZoomState.isPinching = false;
        if (readerZoomState.scale < 1.05) {
          resetZoom(true);
        } else {
          readerZoomState.scale = Math.min(readerZoomState.scale, readerZoomState.maxScale);
          clampPanBounds();
          applyZoomTransform(true);
        }
      } else if (readerZoomState.isPanning && e.touches.length === 0) {
        readerZoomState.isPanning = false;
        clampPanBounds();
        applyZoomTransform(true);
      }

      // Double-tap to zoom toggle
      if (e.touches.length === 0 && !readerZoomState.hasMoved) {
        const now = Date.now();
        if (now - readerZoomState.lastTapTime < 320) {
          readerZoomState.lastTapTime = 0;
          if (readerZoomState.scale > 1.1) {
            resetZoom(true);
          } else {
            const touch = e.changedTouches && e.changedTouches[0];
            if (touch) {
              zoomTo(2.2, touch.clientX, touch.clientY, true);
            } else {
              zoomTo(2.2, window.innerWidth / 2, window.innerHeight / 2, true);
            }
          }
        } else {
          readerZoomState.lastTapTime = now;
        }
      }

      if (readerZoomState.hasMoved && e.touches.length === 0) {
        setTimeout(() => {
          readerZoomState.hasMoved = false;
        }, 320);
      }
    },
    { passive: true }
  );

  // Wheel / Trackpad pinch-to-zoom support
  el.readerContent.addEventListener(
    "wheel",
    (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = -e.deltaY * 0.006;
        const newScale = Math.min(
          Math.max(readerZoomState.scale + delta, readerZoomState.minScale),
          readerZoomState.maxScale
        );
        zoomTo(newScale, e.clientX, e.clientY, false);
      }
    },
    { passive: false }
  );
}

window.addEventListener("resize", () => {
  if (state.currentDoc && readerZoomState.scale > 1.05) {
    resetZoom(false);
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
  const device = el.converterDevice ? el.converterDevice.value : "paper_pro";
  const docId = el.converterDocId.value;
  const uploadedFile = el.converterFileInput.files[0];

  if (!docId && !uploadedFile) {
    showToast("Please select a document or upload a file first.", "warning");
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
          device: device,
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
      formData.append("device", device);

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
              Single-layer linearized PDF formatted for your screen. Loads instantly on reMarkable.
            </span>
          `;
          el.btnConverterDownload.href = `/api/converter/jobs/${jobId}/download`;
          showToast("Document optimization complete!", "success");
        } else if (job.status === "error") {
          clearInterval(state.converterPollInterval);
          state.converterPollInterval = null;
          el.converterProgressArea.style.display = "none";
          showToast(`Conversion error: ${job.error}`, "error");
          el.btnConverterStart.disabled = false;
        }
      } catch (err) {
        console.error("Job poll error", err);
      }
    }, 600);
  } catch (err) {
    el.converterProgressArea.style.display = "none";
    showToast(`Failed to start job: ${err.message}`, "error");
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

  if (state.currentView === "settings") {
    if (e.key === "Escape") {
      navigateToView("library", true);
      return;
    }
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
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
      if (e.target === el.readerPageInput && e.key === "Escape") {
        e.preventDefault();
        closePageJumpInput(false);
      }
      return;
    }
    if (e.key === "Escape") {
      if (state.isFullscreen) {
        toggleFullscreenMode(false);
      } else {
        closeReader();
      }
    } else if (e.key === "g" || e.key === "G") {
      e.preventDefault();
      openPageJumpInput();
    } else if (e.key === "f" || e.key === "F") {
      e.preventDefault();
      toggleFullscreenMode();
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

    const markerIcon = t.marker_type === "star" 
      ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>` 
      : `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>`;

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
        showToast(`Task scan complete! Found ${data.tasks_found} tasks.`, "success");
        fetchTasks();
      }
    } catch (e) {
      showToast(`Scan failed: ${e.message}`, "error");
    } finally {
      el.btnTasksScanAll.disabled = false;
      el.btnTasksScanAll.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"></path><path d="M16 21h5v-5"></path></svg><span>Scan Documents</span>`;
    }
  });
}

// --- Settings View Controller ---
function navigateToView(viewName, updateHistory = true) {
  if (viewName === "settings") {
    state.currentView = "settings";
    if (el.libraryView) el.libraryView.style.display = "none";
    if (el.readerView) el.readerView.style.display = "none";
    if (el.settingsView) el.settingsView.style.display = "block";

    loadVisionSettings();
    loadDeliverySettings();
    updateSettingsSystemStats();
    applyAppTheme(state.themePreference);

    if (updateHistory) {
      try {
        const url = new URL(window.location.href);
        url.searchParams.set("view", "settings");
        url.searchParams.delete("read");
        url.searchParams.delete("page");
        url.searchParams.delete("doc");
        window.history.pushState({ view: "settings" }, "", url.toString());
      } catch (_) {}
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else {
    state.currentView = "library";
    if (el.settingsView) el.settingsView.style.display = "none";
    if (el.readerView && !state.currentDoc) el.readerView.style.display = "none";
    if (el.libraryView) el.libraryView.style.display = "block";

    if (updateHistory) {
      try {
        const url = new URL(window.location.href);
        url.searchParams.delete("view");
        window.history.pushState({ view: "library" }, "", url.pathname + (url.search ? url.search : ""));
      } catch (_) {}
    }
  }
}

function openSettingsModal() {
  navigateToView("settings", true);
}

function closeSettingsModal() {
  navigateToView("library", true);
}

if (el.btnSettingsToggle) el.btnSettingsToggle.addEventListener("click", () => navigateToView("settings", true));
if (el.btnSettingsBack) el.btnSettingsBack.addEventListener("click", () => navigateToView("library", true));
if (el.btnSettingsClose && el.btnSettingsClose !== el.btnSettingsBack) {
  el.btnSettingsClose.addEventListener("click", () => navigateToView("library", true));
}

if (el.btnToggleKeyVisibility && el.settingsApiKey) {
  el.btnToggleKeyVisibility.addEventListener("click", () => {
    const isPass = el.settingsApiKey.type === "password";
    el.settingsApiKey.type = isPass ? "text" : "password";
    el.btnToggleKeyVisibility.innerHTML = isPass 
      ? '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>' 
      : '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
  });
}

if (el.btnSettingsSyncTrigger) {
  el.btnSettingsSyncTrigger.addEventListener("click", async () => {
    el.btnSettingsSyncTrigger.disabled = true;
    el.btnSettingsSyncTrigger.textContent = "Triggering...";
    try {
      await fetch("/api/sync/trigger", { method: "POST" });
      showToast("Background sync initiated", "info");
      await fetchStatus();
      await updateSettingsSystemStats();
    } catch (e) {
      showToast(`Sync failed: ${e.message}`, "error");
    } finally {
      el.btnSettingsSyncTrigger.disabled = false;
      el.btnSettingsSyncTrigger.textContent = "Sync Now";
    }
  });
}

if (el.btnSettingsSyncDrawerToggle) {
  el.btnSettingsSyncDrawerToggle.addEventListener("click", () => {
    toggleSyncDrawer();
  });
}

if (el.btnSettingsLogout) {
  el.btnSettingsLogout.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to log out and unlink your reMarkable tablet? Local cached files will remain, but cloud syncing will pause until reconnected.")) {
      return;
    }
    el.btnSettingsLogout.disabled = true;
    el.btnSettingsLogout.textContent = "Unlinking...";
    try {
      const res = await fetch("/api/auth/logout", { method: "POST" });
      if (res.ok) {
        showToast("Tablet successfully unlinked from reMarkable Cloud.", "success");
        await fetchStatus();
        await updateSettingsSystemStats();
      } else {
        showToast("Failed to log out", "error");
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, "error");
    } finally {
      el.btnSettingsLogout.disabled = false;
      el.btnSettingsLogout.textContent = "Log Out / Unlink Tablet";
    }
  });
}

if (el.btnSettingsScanTasks) {
  el.btnSettingsScanTasks.addEventListener("click", async () => {
    el.btnSettingsScanTasks.disabled = true;
    el.btnSettingsScanTasks.textContent = "Scanning documents...";
    try {
      const res = await fetch("/api/tasks/scan-all", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        showToast(`Scan complete! Extracted ${data.tasks_extracted ?? 0} tasks from ${data.documents_scanned ?? 0} documents.`, "success");
        await updateSettingsSystemStats();
        fetchTasks();
      } else {
        showToast("Scan failed", "error");
      }
    } catch (e) {
      showToast(`Scan failed: ${e.message}`, "error");
    } finally {
      el.btnSettingsScanTasks.disabled = false;
      el.btnSettingsScanTasks.innerHTML = `${ICONS.tasks}<span>Scan Documents for Tasks</span>`;
    }
  });
}

async function updateSettingsSystemStats() {
  const origin = window.location.origin;
  const host = window.location.hostname || "127.0.0.1";

  if (el.mcpHttpUrl) {
    el.mcpHttpUrl.textContent = `${origin}/mcp/sse`;
  }

  const sseSnippet = document.getElementById("mcp-config-sse-snippet");
  if (sseSnippet) {
    sseSnippet.textContent = JSON.stringify({
      mcpServers: {
        remarkable: {
          url: `${origin}/mcp/sse`
        }
      }
    }, null, 2);
  }

  const sshSnippet = document.getElementById("mcp-config-ssh-snippet");
  if (sshSnippet) {
    sshSnippet.textContent = JSON.stringify({
      mcpServers: {
        "remarkable-remote": {
          command: "ssh",
          args: [
            `user@${host}`,
            "docker", "exec", "-i", "rmcompanion", "python", "-m", "rmcompanion.mcp.server"
          ]
        }
      }
    }, null, 2);
  }

  const proxySnippet = document.getElementById("mcp-config-proxy-snippet");
  if (proxySnippet) {
    proxySnippet.textContent = JSON.stringify({
      mcpServers: {
        "remarkable-remote": {
          command: "npx",
          args: [
            "-y",
            "mcp-proxy",
            `${origin}/mcp/sse`
          ]
        }
      }
    }, null, 2);
  }

  // Update cloud sync status
  try {
    const statusRes = await fetch("/api/status");
    if (statusRes.ok) {
      const statusData = await statusRes.json();
      const sync = statusData.sync || {};
      if (el.settingsCloudStatusTitle && el.settingsCloudStatusDesc) {
        if (!sync.is_authenticated) {
          el.settingsCloudStatusTitle.textContent = "Connection Status: Not Linked";
          el.settingsCloudStatusDesc.textContent = "Your instance is not paired with a reMarkable cloud account. Pair using the link banner or auth code.";
        } else if (sync.status === "syncing") {
          const p = sync.progress || {};
          const pct = p.total_docs > 0 ? Math.round((p.current_doc_idx / p.total_docs) * 100) : 0;
          el.settingsCloudStatusTitle.textContent = `Connection Status: Syncing (${pct}%)`;
          el.settingsCloudStatusDesc.textContent = `Continuous sync active. Stage: ${p.stage || "syncing"}.`;
        } else if (sync.status === "error") {
          el.settingsCloudStatusTitle.textContent = "Connection Status: Sync Error";
          el.settingsCloudStatusDesc.textContent = "Encountered an issue during last sync cycle. Open activity log to inspect details.";
        } else {
          el.settingsCloudStatusTitle.textContent = "Connection Status: Connected & Synced";
          el.settingsCloudStatusDesc.textContent = `Device paired. Last sync generation: ${sync.last_generation || 0}. Real-time cloud sync active.`;
        }
      }
    }
  } catch (e) {
    console.error("Failed to load cloud status in settings", e);
  }

  // Update library diagnostics
  try {
    const [docsRes, tasksRes] = await Promise.all([
      fetch("/api/documents"),
      fetch("/api/tasks")
    ]);
    if (docsRes.ok) {
      const docs = await docsRes.json();
      const realDocs = docs.filter(d => d.type !== "CollectionType");
      const notebooks = realDocs.filter(d => d.file_type === "notebook" || (d.type === "DocumentType" && !d.file_type));
      const pdfsAndEpubs = realDocs.filter(d => d.file_type === "pdf" || d.file_type === "epub");

      if (el.statTotalDocs) el.statTotalDocs.textContent = realDocs.length;
      if (el.statNotebooks) el.statNotebooks.textContent = notebooks.length;
      if (el.statPdfs) el.statPdfs.textContent = pdfsAndEpubs.length;
    }
    if (tasksRes.ok) {
      const tasks = await tasksRes.json();
      if (el.statTasks) el.statTasks.textContent = Array.isArray(tasks) ? tasks.length : "-";
    }
  } catch (e) {
    console.error("Failed to load library diagnostics in settings", e);
  }
}

let modelFetchDebounce = null;
async function fetchAndPopulateVisionModels(currentSelected = null) {
  if (!el.settingsModel) return;
  const payload = {
    provider: el.settingsProvider ? el.settingsProvider.value : "gemini",
    api_key: el.settingsApiKey ? el.settingsApiKey.value.trim() : "",
    base_url: el.settingsBaseUrl ? el.settingsBaseUrl.value.trim() : "",
  };

  try {
    const res = await fetch("/api/settings/vision/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return;
    const data = await res.json();
    const models = data.models || [];
    el.settingsModel.innerHTML = "";

    const targetModel = currentSelected || el.settingsModel.value || data.default_model;

    models.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.name;
      if (m.id === targetModel || (!targetModel && m.is_recommended)) {
        opt.selected = true;
      }
      el.settingsModel.appendChild(opt);
    });

    if (targetModel && !models.some((m) => m.id === targetModel)) {
      const customOpt = document.createElement("option");
      customOpt.value = targetModel;
      customOpt.textContent = `${targetModel} (Current)`;
      customOpt.selected = true;
      el.settingsModel.appendChild(customOpt);
    }
  } catch (e) {
    console.debug("Failed to query vision models", e);
  }
}

if (el.settingsProvider) {
  el.settingsProvider.addEventListener("change", () => {
    const isOllama = el.settingsProvider.value === "openai";
    if (el.settingsBaseUrlGroup) {
      el.settingsBaseUrlGroup.style.display = isOllama ? "block" : "none";
    }
    fetchAndPopulateVisionModels();
  });
}

if (el.settingsApiKey) {
  el.settingsApiKey.addEventListener("input", () => {
    clearTimeout(modelFetchDebounce);
    modelFetchDebounce = setTimeout(() => fetchAndPopulateVisionModels(), 600);
  });
}

if (el.settingsBaseUrl) {
  el.settingsBaseUrl.addEventListener("input", () => {
    clearTimeout(modelFetchDebounce);
    modelFetchDebounce = setTimeout(() => fetchAndPopulateVisionModels(), 600);
  });
}

async function loadVisionSettings() {
  try {
    const res = await fetch("/api/settings/vision");
    if (!res.ok) return;
    const conf = await res.json();

    if (el.settingsProvider) el.settingsProvider.value = conf.provider || "gemini";
    if (el.settingsBaseUrl) el.settingsBaseUrl.value = conf.base_url || "";
    if (el.settingsBaseUrlGroup) {
      el.settingsBaseUrlGroup.style.display = conf.provider === "openai" ? "block" : "none";
    }

    await fetchAndPopulateVisionModels(conf.model || "gemini-2.0-flash");

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
        showToast("Vision OCR settings saved successfully!", "success");
        if (el.settingsTestResult) {
          el.settingsTestResult.style.display = "block";
          el.settingsTestResult.style.backgroundColor = "rgba(34, 197, 94, 0.15)";
          el.settingsTestResult.style.color = "var(--success)";
          el.settingsTestResult.textContent = "✓ Vision OCR settings saved successfully!";
        }
      } else {
        showToast("Failed to save settings", "error");
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, "error");
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

// --- News & Puzzles Delivery Controller ---
async function loadDeliverySettings() {
  try {
    const res = await fetch("/api/delivery/settings");
    if (!res.ok) return;
    const settings = await res.json();

    if (el.deliveryNewspaperEnabled) el.deliveryNewspaperEnabled.checked = !!(settings.news_enabled ?? settings.newspaper_enabled);
    if (el.deliveryNewspaperTime) el.deliveryNewspaperTime.value = settings.news_delivery_time || settings.newspaper_time || "06:00";
    if (el.deliveryNewspaperFolder) el.deliveryNewspaperFolder.value = settings.news_folder || settings.newspaper_folder || "Daily News";
    if (el.deliveryIncludeWeather) el.deliveryIncludeWeather.checked = (settings.news_include_weather ?? settings.include_weather) !== false;
    if (el.deliveryWeatherLocation) el.deliveryWeatherLocation.value = settings.news_weather_location || settings.weather_location || "";
    if (el.deliveryIncludeWikipedia) el.deliveryIncludeWikipedia.checked = (settings.news_include_wikipedia ?? settings.include_wikipedia) !== false;
    if (el.deliveryRssFeeds) {
      const feeds = settings.news_rss_feeds || settings.rss_feeds || [];
      el.deliveryRssFeeds.value = feeds.join("\n");
    }
    if (el.deliveryNewspaperStatus) {
      const lastNews = settings.last_news_delivery || settings.last_newspaper_delivery;
      if (lastNews) {
        const d = new Date(lastNews);
        el.deliveryNewspaperStatus.textContent = `Last delivered: ${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      } else {
        el.deliveryNewspaperStatus.textContent = "Not delivered yet";
      }
    }

    if (el.deliveryPuzzlesEnabled) el.deliveryPuzzlesEnabled.checked = !!settings.puzzles_enabled;
    if (el.deliveryPuzzlesTime) el.deliveryPuzzlesTime.value = settings.puzzles_delivery_time || settings.puzzles_time || "06:00";
    if (el.deliveryPuzzlesFolder) el.deliveryPuzzlesFolder.value = settings.puzzles_folder || "Puzzles";
    if (el.deliveryIncludeQuick) el.deliveryIncludeQuick.checked = (settings.puzzles_guardian_quick ?? settings.include_guardian_quick) !== false;
    if (el.deliveryIncludeCryptic) el.deliveryIncludeCryptic.checked = (settings.puzzles_guardian_cryptic ?? settings.include_guardian_cryptic) !== false;
    if (el.deliveryIncludeSudoku) el.deliveryIncludeSudoku.checked = (settings.puzzles_sudoku ?? settings.include_sudoku) !== false;
    if (el.deliverySudokuDifficulty) el.deliverySudokuDifficulty.value = settings.puzzles_sudoku_difficulty || settings.sudoku_difficulty || "medium";
    if (el.deliveryPuzzlesStatus) {
      const lastPuzzles = settings.last_puzzles_delivery;
      if (lastPuzzles) {
        const d = new Date(lastPuzzles);
        el.deliveryPuzzlesStatus.textContent = `Last delivered: ${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      } else {
        el.deliveryPuzzlesStatus.textContent = "Not delivered yet";
      }
    }
  } catch (err) {
    console.error("Failed to load delivery settings", err);
  }
}

async function saveDeliverySettings() {
  if (!el.btnDeliverySave) return;
  const rawFeeds = (el.deliveryRssFeeds ? el.deliveryRssFeeds.value : "")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);

  const payload = {
    news_enabled: el.deliveryNewspaperEnabled ? el.deliveryNewspaperEnabled.checked : false,
    news_delivery_time: el.deliveryNewspaperTime ? el.deliveryNewspaperTime.value : "06:00",
    news_folder: (el.deliveryNewspaperFolder ? el.deliveryNewspaperFolder.value.trim() : "") || "Daily News",
    news_include_weather: el.deliveryIncludeWeather ? el.deliveryIncludeWeather.checked : true,
    news_weather_location: el.deliveryWeatherLocation ? el.deliveryWeatherLocation.value.trim() : "",
    news_include_wikipedia: el.deliveryIncludeWikipedia ? el.deliveryIncludeWikipedia.checked : true,
    news_rss_feeds: rawFeeds,

    puzzles_enabled: el.deliveryPuzzlesEnabled ? el.deliveryPuzzlesEnabled.checked : false,
    puzzles_delivery_time: el.deliveryPuzzlesTime ? el.deliveryPuzzlesTime.value : "06:00",
    puzzles_folder: (el.deliveryPuzzlesFolder ? el.deliveryPuzzlesFolder.value.trim() : "") || "Puzzles",
    puzzles_guardian_quick: el.deliveryIncludeQuick ? el.deliveryIncludeQuick.checked : true,
    puzzles_guardian_cryptic: el.deliveryIncludeCryptic ? el.deliveryIncludeCryptic.checked : true,
    puzzles_sudoku: el.deliveryIncludeSudoku ? el.deliveryIncludeSudoku.checked : true,
    puzzles_sudoku_difficulty: el.deliverySudokuDifficulty ? el.deliverySudokuDifficulty.value : "medium",
  };

  try {
    el.btnDeliverySave.disabled = true;
    if (el.deliverySaveStatus) {
      el.deliverySaveStatus.textContent = "Saving settings...";
      el.deliverySaveStatus.style.color = "var(--text-muted)";
    }

    const res = await fetch("/api/delivery/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to save settings");
    }

    if (el.deliverySaveStatus) {
      el.deliverySaveStatus.textContent = "✓ Settings saved successfully";
      el.deliverySaveStatus.style.color = "var(--success)";
      setTimeout(() => {
        if (el.deliverySaveStatus) el.deliverySaveStatus.textContent = "";
      }, 3500);
    }
    showToast("Delivery settings saved", "success");
  } catch (err) {
    console.error("Save delivery settings error:", err);
    if (el.deliverySaveStatus) {
      el.deliverySaveStatus.textContent = `✗ ${err.message}`;
      el.deliverySaveStatus.style.color = "var(--danger)";
    }
    showToast(err.message, "error");
  } finally {
    if (el.btnDeliverySave) el.btnDeliverySave.disabled = false;
  }
}

async function triggerNewspaperDelivery() {
  if (!el.btnDeliveryNewspaperNow) return;
  const originalText = el.btnDeliveryNewspaperNow.innerHTML;
  try {
    el.btnDeliveryNewspaperNow.disabled = true;
    el.btnDeliveryNewspaperNow.innerHTML = `
      <svg class="spinning" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
      <span>Generating Newspaper...</span>
    `;
    showToast("Generating today's newspaper digest...", "info");

    const res = await fetch("/api/delivery/newspaper/trigger", { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Newspaper delivery failed");
    }
    const data = await res.json();
    showToast(`Delivered newspaper to "${data.folder || 'Daily News'}"!`, "success");
    await loadDeliverySettings();
    await fetchDocuments();
  } catch (err) {
    console.error("Newspaper delivery failed:", err);
    showToast(err.message, "error");
  } finally {
    el.btnDeliveryNewspaperNow.disabled = false;
    el.btnDeliveryNewspaperNow.innerHTML = originalText;
  }
}

async function triggerPuzzlesDelivery() {
  if (!el.btnDeliveryPuzzlesNow) return;
  const originalText = el.btnDeliveryPuzzlesNow.innerHTML;
  try {
    el.btnDeliveryPuzzlesNow.disabled = true;
    el.btnDeliveryPuzzlesNow.innerHTML = `
      <svg class="spinning" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
      <span>Fetching Puzzles...</span>
    `;
    showToast("Fetching Guardian crosswords and generating Sudoku...", "info");

    const res = await fetch("/api/delivery/puzzles/trigger", { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Puzzles delivery failed");
    }
    const data = await res.json();
    const count = data.delivered ? data.delivered.length : 0;
    showToast(`Delivered ${count} puzzle(s) to "${data.folder || 'Puzzles'}"!`, "success");
    await loadDeliverySettings();
    await fetchDocuments();
  } catch (err) {
    console.error("Puzzles delivery failed:", err);
    showToast(err.message, "error");
  } finally {
    el.btnDeliveryPuzzlesNow.disabled = false;
    el.btnDeliveryPuzzlesNow.innerHTML = originalText;
  }
}

if (el.btnDeliverySave) el.btnDeliverySave.addEventListener("click", saveDeliverySettings);
if (el.btnDeliveryNewspaperNow) el.btnDeliveryNewspaperNow.addEventListener("click", triggerNewspaperDelivery);
if (el.btnDeliveryPuzzlesNow) el.btnDeliveryPuzzlesNow.addEventListener("click", triggerPuzzlesDelivery);

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
        showToast("Typed text saved and synced", "success");
        if (el.readerTypingPane) el.readerTypingPane.style.display = "none";
        if (el.btnReaderTypeToggle) {
          el.btnReaderTypeToggle.classList.remove("active");
          el.btnReaderTypeToggle.textContent = "⌨ Type";
        }
      } else {
        showToast("Failed to save typed text", "error");
      }
    } catch (e) {
      showToast(`Error saving text: ${e.message}`, "error");
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
      opt.textContent = f.visible_name;
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
        showToast(`Notebook "${title}" created`, "success");
        await fetchDocuments();
        fetchTasks();
        openReader(newDoc.id, 0);
      } else {
        showToast("Failed to create notebook", "error");
      }
    } catch (e) {
      showToast(`Error creating notebook: ${e.message}`, "error");
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
        showToast("Task added to Tasks notebook", "success");
        await fetchTasks();
      } else {
        showToast("Failed to add task", "error");
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, "error");
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
        showToast(`Successfully synced ${data.result.task_count} tasks to 'Tasks' notebook!`, "success");
        fetchDocuments();
      } else {
        showToast("Failed to sync tasks to notebook", "error");
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, "error");
    } finally {
      el.btnSyncTasksNotebook.disabled = false;
      el.btnSyncTasksNotebook.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg><span>Sync to 'Tasks' Notebook</span>`;
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
      showToast(isTask ? "Task captured and saved to tablet" : "Note saved to Quick Notes", "success");
      if (isTask) {
        await fetchTasks();
      } else {
        await fetchDocuments();
      }
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(`Capture failed: ${err.detail || "Server error"}`, "error");
    }
  } catch (err) {
    showToast(`Capture error: ${err.message}`, "error");
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
  if (el.folderOptionsMenu && !e.target.closest("#folder-options-container")) {
    el.folderOptionsMenu.style.display = "none";
  }
  if (el.readerMoreMenuDesktop && !e.target.closest(".reader-more-container")) {
    el.readerMoreMenuDesktop.style.display = "none";
  }
});

if (el.menuNewNote) {
  el.menuNewNote.addEventListener("click", () => {
    if (el.newItemDropdown) el.newItemDropdown.style.display = "none";
    if (el.btnNewNotebook) el.btnNewNotebook.click();
  });
}

if (el.menuQuickCapture) {
  el.menuQuickCapture.addEventListener("click", () => {
    if (el.newItemDropdown) el.newItemDropdown.style.display = "none";
    openQuickCapture();
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
          opt.textContent = `${prefix}${f.visible_name || f.name || "Untitled Folder"}`;
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
    icon: ICONS.notebook,
    title: "New Notebook",
    desc: "Create a blank note or import Markdown",
    action: () => { if (el.btnNewNotebook) el.btnNewNotebook.click(); },
  },
  {
    id: "new-folder",
    icon: ICONS.folder,
    title: "New Folder",
    desc: "Create a new folder in current location",
    action: () => { if (el.btnNewFolder) el.btnNewFolder.click(); },
  },
  {
    id: "bulk-import",
    icon: ICONS.download,
    title: "Bulk Import Files",
    desc: "Upload multiple PDF, EPUB, or Markdown files",
    action: () => openBulkImportModal(),
  },
  {
    id: "quick-capture",
    icon: ICONS.quickCapture,
    title: "Quick Capture",
    desc: "Instantly capture an action item or note",
    action: () => { if (el.btnQuickCapture) el.btnQuickCapture.click(); },
  },
  {
    id: "sync-now",
    icon: ICONS.sync,
    title: "Sync with Cloud",
    desc: "Trigger live background synchronization",
    action: () => { if (el.btnSyncNow) el.btnSyncNow.click(); },
  },
  {
    id: "open-tasks",
    icon: ICONS.tasks,
    title: "Open Tasks",
    desc: "View consolidated action items across notebooks",
    action: () => { if (el.btnTasksToggle) el.btnTasksToggle.click(); },
  },
  {
    id: "settings",
    icon: ICONS.settings,
    title: "Settings & AI OCR",
    desc: "Configure Vision providers and MCP integrations",
    action: () => { if (el.btnSettingsToggle) el.btnSettingsToggle.click(); },
  },
  {
    id: "toggle-theme",
    icon: ICONS.theme,
    title: "Toggle Theme (Dark / Light / Auto)",
    desc: "Switch between dark, light, or auto system theme",
    action: () => { if (el.btnThemeToggle) el.btnThemeToggle.click(); },
  },
  {
    id: "optimize-pro",
    icon: ICONS.optimize,
    title: "Optimize for reMarkable",
    desc: "Convert a comic or heavy document for reMarkable",
    action: () => { if (el.btnOpenConverter) el.btnOpenConverter.click(); },
  },
  {
    id: "view-grid",
    icon: ICONS.grid,
    title: "Grid View",
    desc: "Switch library display to grid view",
    action: () => setViewMode("grid"),
  },
  {
    id: "view-list",
    icon: ICONS.list,
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

  const allDocs = (state.allDocs || []).filter((d) => d.parent_id !== "trash");
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
            <span class="command-item-icon">${cmd.icon}</span>
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
      const icon = isFolder ? ICONS.folder : (doc.file_type === "pdf" ? ICONS.pdf : (doc.file_type === "epub" ? ICONS.epub : ICONS.notebook));
      const meta = isFolder ? "Folder" : `${doc.page_count || 1} pages`;
      html += `
        <div class="command-item ${idx === 0 && matchedCommands.length === 0 ? 'selected' : ''}" data-idx="${idx}">
          <div class="command-item-left">
            <span class="command-item-icon">${icon}</span>
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

// --- MCP Tabs & Copy Buttons ---
document.querySelectorAll(".mcp-tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mcp-tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    const panelLocal = document.getElementById("mcp-panel-local");
    const panelSse = document.getElementById("mcp-panel-network-sse");
    const panelClaude = document.getElementById("mcp-panel-network-claude");
    if (panelLocal) panelLocal.style.display = tab === "local" ? "block" : "none";
    if (panelSse) panelSse.style.display = tab === "network-sse" ? "block" : "none";
    if (panelClaude) panelClaude.style.display = tab === "network-claude" ? "block" : "none";
  });
});

function setupCopyBtn(btn, textSourceId) {
  if (!btn) return;
  btn.addEventListener("click", () => {
    const elTarget = document.getElementById(textSourceId);
    if (!elTarget) return;
    const text = elTarget.innerText;
    navigator.clipboard.writeText(text).then(() => {
      const origHtml = btn.innerHTML;
      btn.innerHTML = `${ICONS.check}<span>Copied!</span>`;
      setTimeout(() => { btn.innerHTML = origHtml; }, 1500);
    });
  });
}

setupCopyBtn(el.btnCopyMcpConfig, "mcp-config-snippet");
setupCopyBtn(el.btnCopyMcpLocal, "mcp-config-snippet");
setupCopyBtn(el.btnCopyMcpSse, "mcp-config-sse-snippet");
setupCopyBtn(el.btnCopyMcpSsh, "mcp-config-ssh-snippet");
setupCopyBtn(el.btnCopyMcpProxy, "mcp-config-proxy-snippet");
setupCopyBtn(el.btnCopyMcpUrl, "mcp-http-url");

// --- Settings: Rescan & Re-index Library ---
if (el.btnSettingsRescanLibrary) {
  el.btnSettingsRescanLibrary.addEventListener("click", async () => {
    el.btnSettingsRescanLibrary.disabled = true;
    const origHtml = el.btnSettingsRescanLibrary.innerHTML;
    el.btnSettingsRescanLibrary.innerHTML = `<span class="reader-page-spinner" style="margin-right: 0.25rem;">${ICONS.sync}</span><span>Rescanning...</span>`;
    if (el.settingsRescanStatus) {
      el.settingsRescanStatus.style.display = "block";
      el.settingsRescanStatus.style.color = "var(--text-muted)";
      el.settingsRescanStatus.textContent = "Scanning documents and rebuilding index (respecting excluded folders)...";
    }

    try {
      const res = await fetch("/api/settings/rescan", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.ok) {
        if (el.settingsRescanStatus) {
          el.settingsRescanStatus.style.color = "var(--accent)";
          el.settingsRescanStatus.textContent = `✓ ${data.message}`;
        }
        await fetchDocuments();
        await fetchTasks();
        await updateSettingsSystemStats();
      } else {
        throw new Error(data.detail || "Rescan failed");
      }
    } catch (e) {
      if (el.settingsRescanStatus) {
        el.settingsRescanStatus.style.color = "var(--danger)";
        el.settingsRescanStatus.textContent = `✕ Rescan error: ${e.message}`;
      }
    } finally {
      el.btnSettingsRescanLibrary.disabled = false;
      el.btnSettingsRescanLibrary.innerHTML = origHtml;
    }
  });
}

// --- Initialization & Routing ---
setViewMode(state.viewMode);
fetchStatus();
fetchTasks();
fetchDocuments();

window.addEventListener("popstate", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const view = urlParams.get("view");
  const readDocId = urlParams.get("read") || urlParams.get("doc");

  if (view === "settings") {
    navigateToView("settings", false);
  } else if (readDocId) {
    const pageParam = urlParams.get("page");
    const pageIdx = pageParam !== null ? parseInt(pageParam, 10) : null;
    openReader(readDocId, (pageIdx !== null && !isNaN(pageIdx)) ? pageIdx : null);
  } else {
    if (state.currentView === "settings") {
      navigateToView("library", false);
    }
    if (state.currentDoc) {
      closeReader();
    }
  }
});

// Check initial URL parameters for deep linking
try {
  const urlParams = new URLSearchParams(window.location.search);
  const view = urlParams.get("view");
  if (view === "settings") {
    navigateToView("settings", false);
  } else {
    const readDocId = urlParams.get("read") || urlParams.get("doc");
    if (readDocId) {
      const pageParam = urlParams.get("page");
      const pageIdx = pageParam !== null ? parseInt(pageParam, 10) : null;
      openReader(readDocId, (pageIdx !== null && !isNaN(pageIdx)) ? pageIdx : null);
    }
  }
} catch (e) {
  console.error("Deep-link read error", e);
}
