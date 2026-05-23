let state = {
  days: [],
  feedback: [],
  candidates: [],
  calendar: [],
  strategy: null,
  curation: null,
  products: [],
  rawAssets: [],
  rawAssetsLoaded: false,
  actionChecklists: { seo: { items: [] }, ads: { items: [] } },
  performance: { records: [], summary: null },
  creativeBrief: { brief: {}, revisions: [] },
  campaignMemory: { memory: {}, revisions: [] },
  shootPlan: null,
  merchandising: null,
  launchPlan: null,
  communityFaq: null,
  ownedPlan: null,
  automation: null,
  highlights: [],
  contentStates: {},
  lifecycleStates: [],
  selectedHighlightFrame: null,
  selectedDay: null,
  selectedItem: null,
  selectedCandidate: null,
  selectedCalendarItem: null,
  reviewItems: [],
  builderSlotIndex: 0,
  builderAssetFilter: "All",
  mode: "review",
};

const dayList = document.getElementById("dayList");
const postGrid = document.getElementById("postGrid");
const reportList = document.getElementById("reportList");
const preview = document.getElementById("preview");
const selectedTitle = document.getElementById("selectedTitle");
const selectedKind = document.getElementById("selectedKind");
const feedbackPath = document.getElementById("feedbackPath");
const feedbackStatus = document.getElementById("feedbackStatus");
const replaceForm = document.getElementById("replaceForm");
const replaceStatus = document.getElementById("replaceStatus");
const replacementFile = document.getElementById("replacementFile");
const runStatus = document.getElementById("runStatus");
const runNotice = document.getElementById("runNotice");
const runAgentsButton = document.getElementById("runAgents");
const openReviewModalButton = document.getElementById("openReviewModal");
const workspace = document.getElementById("workspace");
const workspaceTitle = document.getElementById("workspaceTitle");
const regenStatus = document.getElementById("regenStatus");
const drivePicker = document.getElementById("drivePicker");
const driveAssetList = document.getElementById("driveAssetList");
const driveReplaceStatus = document.getElementById("driveReplaceStatus");
const calendarGrid = document.getElementById("calendarGrid");
const feedGrid = document.getElementById("feedGrid");
const feedCuration = document.getElementById("feedCuration");
const calendarStrategy = document.getElementById("calendarStrategy");
const modeTitle = document.getElementById("modeTitle");
const builderTitle = document.getElementById("builderTitle");
const builderPreview = document.getElementById("builderPreview");
const builderWorkspace = document.getElementById("builderWorkspace");
const builderAssetTray = document.getElementById("builderAssetTray");
const builderStatus = document.getElementById("builderStatus");
const builderAssetLibrary = document.getElementById("builderAssetLibrary");
const builderAssetFilters = document.getElementById("builderAssetFilters");
const visualArchive = document.getElementById("visualArchive");
const aiVisualArchive = document.getElementById("aiVisualArchive");
const reviewModal = document.getElementById("reviewModal");
const reviewItems = document.getElementById("reviewItems");
const closeReviewModal = document.getElementById("closeReviewModal");
const saveReviewRatings = document.getElementById("saveReviewRatings");
const saveReviewAndCurate = document.getElementById("saveReviewAndCurate");
const reviewModalStatus = document.getElementById("reviewModalStatus");
const imageModal = document.getElementById("imageModal");
const imageModalMedia = document.getElementById("imageModalMedia");
const closeImageModal = document.getElementById("closeImageModal");
const iterationForm = document.getElementById("iterationForm");
const iterationStatus = document.getElementById("iterationStatus");
const seoChecklist = document.getElementById("seoChecklist");
const adsChecklist = document.getElementById("adsChecklist");
const performanceSummary = document.getElementById("performanceSummary");
const performanceList = document.getElementById("performanceList");
const creativeBriefEditor = document.getElementById("creativeBriefEditor");
const campaignMemoryPanel = document.getElementById("campaignMemoryPanel");
const refreshCampaignMemoryButton = document.getElementById("refreshCampaignMemory");
const shootPlan = document.getElementById("shootPlan");
const refreshShootPlanButton = document.getElementById("refreshShootPlan");
const merchandisingPlan = document.getElementById("merchandisingPlan");
const refreshMerchandisingButton = document.getElementById("refreshMerchandising");
const launchPlan = document.getElementById("launchPlan");
const refreshLaunchPlanButton = document.getElementById("refreshLaunchPlan");
const communityFaq = document.getElementById("communityFaq");
const refreshCommunityFaqButton = document.getElementById("refreshCommunityFaq");
const ownedPlan = document.getElementById("ownedPlan");
const refreshOwnedPlanButton = document.getElementById("refreshOwnedPlan");
const automationPanel = document.getElementById("automationPanel");
const highlightGrid = document.getElementById("highlightGrid");
const refreshHighlightsButton = document.getElementById("refreshHighlights");

async function loadDashboard() {
  document.body.classList.add("is-loading");
  const [daysResponse, feedbackResponse, productsResponse] = await Promise.all([
    fetch("/api/days"),
    fetch("/api/feedback"),
    fetch("/api/product-inventory"),
  ]);
  state.days = (await daysResponse.json()).days;
  state.feedback = (await feedbackResponse.json()).feedback;
  state.products = (await productsResponse.json()).products;

  if (!state.selectedDay || !state.days.some((day) => day.date === state.selectedDay.date)) {
    state.selectedDay = state.days[0] || null;
  } else {
    state.selectedDay = state.days.find((day) => day.date === state.selectedDay.date);
  }

  await loadCandidates();
  await loadCalendar();
  await loadCreativeBrief();
  await loadCampaignMemory();
  await loadContentStates();
  renderDashboard();
  document.body.classList.remove("is-loading");
  hydrateSecondaryData();
}

async function hydrateSecondaryData() {
  await Promise.allSettled([
    loadRawAssets(),
    loadActionChecklists(),
    loadPerformance(),
    loadShootPlan(),
    loadMerchandising(),
    loadLaunchPlan(),
    loadCommunityFaq(),
    loadOwnedPlan(),
    loadAutomation(),
    loadHighlights(),
  ]);
  renderDashboard();
}

async function ensureModeData(mode) {
  const jobs = [];
  if (["calendar", "feed", "builder", "performance", "shoot", "merchandising", "launch"].includes(mode) && !state.rawAssetsLoaded) jobs.push(loadRawAssets());
  if (["seo", "ads"].includes(mode) && !(state.actionChecklists?.seo?.items || []).length) jobs.push(loadActionChecklists());
  if (mode === "performance" && !state.performance?.summary) jobs.push(loadPerformance());
  if (mode === "shoot" && !state.shootPlan) jobs.push(loadShootPlan());
  if (mode === "merchandising" && !state.merchandising) jobs.push(loadMerchandising());
  if (mode === "launch" && !state.launchPlan) jobs.push(loadLaunchPlan());
  if (mode === "community" && !state.communityFaq) jobs.push(loadCommunityFaq());
  if (mode === "owned" && !state.ownedPlan) jobs.push(loadOwnedPlan());
  if (mode === "automation" && !state.automation) jobs.push(loadAutomation());
  if (mode === "highlights" && !state.highlights.length) jobs.push(loadHighlights());
  if (jobs.length) {
    document.body.classList.add("is-loading");
    await Promise.allSettled(jobs);
    document.body.classList.remove("is-loading");
  }
}

async function loadCandidates() {
  if (!state.selectedDay) {
    state.candidates = [];
    return;
  }
  const response = await fetch(`/api/candidates?date=${encodeURIComponent(state.selectedDay.date)}`);
  state.candidates = (await response.json()).candidates;
}

async function loadCalendar() {
  const response = await fetch("/api/calendar");
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.curation = data.curation || null;
}

async function loadActionChecklists() {
  const response = await fetch("/api/action-checklists");
  state.actionChecklists = await response.json();
}

async function loadPerformance() {
  const response = await fetch("/api/performance");
  state.performance = await response.json();
}

async function loadCreativeBrief() {
  const response = await fetch("/api/creative-brief");
  state.creativeBrief = await response.json();
}

async function loadCampaignMemory() {
  const response = await fetch("/api/campaign-memory");
  state.campaignMemory = await response.json();
}

async function loadShootPlan() {
  const response = await fetch("/api/shoot-plan");
  state.shootPlan = await response.json();
}

async function loadMerchandising() {
  const response = await fetch("/api/merchandising");
  state.merchandising = await response.json();
}

async function loadLaunchPlan() {
  const response = await fetch("/api/drop-launch");
  state.launchPlan = await response.json();
}

async function loadCommunityFaq() {
  const response = await fetch("/api/community-faq");
  state.communityFaq = await response.json();
}

async function loadOwnedPlan() {
  const response = await fetch("/api/email-sms");
  state.ownedPlan = await response.json();
}

async function loadAutomation() {
  const response = await fetch("/api/automation");
  state.automation = await response.json();
}

async function loadHighlights() {
  const response = await fetch("/api/highlights");
  state.highlights = (await response.json()).highlights || [];
}

async function loadContentStates() {
  const response = await fetch("/api/content-state");
  const data = await response.json();
  state.contentStates = data.states || {};
  state.lifecycleStates = data.lifecycle_states || [];
}

function renderDashboard() {
  renderDays();
  renderMetrics();
  renderPosts();
  renderReports();
  renderCalendar();
  renderFeed();
  renderVisualArchive();
  renderHighlights();
  renderActionChecklists();
  renderPerformance();
  renderCampaignMemory();
  renderCreativeBrief();
  renderShootPlan();
  renderMerchandising();
  renderLaunchPlan();
  renderCommunityFaq();
  renderOwnedPlan();
  renderAutomation();
  renderBuilder();
  renderWorkspace();
  renderInlineComments();
  renderMode();
}

function renderMode() {
  document.getElementById("reviewView").classList.toggle("hidden", state.mode !== "review");
  document.getElementById("calendarView").classList.toggle("hidden", state.mode !== "calendar");
  document.getElementById("feedView").classList.toggle("hidden", state.mode !== "feed");
  document.getElementById("builderView").classList.toggle("hidden", state.mode !== "builder");
  document.getElementById("visualsView").classList.toggle("hidden", state.mode !== "visuals");
  document.getElementById("highlightsView").classList.toggle("hidden", state.mode !== "highlights");
  document.getElementById("directionView").classList.toggle("hidden", state.mode !== "direction");
  document.getElementById("seoView").classList.toggle("hidden", state.mode !== "seo");
  document.getElementById("adsView").classList.toggle("hidden", state.mode !== "ads");
  document.getElementById("performanceView").classList.toggle("hidden", state.mode !== "performance");
  document.getElementById("shootView").classList.toggle("hidden", state.mode !== "shoot");
  document.getElementById("merchandisingView").classList.toggle("hidden", state.mode !== "merchandising");
  document.getElementById("launchView").classList.toggle("hidden", state.mode !== "launch");
  document.getElementById("communityView").classList.toggle("hidden", state.mode !== "community");
  document.getElementById("ownedView").classList.toggle("hidden", state.mode !== "owned");
  document.getElementById("automationView").classList.toggle("hidden", state.mode !== "automation");
  document.querySelectorAll(".mode-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === state.mode);
  });
  modeTitle.textContent = {
    review: "Review generated posts, notes, and reports.",
    calendar: "Plan the week by rhythm, format, and brand fit.",
    feed: "Curate the next grid before anything goes live.",
    builder: "Build one post until it is ready to approve.",
    visuals: "Browse generated visual directions and concept renders.",
    highlights: "Curate profile highlight covers and story frames.",
    direction: "Steer every agent from one current creative brief.",
    seo: "Review SEO changes before they touch Shopify.",
    ads: "Review ad readiness before any campaign action.",
    performance: "Record what posted, what worked, and what agents should learn.",
    shoot: "Turn feed and content gaps into a practical shoot list.",
    merchandising: "Rotate products intentionally before the feed gets repetitive.",
    launch: "Coordinate a drop across content, profile, SEO, ads, and shoots.",
    community: "Turn audience questions into useful replies and highlights.",
    owned: "Reuse approved content for email and SMS drafts.",
    automation: "Run agents on a rhythm without skipping approval.",
  }[state.mode];
}

function renderDays() {
  dayList.innerHTML = "";
  if (!state.days.length) {
    dayList.innerHTML = '<div class="empty-note">No runs yet.</div>';
    return;
  }

  state.days.forEach((day) => {
    const button = document.createElement("button");
    button.className = `day-button ${state.selectedDay?.date === day.date ? "active" : ""}`;
    button.innerHTML = `<strong>${day.date}</strong><span>${day.images.length} images / ${day.reports.length} reports</span>`;
    button.addEventListener("click", () => {
      state.selectedDay = day;
      state.selectedItem = null;
      state.selectedCandidate = null;
      state.selectedCalendarItem = null;
      state.builderSlotIndex = 0;
      loadCandidates().then(renderDashboard);
      clearSelection();
    });
    dayList.appendChild(button);
  });
}

function renderMetrics() {
  const day = state.selectedDay;
  document.getElementById("selectedDateLabel").textContent = day ? day.date : "No Day";
  document.getElementById("postCount").textContent = day ? day.images.length + state.candidates.length : 0;
  document.getElementById("reportCount").textContent = day ? day.reports.length : 0;
  document.getElementById("feedbackCount").textContent = state.feedback.length;
}

function renderPosts() {
  postGrid.innerHTML = "";
  const day = state.selectedDay;
  if (!day) {
    postGrid.innerHTML = '<div class="empty-note">Run agents to create previews.</div>';
    return;
  }

  const groups = buildFormatGroups(day);
  Object.entries(groups).forEach(([label, items]) => {
    const section = document.createElement("section");
    section.className = "post-group";
    section.innerHTML = `<h4>${label}</h4>`;
    if (!items.length) {
      section.innerHTML += '<div class="empty-note">No items yet.</div>';
    }
    items.forEach((item) => {
      if (item.type === "candidate") section.appendChild(candidateButton(item.candidate));
      if (item.type === "visualGroup") section.appendChild(visualGroupButton(item.group, label));
      if (item.type === "copy") section.appendChild(textButton(item.item));
    });
    postGrid.appendChild(section);
  });

  if (!day.visuals.length && !day.copy.length && !state.candidates.length) {
    postGrid.innerHTML = '<div class="empty-note">No post previews for this day.</div>';
  }
}

function renderCalendar() {
  if (!calendarGrid) return;
  const days = calendarDays();
  calendarGrid.innerHTML = "";
  days.forEach((day) => {
    const cell = document.createElement("section");
    cell.className = "calendar-day";
    cell.dataset.date = day.date;
    cell.innerHTML = `<div class="calendar-day-head"><strong>${day.label}</strong><span>${day.date}</span></div>`;
    cell.addEventListener("dragover", (event) => event.preventDefault());
    cell.addEventListener("drop", (event) => {
      event.preventDefault();
      const itemId = event.dataTransfer.getData("text/plain");
      moveCalendarItem(itemId, day.date);
    });

    const items = state.calendar.filter((item) => item.scheduled_date === day.date);
    if (!items.length) {
      cell.innerHTML += '<div class="empty-note">Open slot</div>';
    }
    items.forEach((item) => cell.appendChild(calendarCard(item)));
    calendarGrid.appendChild(cell);
  });
  renderStrategy();
}

function calendarDays() {
  const dates = state.calendar.map((item) => item.scheduled_date).filter(Boolean).sort();
  const start = dates.length ? new Date(`${dates[0]}T00:00:00`) : new Date();
  const end = dates.length ? new Date(`${dates[dates.length - 1]}T00:00:00`) : start;
  const daySpan = Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
  const dayCount = Math.max(14, daySpan);
  return Array.from({ length: dayCount }, (_, index) => {
    const current = new Date(start);
    current.setDate(start.getDate() + index);
    return {
      date: current.toISOString().slice(0, 10),
      label: current.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }),
    };
  });
}

function calendarCard(item) {
  const card = document.createElement("article");
  card.className = `calendar-card ${state.selectedCalendarItem?.id === item.id ? "active" : ""} ${duplicateClass(item)}`;
  card.draggable = true;
  card.addEventListener("dragstart", (event) => event.dataTransfer.setData("text/plain", item.id));
  card.addEventListener("click", () => openBuilder(item));
  const previews = calendarItemAssets(item).slice(0, 2);
  const gridPosition = feedPositionLabel(item);
  const adjacent = adjacentFeedLabel(item);
  card.innerHTML = `
    <div class="calendar-card-media">${previews.map((asset) => assetThumb(asset)).join("") || calendarVisualThumb(item)}</div>
    <div class="calendar-card-copy">
      <div class="calendar-card-meta">
        <span>${escapeHtml(gridPosition)}</span>
        <button class="mini-danger" type="button" data-remove-draft="${escapeForAttribute(item.id)}">Remove</button>
      </div>
      <strong>${escapeHtml(item.hook || "Scheduled post")}</strong>
      <span>${escapeHtml(item.format || "Post")} / ${escapeHtml(item.pillar || "General")}</span>
      ${feedRoleBadge(item)}
      ${visualSurfaceBadge(item)}
      ${item.launch_role ? `<small>${escapeHtml(item.launch_role)}</small>` : ""}
      <small>${escapeHtml(item.status || "Draft")} ${adjacent ? `/ ${escapeHtml(adjacent)}` : ""}</small>
      ${stateControls("post", item.id, item.status || "Draft", item.hook || item.id, "calendar-card-actions")}
      ${productRotationBadge(item)}
      ${duplicateBadge(item)}
      ${qualityBadge(item)}
    </div>
  `;
  card.querySelector("[data-remove-draft]")?.addEventListener("click", (event) => {
    event.stopPropagation();
    removeCalendarItem(item.id);
  });
  bindStateControls(card);
  return card;
}

function duplicateClass(item) {
  return item.duplicate_status && item.duplicate_status !== "unique" ? "has-duplicate-warning" : "";
}

function duplicateBadge(item) {
  if (!item.duplicate_status || item.duplicate_status === "unique") return "";
  return `<div class="duplicate-badge" title="${escapeHtml(item.duplicate_note || "")}">${escapeHtml(titleize(item.duplicate_status))}</div>`;
}

function productRotationBadge(item) {
  if (!item.product_keys?.length) return "";
  const label = item.product_keys.slice(0, 2).map(titleize).join(" / ");
  const note = item.product_rotation_note || "Product family tracked for rotation.";
  return `<div class="rotation-badge" title="${escapeHtml(note)}">${escapeHtml(label)}</div>`;
}

function feedRoleBadge(item) {
  const role = item.feed_role || "";
  if (!role) return "";
  return `<div class="rotation-badge feed-role-badge" title="Curator rhythm role">${escapeHtml(titleize(role))}</div>`;
}

function visualSurfaceBadge(item) {
  const surface = item.visual_surface || "";
  if (!surface) return "";
  return `<div class="rotation-badge" title="Visible post surface">${escapeHtml(titleize(surface))}</div>`;
}

function qualityBadge(item) {
  const score = item.quality_score?.overall;
  if (score === undefined || score === null) return "";
  const needs = item.needs_work || [];
  const label = needs.length ? `Q ${score} / Needs Work` : `Q ${score}`;
  return `<div class="quality-badge ${needs.length ? "needs-work" : ""}" title="${escapeHtml(needs.map((entry) => entry.note).join(" "))}">${escapeHtml(label)}</div>`;
}

function visualFingerprintLabel(item) {
  const fingerprint = item.visual_fingerprint || {};
  const parts = [fingerprint.palette, fingerprint.visual_family].filter((value) => value && value !== "unknown");
  if (!parts.length) return "";
  return parts.map(titleize).join(" / ");
}

function feedPositionLabel(item) {
  const index = sortedFeedItems().findIndex((entry) => entry.id === item.id);
  return index >= 0 ? `Grid #${index + 1}` : "Off grid";
}

function adjacentFeedLabel(item) {
  const items = sortedFeedItems();
  const index = items.findIndex((entry) => entry.id === item.id);
  if (index < 0) return "";
  const previous = items[index - 1]?.hook;
  const next = items[index + 1]?.hook;
  if (previous && next) return `between ${previous} / ${next}`;
  if (next) return `next before ${next}`;
  if (previous) return `after ${previous}`;
  return "only post";
}

function calendarVisualThumb(item) {
  const image = item.visual_group?.images?.[0];
  if (!image) return '<div class="asset-placeholder">POST</div>';
  return `<img src="/media?path=${encodeURIComponent(image.path)}" alt="${escapeHtml(image.name)}" loading="lazy" />`;
}

function calendarItemAssets(item) {
  const slotNames = (item.visual_slots || []).map((slot) => slot.asset_name).filter(Boolean);
  return (slotNames.length ? slotNames : item.selected_assets || item.source_files || []).map((name) => findRawAsset(name)).filter(Boolean);
}

async function moveCalendarItem(itemId, date) {
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scheduled_date: date }),
  });
  if (!response.ok) return;
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.curation = data.curation || state.curation;
  state.selectedCalendarItem = state.calendar.find((item) => item.id === state.selectedCalendarItem?.id) || state.selectedCalendarItem;
  renderCalendar();
  renderFeed();
  renderBuilder();
}

async function removeCalendarItem(itemId) {
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}`, { method: "DELETE" });
  if (!response.ok) return;
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.curation = data.curation || state.curation;
  if (state.selectedCalendarItem?.id === itemId) {
    state.selectedCalendarItem = null;
    state.selectedCandidate = null;
  }
  renderCalendar();
  renderFeed();
  renderBuilder();
}

function selectCalendarItem(item) {
  const candidate = state.candidates.find((candidateItem) =>
    candidateItem.index === item.candidate_index && (!item.candidate_source_path || candidateItem.source_path === item.candidate_source_path)
  );
  state.mode = "builder";
  state.selectedCalendarItem = item;
  state.selectedCandidate = candidate || null;
  state.selectedItem = null;
  clearSelection();
  renderPosts();
  renderWorkspace();
  renderMode();
}

function openBuilder(item) {
  state.builderSlotIndex = 0;
  selectCalendarItem(item);
  renderCalendar();
  renderFeed();
  renderBuilder();
}

function renderFeed() {
  if (!feedGrid) return;
  const items = sortedFeedItems();
  feedGrid.innerHTML = "";
  if (!items.length) {
    feedGrid.innerHTML = '<div class="empty-note">No scheduled posts yet.</div>';
    renderFeedCuration();
    return;
  }
  items.forEach((item, index) => {
    const tile = document.createElement("button");
    tile.className = `feed-tile ${state.selectedCalendarItem?.id === item.id ? "active" : ""} ${duplicateClass(item)}`;
    tile.draggable = true;
    tile.dataset.itemId = item.id;
    tile.addEventListener("dragstart", (event) => event.dataTransfer.setData("text/plain", item.id));
    tile.addEventListener("dragover", (event) => event.preventDefault());
    tile.addEventListener("drop", (event) => {
      event.preventDefault();
      reorderFeed(event.dataTransfer.getData("text/plain"), item.id);
    });
    tile.addEventListener("click", () => openBuilder(item));
    const assets = calendarItemAssets(item);
    tile.innerHTML = `
      <div class="feed-media">${assets[0] ? assetThumb(assets[0]) : calendarVisualThumb(item)}</div>
      <div class="feed-overlay">
        <strong>${index + 1}. ${escapeHtml(item.format || "Post")}</strong>
        <span>${escapeHtml(item.scheduled_date || "")} / ${escapeHtml(item.feed_role || item.visual_role || item.pillar || "")}${visualFingerprintLabel(item) ? ` / ${escapeHtml(visualFingerprintLabel(item))}` : ""}</span>
        ${item.launch_role ? `<span>${escapeHtml(item.launch_role)}</span>` : ""}
      </div>
      ${item.curator_reason ? `<div class="curator-note">${escapeHtml(item.curator_reason)}</div>` : ""}
      ${stateControls("post", item.id, item.status || "Draft", item.hook || item.id, "feed-state-actions")}
      ${feedRoleBadge(item)}
      ${productRotationBadge(item)}
      ${duplicateBadge(item)}
    `;
    feedGrid.appendChild(tile);
    bindStateControls(tile);
  });
  renderFeedCuration();
}

function renderFeedCuration() {
  if (!feedCuration) return;
  const curation = state.curation;
  const visualWarnings = state.strategy?.visual_warnings || [];
  if (!curation || !curation.feed_story) {
    feedCuration.innerHTML = `
      <details class="strategy-disclosure">
        <summary><span>Curator</span><strong>Run Curate Feed to arrange posts as a profile story.</strong></summary>
        ${visualWarnings.length ? `<button class="secondary compact-action" type="button" data-fix-visual-clusters>Fix Visual Clusters</button>` : ""}
        ${curatorReconstructControls()}
        <p id="feedFixStatus" class="status"></p>
      </details>
    `;
    bindCuratorControls();
    return;
  }
  feedCuration.innerHTML = `
    <details class="strategy-disclosure">
      <summary><span>Curator Rationale</span><strong>${escapeHtml(curation.rationale?.summary || curation.feed_story)}</strong></summary>
      <div class="strategy-detail-grid">
        <div>
          <p class="eyebrow">Feed Story</p>
          <p>${escapeHtml(curation.feed_story)}</p>
        </div>
        <div>
          <p class="eyebrow">Rules</p>
          <ul>${(curation.rules || []).slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
        <div>
          <p class="eyebrow">Warnings</p>
          <ul>${(curation.warnings || ["No warnings yet."]).slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
        <div>
          <p class="eyebrow">Rows</p>
          <ul>${(curation.rationale?.row_notes || []).slice(0, 6).map((item) => `<li>Row ${escapeHtml(String(item.row))}: ${escapeHtml(item.note || "")}</li>`).join("")}</ul>
        </div>
        <div>
          <p class="eyebrow">Columns</p>
          <ul>${(curation.rationale?.column_notes || []).map((item) => `<li>Column ${escapeHtml(String(item.column))}: ${escapeHtml(item.note || "")}</li>`).join("")}</ul>
        </div>
        <div>
          <p class="eyebrow">Visual Watch</p>
          <ul>${(visualWarnings.length ? visualWarnings : [{ note: "No visual rhythm warnings yet." }]).slice(0, 5).map((item) => `<li>${visualWarningText(item)}</li>`).join("")}</ul>
          ${(state.strategy?.photoshoot_gaps || []).length ? `<ul>${state.strategy.photoshoot_gaps.slice(0, 2).map((item) => `<li>${visualWarningText(item)}</li>`).join("")}</ul>` : ""}
        </div>
      </div>
      ${visualWarnings.length ? `<button class="secondary compact-action" type="button" data-fix-visual-clusters>Fix Visual Clusters</button>` : ""}
      ${curatorReconstructControls()}
      <p id="feedFixStatus" class="status"></p>
    </details>
  `;
  bindCuratorControls();
}

function curatorReconstructControls() {
  return `
    <div class="curator-reconstruct">
      <textarea id="curatorDirection" placeholder="Tell the curator what to change, e.g. make left column product-led, break up black posts, put model/campaign anchors every third tile."></textarea>
      <button class="secondary compact-action" type="button" data-reconstruct-feed>Reconstruct Feed</button>
    </div>
  `;
}

function bindCuratorControls() {
  feedCuration.querySelector("[data-fix-visual-clusters]")?.addEventListener("click", () => curateFeed("visual_warnings"));
  feedCuration.querySelector("[data-reconstruct-feed]")?.addEventListener("click", () => {
    const direction = feedCuration.querySelector("#curatorDirection")?.value || "";
    curateFeed("user_direction", direction);
  });
}

function sortedFeedItems() {
  return state.calendar.slice().sort((a, b) => {
    const aPosition = Number.isFinite(a.feed_position) ? a.feed_position : 999;
    const bPosition = Number.isFinite(b.feed_position) ? b.feed_position : 999;
    if (aPosition !== bPosition) return aPosition - bPosition;
    return (a.scheduled_date || "").localeCompare(b.scheduled_date || "");
  });
}

async function reorderFeed(draggedId, targetId) {
  if (!draggedId || draggedId === targetId) return;
  const ordered = sortedFeedItems().map((item) => item.id);
  const from = ordered.indexOf(draggedId);
  const to = ordered.indexOf(targetId);
  if (from < 0 || to < 0) return;
  ordered.splice(from, 1);
  ordered.splice(to, 0, draggedId);
  const response = await fetch("/api/feed/reorder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ordered_ids: ordered }),
  });
  if (!response.ok) return;
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.curation = data.curation || state.curation;
  state.selectedCalendarItem = state.calendar.find((item) => item.id === state.selectedCalendarItem?.id) || null;
  renderFeed();
  renderCalendar();
  renderBuilder();
}

async function curateFeed(focus = "general", direction = "") {
  const button = document.getElementById("curateFeed");
  const fixStatus = document.getElementById("feedFixStatus");
  if (button) {
    button.disabled = true;
    button.textContent = focus === "visual_warnings" ? "Fixing..." : "Curating...";
  }
  if (fixStatus) fixStatus.textContent = focus === "visual_warnings" ? "Asking curator to break up visual clusters..." : "";
  const response = await fetch("/api/feed/curate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ focus, direction }),
  });
  if (button) {
    button.disabled = false;
    button.textContent = "Curate Feed";
  }
  if (!response.ok) return;
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.curation = data.curation || null;
  state.selectedCalendarItem = state.calendar.find((item) => item.id === state.selectedCalendarItem?.id) || null;
  renderFeed();
  renderCalendar();
  renderBuilder();
  if (focus === "visual_warnings") {
    const updatedStatus = document.getElementById("feedFixStatus");
    if (updatedStatus) updatedStatus.textContent = "Curator reordered the grid using visual warnings.";
  }
}

function renderStrategy() {
  if (!calendarStrategy || !state.strategy) return;
  const duplicateWarnings = state.strategy.duplicate_warnings || [];
  const visualWarnings = state.strategy.visual_warnings || [];
  const feedRoleWarnings = state.strategy.feed_role_warnings || [];
  const visualSurfaceWarnings = state.strategy.visual_surface_warnings || [];
  const productAccuracyWarnings = state.strategy.product_accuracy_warnings || [];
  const photoshootGaps = state.strategy.photoshoot_gaps || [];
  const needsWork = state.strategy.needs_work || [];
  const rowObjectives = state.strategy.row_objectives || [];
  const quality = state.strategy.quality_summary || {};
  calendarStrategy.innerHTML = `
    <details class="strategy-disclosure">
      <summary>
        <span>Calendar Strategy</span>
        <strong>${escapeHtml(state.strategy.rhythm || "Open strategy notes")}</strong>
      </summary>
      <div class="strategy-detail-grid">
        <div>
          <p class="eyebrow">Mood</p>
          <p>${escapeHtml(state.strategy.mood)}</p>
        </div>
        <div>
          <p class="eyebrow">Rhythm</p>
          <p>${escapeHtml(state.strategy.rhythm)}</p>
        </div>
        <div>
          <p class="eyebrow">Guidance</p>
          <ul>${state.strategy.guidance.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
        <div>
          <p class="eyebrow">Product Rotation</p>
          <p>${escapeHtml(state.strategy.product_rotation || "No product rotation data yet.")}</p>
        </div>
        <div>
          <p class="eyebrow">Performance Learning</p>
          <p>${escapeHtml(state.strategy.performance?.headline || "No posted performance records yet.")}</p>
        </div>
        <div>
          <p class="eyebrow">Quality</p>
          <p>Average ${escapeHtml(String(quality.average || 0))} / Ready ${escapeHtml(String(quality.ready || 0))} / Needs work ${escapeHtml(String(quality.needs_work || 0))}</p>
        </div>
        ${rowObjectives.length ? `
          <div class="duplicate-panel">
            <p class="eyebrow">Row Objectives</p>
            <ul>${rowObjectives.slice(0, 6).map((item) => `<li>Row ${escapeHtml(String(item.row))}: ${escapeHtml(item.objective || "")}</li>`).join("")}</ul>
          </div>
        ` : ""}
        ${needsWork.length ? `
          <div class="duplicate-panel">
            <p class="eyebrow">Needs Work Queue</p>
            <ul>${needsWork.slice(0, 8).map((item) => `<li>${escapeHtml(item.hook || item.id)} / Q${escapeHtml(String(item.score || 0))}: ${escapeHtml((item.reasons || []).map((reason) => reason.type).join(", "))}</li>`).join("")}</ul>
          </div>
        ` : ""}
        ${duplicateWarnings.length ? `
          <div class="duplicate-panel">
            <p class="eyebrow">Duplicate Watch</p>
            <ul>${duplicateWarnings.slice(0, 6).map((item) => `<li>${escapeHtml(item.id)}: ${escapeHtml(item.note || item.status)}</li>`).join("")}</ul>
          </div>
        ` : ""}
        ${visualWarnings.length ? `
          <div class="duplicate-panel">
            <p class="eyebrow">Visual Rhythm Watch</p>
            <ul>${visualWarnings.slice(0, 6).map((item) => `<li>${visualWarningText(item)}</li>`).join("")}</ul>
          </div>
        ` : ""}
        ${feedRoleWarnings.length ? `
          <div class="duplicate-panel">
            <p class="eyebrow">Feed Role Rhythm Watch</p>
            <ul>${feedRoleWarnings.slice(0, 6).map((item) => `<li>${visualWarningText(item)}</li>`).join("")}</ul>
          </div>
        ` : ""}
        ${visualSurfaceWarnings.length ? `
          <div class="duplicate-panel">
            <p class="eyebrow">Visual Surface Watch</p>
            <ul>${visualSurfaceWarnings.slice(0, 6).map((item) => `<li>${visualWarningText(item)}</li>`).join("")}</ul>
          </div>
        ` : ""}
        ${productAccuracyWarnings.length ? `
          <div class="duplicate-panel">
            <p class="eyebrow">Product Accuracy Watch</p>
            <ul>${productAccuracyWarnings.slice(0, 6).map((item) => `<li>${visualWarningText(item)}</li>`).join("")}</ul>
          </div>
        ` : ""}
        ${photoshootGaps.length ? `
          <div class="duplicate-panel">
            <p class="eyebrow">Photoshoot Gaps</p>
            <ul>${photoshootGaps.slice(0, 4).map((item) => `<li>${visualWarningText(item)}</li>`).join("")}</ul>
          </div>
        ` : ""}
      </div>
    </details>
  `;
}

function visualWarningText(item) {
  if (typeof item === "string") return escapeHtml(item);
  const severity = item.severity ? `[${item.severity}] ` : "";
  const action = item.suggested_action ? ` Action: ${item.suggested_action}` : "";
  return escapeHtml(`${severity}${item.note || ""}${action}`);
}

function buildFormatGroups(day) {
  const groups = {
    "Solo Image Post": [],
    "Reel": [],
    "Carousel": [],
    "Video": [],
  };

  state.candidates.forEach((candidate) => {
    const key = formatGroup(candidate.format);
    groups[key].push({ type: "candidate", candidate });
  });

  day.visuals.forEach((group) => {
    const key = group.images.length > 1 ? "Carousel" : "Solo Image Post";
    groups[key].push({ type: "visualGroup", group });
  });

  day.copy
    .filter((item) => item.category !== "content_candidates")
    .filter((item) => item.category !== "content_ideas" && item.category !== "content_drafts")
    .forEach((item) => groups["Solo Image Post"].push({ type: "copy", item }));

  return groups;
}

function formatGroup(format) {
  const value = (format || "").toLowerCase();
  if (value.includes("reel")) return "Reel";
  if (value.includes("carousel") || value.includes("carrousel")) return "Carousel";
  if (value.includes("video")) return "Video";
  return "Solo Image Post";
}

function renderReports() {
  reportList.innerHTML = "";
  const day = state.selectedDay;
  if (!day || !day.reports.length) {
    reportList.innerHTML = '<div class="empty-note">No reports for this day.</div>';
    return;
  }

  day.reports.forEach((item) => {
    const button = document.createElement("button");
    button.className = `report-button ${state.selectedItem?.path === item.path ? "active" : ""}`;
    button.innerHTML = `<strong>${reportLabel(item)}</strong><span>${item.name}</span>`;
    button.addEventListener("click", () => selectItem(item));
    reportList.appendChild(button);
  });
}

function renderVisualArchive() {
  if (!visualArchive) return;
  renderAiVisualArchive();
  const groups = [];
  state.days.forEach((day) => {
    (day.visuals || []).forEach((group) => groups.push({ day: day.date, group }));
  });
  if (!groups.length) {
    visualArchive.innerHTML = '<div class="empty-note">No generated visuals yet.</div>';
    return;
  }
  visualArchive.innerHTML = groups.map(({ day, group }) => `
    <section class="visual-archive-group">
      <div>
        <p class="eyebrow">${escapeHtml(day)}</p>
        <h3>${escapeHtml(titleize(group.name))}</h3>
      </div>
      <div class="visual-archive-grid">
        ${(group.images || []).map((item) => `
          <button class="thumb" type="button" data-path="${escapeForAttribute(item.path)}">
            <img src="/media?path=${encodeURIComponent(item.path)}" alt="${escapeHtml(item.name)}" loading="lazy" />
            <span>${escapeHtml(item.name)}</span>
          </button>
        `).join("")}
      </div>
    </section>
  `).join("");
  visualArchive.querySelectorAll("[data-path]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = findOutputByPath(button.dataset.path);
      if (item) selectItem(item);
    });
  });
}

function renderAiVisualArchive() {
  if (!aiVisualArchive) return;
  const attachedConcepts = state.calendar.flatMap((item) =>
    (item.ai_visual_concepts || [])
      .filter((concept) => concept.image_path)
      .map((concept) => ({ item, concept, imagePath: concept.image_path, title: item.hook || "AI visual" }))
  );
  const attachedPaths = new Set(attachedConcepts.map((entry) => entry.imagePath));
  const archiveConcepts = state.days.flatMap((day) =>
    (day.all_outputs || [])
      .filter((output) => output.category === "image_concepts" && output.kind === "image" && !attachedPaths.has(output.path))
      .map((output) => ({ item: null, concept: { concept_type: "image_concept" }, imagePath: output.path, title: output.name }))
  );
  const concepts = [...attachedConcepts, ...archiveConcepts];
  if (!concepts.length) {
    aiVisualArchive.innerHTML = '<div class="empty-note">No AI-generated post concepts yet.</div>';
    return;
  }
  aiVisualArchive.innerHTML = `
    <section class="visual-archive-group">
      <div>
        <p class="eyebrow">AI Generated</p>
        <h3>Post image concepts</h3>
      </div>
      <div class="ai-concept-grid">
        ${concepts.map(({ item, concept, imagePath, title }) => `
          <button class="ai-concept-card" type="button"
            data-image-path="${escapeForAttribute(imagePath)}"
            data-item-id="${escapeForAttribute(item?.id || "")}"
            data-concept-type="${escapeForAttribute(concept.concept_type || "model_shoot")}">
            <img src="/media?path=${encodeURIComponent(imagePath)}" alt="${escapeHtml(title)}" loading="lazy" />
            <span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(titleize(concept.concept_type || "visual concept"))}</small></span>
          </button>
        `).join("")}
      </div>
    </section>
  `;
  aiVisualArchive.querySelectorAll("[data-image-path]").forEach((button) => {
    button.addEventListener("click", () => openImageModal({
      imagePath: button.dataset.imagePath,
      itemId: button.dataset.itemId,
      conceptType: button.dataset.conceptType,
      title: button.innerText,
    }));
  });
}

function generatedImageButton(imagePath, itemId = "", conceptType = "generated_image", label = "Open Generated Image") {
  if (!imagePath) return "";
  return `
    <button class="inline-mini-button generated-image-button" type="button"
      data-open-generated-image="${escapeForAttribute(imagePath)}"
      data-open-generated-item="${escapeForAttribute(itemId)}"
      data-open-generated-concept="${escapeForAttribute(conceptType)}">
      ${escapeHtml(label)}
    </button>
  `;
}

function bindGeneratedImageButtons(root = document) {
  root.querySelectorAll("[data-open-generated-image]").forEach((button) => {
    button.addEventListener("click", () => openImageModal({
      imagePath: button.dataset.openGeneratedImage,
      itemId: button.dataset.openGeneratedItem || "",
      conceptType: button.dataset.openGeneratedConcept || "generated_image",
      title: "Generated image",
    }));
  });
}

function findOutputByPath(path) {
  for (const day of state.days) {
    const found = (day.all_outputs || []).find((item) => item.path === path);
    if (found) return found;
  }
  return null;
}

function imageButton(item) {
  const button = document.createElement("button");
  button.className = `thumb ${state.selectedItem?.path === item.path ? "active" : ""}`;
  button.innerHTML = `<img src="/media?path=${encodeURIComponent(item.path)}" alt="${item.name}" /><span>${item.name}</span>`;
  button.addEventListener("click", () => selectItem(item));
  return button;
}

function textButton(item) {
  const button = document.createElement("button");
  button.className = `copy-button ${state.selectedItem?.path === item.path ? "active" : ""}`;
  button.innerHTML = `<strong>${reportLabel(item)}</strong><span>${item.name}</span>`;
  button.addEventListener("click", () => selectItem(item));
  return button;
}

function candidateButton(candidate) {
  const button = document.createElement("button");
  button.className = `candidate-card ${state.selectedCandidate?.index === candidate.index ? "active" : ""}`;
  const previews = candidateSourceAssets(candidate).slice(0, 3);
  button.innerHTML = `
    <div class="candidate-previews">
      ${previews.map((asset) => assetThumb(asset)).join("") || '<div class="asset-placeholder">No preview</div>'}
    </div>
    <div class="candidate-card-head">
      <strong>${escapeHtml(candidate.hook || candidate.title)}</strong>
      <span>${escapeHtml(candidate.format || "Draft")}</span>
    </div>
    <p>${escapeHtml(candidate.pillar || "General")}</p>
    <small>${candidate.source_files.length} source file${candidate.source_files.length === 1 ? "" : "s"}</small>
  `;
  button.addEventListener("click", () => selectCandidate(candidate));
  return button;
}

function visualGroupButton(group, label) {
  const wrapper = document.createElement("div");
  wrapper.className = "visual-group-card";
  wrapper.innerHTML = `<div><strong>${titleize(group.name)}</strong><span>${label} / ${group.images.length} slide${group.images.length === 1 ? "" : "s"}</span></div>`;
  const row = document.createElement("div");
  row.className = "mini-slide-row";
  group.images.forEach((item) => row.appendChild(imageButton(item)));
  wrapper.appendChild(row);
  return wrapper;
}

function selectCandidate(candidate) {
  state.selectedCandidate = candidate;
  state.selectedItem = null;
  clearSelection();
  renderPosts();
  renderWorkspace();
}

function renderActionChecklists() {
  renderActionChecklist(seoChecklist, state.actionChecklists?.seo, "SEO");
  renderActionChecklist(adsChecklist, state.actionChecklists?.ads, "Ads");
}

function renderPerformance() {
  if (!performanceSummary || !performanceList) return;
  const summary = state.performance?.summary || {};
  performanceSummary.innerHTML = `
    <div>
      <p class="eyebrow">Learning Summary</p>
      <p>${escapeHtml(summary.headline || "No posted performance records yet.")}</p>
    </div>
    <div>
      <p class="eyebrow">Learning Notes</p>
      <ul>${(summary.learning_notes || ["Add a posted URL and first metrics after publishing."]).map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>
    </div>
    <div>
      <p class="eyebrow">Top Posts</p>
      <ul>${(summary.top_posts || []).slice(0, 5).map((post) => `<li>${escapeHtml(post.hook || post.id)} / score ${escapeHtml(String(post.score || 0))}</li>`).join("") || "<li>No measured posts yet.</li>"}</ul>
    </div>
  `;

  const recordsByPost = new Map((state.performance?.records || []).map((record) => [record.post_id, record]));
  const items = sortedFeedItems();
  if (!items.length) {
    performanceList.innerHTML = '<div class="empty-note">Schedule or approve posts first, then log performance here after publishing.</div>';
    return;
  }
  performanceList.innerHTML = items.map((item) => performanceCard(item, recordsByPost.get(item.id) || {})).join("");
  bindPerformanceControls();
}

function renderCampaignMemory() {
  if (!campaignMemoryPanel) return;
  const memory = state.campaignMemory?.memory || {};
  const rows = [
    ["Campaign Focus", memory.campaign_focus],
    ["Active Narrative", memory.active_narrative],
    ["Feed Objective", memory.feed_objective],
    ["Summary", memory.summary],
  ];
  campaignMemoryPanel.innerHTML = `
    <section class="campaign-memory-card">
      <div class="campaign-memory-head">
        <div>
          <p class="eyebrow">Campaign Operating Brief</p>
          <h4>${escapeHtml(memory.campaign_focus || "Current campaign")}</h4>
        </div>
        <span>${escapeHtml((state.campaignMemory?.revisions || [])[0]?.updated_at || "Not refreshed yet")}</span>
      </div>
      <div class="campaign-memory-grid">
        ${rows.map(([label, value]) => `
          <div><p class="eyebrow">${escapeHtml(label)}</p><p>${escapeHtml(value || "Not specified")}</p></div>
        `).join("")}
        ${campaignMemoryList("Product Priorities", memory.product_priorities)}
        ${campaignMemoryList("Visual Needs", memory.visual_needs)}
        ${campaignMemoryList("Calendar Commitments", memory.calendar_commitments)}
        ${campaignMemoryList("Shoot Gaps", memory.shoot_gaps)}
        ${campaignMemoryList("Avoid", memory.avoid_list)}
      </div>
    </section>
  `;
  bindCampaignMemoryActions();
}

function campaignMemoryList(label, items = []) {
  const canGenerate = label === "Visual Needs" || label === "Shoot Gaps";
  return `
    <div>
      <p class="eyebrow">${escapeHtml(label)}</p>
      <ul>${(items || []).slice(0, 5).map((item) => `
        <li>
          <span>${escapeHtml(item)}</span>
          ${canGenerate ? `<button class="inline-mini-button" type="button" data-generate-visual-need="${escapeForAttribute(item)}">Generate reference</button>` : ""}
        </li>
      `).join("") || "<li>Not specified</li>"}</ul>
    </div>
  `;
}

function bindCampaignMemoryActions() {
  campaignMemoryPanel?.querySelectorAll("[data-generate-visual-need]").forEach((button) => {
    button.addEventListener("click", () => generateVisualNeedReference(button));
  });
}

async function generateVisualNeedReference(button) {
  const need = button.dataset.generateVisualNeed || "";
  button.disabled = true;
  const originalText = button.textContent;
  button.textContent = "Generating...";
  const response = await fetch("/api/visual-needs/reference-image", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ need }),
  });
  button.disabled = false;
  button.textContent = response.ok ? "Generated" : "Try again";
  window.setTimeout(() => {
    button.textContent = originalText;
  }, 2400);
  if (!response.ok) return;
  const data = await response.json();
  const holder = document.createElement("div");
  holder.className = "generated-open-slot";
  holder.innerHTML = generatedImageButton(data.concept?.image_path || "", "", "curator_process_reference", "Open Generated Image");
  if (data.concept?.image_path) {
    button.insertAdjacentElement("afterend", holder);
    bindGeneratedImageButtons(holder);
  }
  if (data.concept?.image_path) {
    openImageModal({ imagePath: data.concept.image_path, title: "Curator visual reference", conceptType: "curator_process_reference" });
  }
}

async function refreshCampaignMemory() {
  if (!refreshCampaignMemoryButton) return;
  refreshCampaignMemoryButton.disabled = true;
  refreshCampaignMemoryButton.textContent = "Refreshing...";
  const response = await fetch("/api/campaign-memory/refresh", { method: "POST" });
  refreshCampaignMemoryButton.disabled = false;
  refreshCampaignMemoryButton.textContent = "Refresh Campaign Memory";
  if (!response.ok) return;
  state.campaignMemory = await response.json();
  renderCampaignMemory();
}

function performanceCard(item, record) {
  const metrics = record.metrics || {};
  const firstAsset = calendarItemAssets(item)[0];
  return `
    <article class="performance-card" data-performance-item="${escapeForAttribute(item.id)}">
      <div class="performance-media">${firstAsset ? assetThumb(firstAsset) : calendarVisualThumb(item)}</div>
      <div class="performance-fields">
        <div>
          <p class="eyebrow">${escapeHtml(item.format || "Post")}</p>
          <h4>${escapeHtml(item.hook || item.id)}</h4>
          <span>${escapeHtml(item.scheduled_date || "")} / ${escapeHtml((item.product_keys || []).join(", ") || "No product mapped")}</span>
        </div>
        <div class="performance-grid">
          <label>Platform<input data-performance-field="platform" value="${escapeForAttribute(record.platform || "Instagram")}" /></label>
          <label>Post URL<input data-performance-field="post_url" value="${escapeForAttribute(record.post_url || "")}" placeholder="https://..." /></label>
          <label>Posted Date<input data-performance-field="posted_date" type="date" value="${escapeForAttribute(record.posted_date || item.scheduled_date || "")}" /></label>
          ${["reach", "saves", "shares", "follows", "profile_visits", "clicks", "orders"].map((field) => `
            <label>${escapeHtml(titleize(field))}<input data-performance-metric="${field}" type="number" min="0" value="${escapeForAttribute(metrics[field] || 0)}" /></label>
          `).join("")}
        </div>
        <textarea data-performance-field="notes" placeholder="What worked, what felt off, what to repeat or avoid">${escapeHtml(record.notes || "")}</textarea>
        <div class="action-buttons">
          <button class="secondary" type="button" data-save-performance>Save Metrics</button>
          ${stateControls("post", item.id, item.status || "Draft", item.hook || item.id, "performance-state-actions")}
        </div>
        <p class="status" data-performance-status></p>
      </div>
    </article>
  `;
}

function bindPerformanceControls() {
  performanceList.querySelectorAll("[data-save-performance]").forEach((button) => {
    button.addEventListener("click", () => savePerformanceRecord(button.closest("[data-performance-item]")));
  });
  bindStateControls(performanceList);
}

async function savePerformanceRecord(card) {
  if (!card) return;
  const item = state.calendar.find((entry) => entry.id === card.dataset.performanceItem);
  if (!item) return;
  const status = card.querySelector("[data-performance-status]");
  if (status) status.textContent = "Saving performance record...";
  const metrics = {};
  card.querySelectorAll("[data-performance-metric]").forEach((input) => {
    metrics[input.dataset.performanceMetric] = Number(input.value || 0);
  });
  const fieldValue = (name) => card.querySelector(`[data-performance-field="${name}"]`)?.value || "";
  const response = await fetch("/api/performance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      post_id: item.id,
      platform: fieldValue("platform"),
      post_url: fieldValue("post_url"),
      posted_date: fieldValue("posted_date"),
      format: item.format || "",
      assets: calendarItemAssets(item).map((asset) => asset.name),
      product_family: (item.product_keys || [])[0] || "",
      caption: item.caption || "",
      hook: item.hook || "",
      notes: fieldValue("notes"),
      metrics,
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not save performance record.";
    return;
  }
  const data = await response.json();
  state.performance = { records: data.records || [], summary: data.summary || null };
  state.contentStates = data.states || state.contentStates;
  await loadCalendar();
  renderDashboard();
}

function renderCreativeBrief() {
  if (!creativeBriefEditor) return;
  const brief = state.creativeBrief?.brief || {};
  const fields = [
    ["current_drop_focus", "Current Drop Focus"],
    ["products_to_push", "Products To Push"],
    ["products_to_pause", "Products To Pause"],
    ["tone", "Tone"],
    ["visual_references", "Visual References"],
    ["avoid_list", "Avoid List"],
    ["seasonal_direction", "Seasonal Direction"],
  ];
  creativeBriefEditor.innerHTML = `
    <section class="creative-brief-card">
      <div class="creative-brief-grid">
        ${fields.map(([key, label]) => `
          <label>
            ${escapeHtml(label)}
            <textarea data-brief-field="${key}" placeholder="${escapeForAttribute(label)}">${escapeHtml(brief[key] || "")}</textarea>
          </label>
        `).join("")}
      </div>
      <label class="revision-note">
        Revision Note
        <input data-brief-note placeholder="What changed and why?" />
      </label>
      <div class="action-buttons">
        <button class="secondary" type="button" data-save-creative-brief>Save Direction</button>
      </div>
      <p class="status" data-brief-status></p>
    </section>
    <section class="creative-brief-card">
      <p class="eyebrow">Revision History</p>
      ${(state.creativeBrief?.revisions || []).slice(0, 8).map((revision) => `
        <div class="revision-row">
          <strong>${escapeHtml(revision.updated_at || "")}</strong>
          <span>${escapeHtml(revision.note || "No note")}</span>
        </div>
      `).join("") || '<div class="empty-note">No revisions yet.</div>'}
    </section>
  `;
  creativeBriefEditor.querySelector("[data-save-creative-brief]")?.addEventListener("click", saveCreativeBrief);
}

async function saveCreativeBrief() {
  const brief = {};
  creativeBriefEditor.querySelectorAll("[data-brief-field]").forEach((field) => {
    brief[field.dataset.briefField] = field.value;
  });
  const status = creativeBriefEditor.querySelector("[data-brief-status]");
  if (status) status.textContent = "Saving creative direction...";
  const response = await fetch("/api/creative-brief", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brief, note: creativeBriefEditor.querySelector("[data-brief-note]")?.value || "" }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not save creative direction.";
    return;
  }
  state.creativeBrief = await response.json();
  renderCreativeBrief();
}

function renderShootPlan() {
  if (!shootPlan) return;
  const plan = state.shootPlan || {};
  shootPlan.innerHTML = `
    <section class="shoot-summary">
      <p>${escapeHtml(plan.summary || "No shot list yet.")}</p>
      <div class="shoot-signals">
        ${(plan.signals?.photoshoot_gaps || []).slice(0, 2).map((item) => `<span>${visualWarningText(item)}</span>`).join("")}
        ${(plan.signals?.highlight_needs || []).slice(0, 3).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
      </div>
    </section>
    ${shootPlanSection("Must Shoot", plan.must_shoot || [])}
    ${shootPlanSection("Nice To Have", plan.nice_to_have || [])}
    ${shootPlanSection("Optional", plan.optional || [])}
  `;
  bindShootReferenceActions();
}

function shootPlanSection(title, items) {
  return `
    <section class="shoot-section">
      <p class="eyebrow">${escapeHtml(title)}</p>
      <div class="shoot-grid">
        ${items.map((item) => shootCard(item)).join("") || '<div class="empty-note">No requests in this priority yet.</div>'}
      </div>
    </section>
  `;
}

function shootCard(item) {
  return `
    <article class="shoot-card" data-shoot-brief="${escapeForAttribute(JSON.stringify(item))}">
      <strong>${escapeHtml(item.product || "Shot request")}</strong>
      <dl>
        <dt>Angle</dt><dd>${escapeHtml(item.angle || "")}</dd>
        <dt>Crop</dt><dd>${escapeHtml(item.crop || "")}</dd>
        <dt>Mood</dt><dd>${escapeHtml(item.mood || "")}</dd>
        <dt>Background</dt><dd>${escapeHtml(item.background || "")}</dd>
        <dt>Lighting</dt><dd>${escapeHtml(item.lighting || "")}</dd>
        <dt>Use</dt><dd>${escapeHtml(item.use_case || "")}</dd>
      </dl>
      <p>${escapeHtml(item.solves || "")}</p>
      <button class="secondary compact-action" type="button" data-generate-shoot-reference>Generate Reference Image</button>
      <button class="secondary compact-action" type="button" data-add-shoot-placeholder>Add Calendar Placeholder</button>
      <p class="status" data-shoot-reference-status></p>
    </article>
  `;
}

function bindShootReferenceActions() {
  shootPlan.querySelectorAll("[data-generate-shoot-reference]").forEach((button) => {
    button.addEventListener("click", () => generateShootReference(button.closest("[data-shoot-brief]")));
  });
  shootPlan.querySelectorAll("[data-add-shoot-placeholder]").forEach((button) => {
    button.addEventListener("click", () => addShootPlaceholder(button.closest("[data-shoot-brief]")));
  });
}

async function addShootPlaceholder(card) {
  if (!card) return;
  const status = card.querySelector("[data-shoot-reference-status]");
  let brief = {};
  try {
    brief = JSON.parse(card.dataset.shootBrief || "{}");
  } catch {
    brief = {};
  }
  if (status) status.textContent = "Adding calendar placeholder...";
  const response = await fetch("/api/shoot-plan/calendar-placeholder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      brief: Object.entries(brief).map(([key, value]) => `${titleize(key)}: ${value}`).join("\n"),
      priority: brief.priority || "shoot_gap",
      direction: brief.solves || "",
      request: brief,
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not add placeholder.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || state.calendar;
  state.strategy = data.strategy || state.strategy;
  if (status) status.textContent = "Placeholder added to calendar.";
  renderCalendar();
  renderFeed();
}

async function generateShootReference(card) {
  if (!card) return;
  const status = card.querySelector("[data-shoot-reference-status]");
  if (status) status.textContent = "Generating AI reference image...";
  let brief = {};
  try {
    brief = JSON.parse(card.dataset.shootBrief || "{}");
  } catch {
    brief = {};
  }
  const response = await fetch("/api/shoot-plan/reference-image", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      brief: Object.entries(brief).map(([key, value]) => `${titleize(key)}: ${value}`).join("\n"),
      priority: brief.priority || "shoot_gap",
      direction: brief.solves || "",
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Reference generation failed. Check API key/image settings.";
    return;
  }
  const data = await response.json();
  if (status) {
    status.innerHTML = `Reference image generated. ${generatedImageButton(data.concept?.image_path || "", "", data.concept?.concept_type || "shoot_reference", "Open Generated Image")}`;
    bindGeneratedImageButtons(status);
  }
  if (data.concept?.image_path) {
    openImageModal({ imagePath: data.concept.image_path, title: "Shoot reference image", conceptType: "shoot_reference" });
  }
}

function renderMerchandising() {
  if (!merchandisingPlan) return;
  const plan = state.merchandising || {};
  merchandisingPlan.innerHTML = `
    <section class="shoot-summary">
      <p>${escapeHtml(plan.summary || "No merchandising plan yet.")}</p>
      <div class="shoot-signals">
        ${(plan.warnings || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
      </div>
      ${shopifyStatusPanel(plan.shopify_status || {})}
    </section>
    <section class="merch-grid">
      ${(plan.recommendations || []).map((item) => merchandisingCard(item)).join("") || '<div class="empty-note">No product recommendations yet.</div>'}
    </section>
    <section class="creative-brief-card">
      <p class="eyebrow">Shopify Product Preview</p>
      <div class="merch-products">
        ${(plan.shopify_products || []).map((item) => `
          <div>
            <strong>${escapeHtml(item.title || "Product")}</strong>
            <span>${escapeHtml(item.handle || "")} / ${escapeHtml(String(item.image_count || 0))} images</span>
          </div>
        `).join("") || '<div class="empty-note">Connect Shopify for read-only product preview.</div>'}
      </div>
    </section>
  `;
}

function merchandisingCard(item) {
  return `
    <article class="merch-card ${escapeForAttribute((item.priority || "").toLowerCase())}">
      <p class="eyebrow">${escapeHtml(item.priority || "Review")}</p>
      <strong>${escapeHtml(item.product || "Product")}</strong>
      <p>${escapeHtml(item.reason || "")}</p>
      <span>${escapeHtml(item.next_action || "")}</span>
      <small>Drive assets: ${escapeHtml(String(item.asset_count || 0))} / Calendar: ${escapeHtml(String(item.calendar_count || 0))} / Performance: ${escapeHtml(String(item.performance_count || 0))}</small>
    </article>
  `;
}

function renderLaunchPlan() {
  if (!launchPlan) return;
  const plan = state.launchPlan || {};
  const readiness = plan.readiness || {};
  launchPlan.innerHTML = `
    <section class="shoot-summary">
      <p>${escapeHtml(plan.summary || "No launch plan yet.")}</p>
      <div class="launch-readiness">
        ${Object.entries(readiness).map(([key, value]) => `<span><strong>${escapeHtml(String(value))}</strong>${escapeHtml(titleize(key))}</span>`).join("")}
      </div>
      <div class="shoot-signals">
        ${(plan.blockers || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
      </div>
    </section>
    <section class="launch-sequence">
      ${(plan.sequence || []).map((step) => launchStep(step)).join("")}
    </section>
  `;
}

function launchStep(step) {
  return `
    <article class="launch-step">
      <div>
        <p class="eyebrow">${escapeHtml(step.stage || "Stage")}</p>
        <strong>${escapeHtml(step.purpose || "")}</strong>
      </div>
      <div class="launch-step-items">
        ${(step.items || []).map((item) => `
          <button type="button" data-launch-item="${escapeForAttribute(item.id)}">
            <strong>${escapeHtml(item.title || item.id || "Item")}</strong>
            <span>${escapeHtml(item.format || "Item")} / ${escapeHtml(item.status || "Draft")} ${item.date ? `/ ${escapeHtml(item.date)}` : ""}</span>
          </button>
        `).join("") || '<div class="empty-note">No matching item yet.</div>'}
      </div>
    </article>
  `;
}

function renderCommunityFaq() {
  if (!communityFaq) return;
  const faq = state.communityFaq || {};
  communityFaq.innerHTML = `
    <section class="shoot-summary"><p>${escapeHtml(faq.summary || "No FAQ plan yet.")}</p></section>
    <section class="merch-grid">
      ${(faq.replies || []).map((item) => `
        <article class="merch-card">
          <p class="eyebrow">${escapeHtml(item.category || "FAQ")}</p>
          <strong>${escapeHtml(item.question || "")}</strong>
          <p>${escapeHtml(item.reply || "")}</p>
        </article>
      `).join("")}
    </section>
    <section class="creative-brief-card">
      <p class="eyebrow">Story Prompts</p>
      <div class="shoot-signals">${(faq.story_prompts || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
    </section>
    <section class="creative-brief-card">
      <p class="eyebrow">Highlight Suggestions</p>
      <div class="merch-products">${(faq.highlight_suggestions || []).map((item) => `
        <div><strong>${escapeHtml(item.title || "")}</strong><span>${escapeHtml((item.frames || []).join(" / "))}</span></div>
      `).join("")}</div>
    </section>
  `;
}

function renderOwnedPlan() {
  if (!ownedPlan) return;
  const plan = state.ownedPlan || {};
  ownedPlan.innerHTML = `
    <section class="shoot-summary"><p>${escapeHtml(plan.summary || "No owned-channel plan yet.")}</p></section>
    <section class="merch-grid">
      <article class="merch-card"><p class="eyebrow">Subject Lines</p>${(plan.subject_lines || []).map((item) => `<p>${escapeHtml(item)}</p>`).join("")}</article>
      <article class="merch-card"><p class="eyebrow">Preview Text</p>${(plan.preview_text || []).map((item) => `<p>${escapeHtml(item)}</p>`).join("")}</article>
      <article class="merch-card"><p class="eyebrow">SMS Drafts</p>${(plan.sms_drafts || []).map((item) => `<p>${escapeHtml(item)}</p>`).join("")}</article>
    </section>
    <section class="launch-sequence">
      ${(plan.email_sections || []).map((section) => `
        <article class="launch-step">
          <div><p class="eyebrow">${escapeHtml(section.title || "Section")}</p></div>
          <p>${escapeHtml(section.copy || "")}</p>
        </article>
      `).join("")}
    </section>
  `;
}

function renderAutomation() {
  if (!automationPanel) return;
  const config = state.automation?.config || {};
  const presets = state.automation?.presets || [];
  automationPanel.innerHTML = `
    <section class="creative-brief-card">
      <div class="performance-grid">
        <label>Preset
          <select data-automation-preset>
            ${presets.map((preset) => `<option value="${escapeForAttribute(preset.id)}" ${preset.id === config.preset ? "selected" : ""}>${escapeHtml(preset.label)}</option>`).join("")}
          </select>
        </label>
        <label>Enabled
          <select data-automation-enabled>
            <option value="false" ${!config.enabled ? "selected" : ""}>No</option>
            <option value="true" ${config.enabled ? "selected" : ""}>Yes</option>
          </select>
        </label>
        <label>Review Required
          <select data-automation-review>
            <option value="true" ${config.review_required !== false ? "selected" : ""}>Yes</option>
            <option value="false" ${config.review_required === false ? "selected" : ""}>No</option>
          </select>
        </label>
      </div>
      <textarea data-automation-notes placeholder="Automation notes">${escapeHtml(config.notes || "")}</textarea>
      <div class="action-buttons"><button class="secondary" type="button" data-save-automation>Save Automation</button></div>
      <p class="status" data-automation-status>External changes remain ${escapeHtml(config.external_changes || "approval-gated")}.</p>
    </section>
    <section class="creative-brief-card">
      <p class="eyebrow">Automation Logs</p>
      ${(state.automation?.logs || []).map((log) => `
        <div class="revision-row"><strong>${escapeHtml(log.created_at || "")}</strong><span>${escapeHtml(log.event_type || "")}</span></div>
      `).join("") || '<div class="empty-note">No automation logs yet.</div>'}
    </section>
  `;
  automationPanel.querySelector("[data-save-automation]")?.addEventListener("click", saveAutomation);
}

async function saveAutomation() {
  const status = automationPanel.querySelector("[data-automation-status]");
  if (status) status.textContent = "Saving automation schedule...";
  const response = await fetch("/api/automation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preset: automationPanel.querySelector("[data-automation-preset]")?.value || "manual",
      enabled: automationPanel.querySelector("[data-automation-enabled]")?.value === "true",
      review_required: automationPanel.querySelector("[data-automation-review]")?.value !== "false",
      notes: automationPanel.querySelector("[data-automation-notes]")?.value || "",
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not save automation schedule.";
    return;
  }
  state.automation = await response.json();
  renderAutomation();
}

function renderActionChecklist(container, checklist, label) {
  if (!container) return;
  const items = checklist?.items || [];
  if (!items.length) {
    container.innerHTML = `<div class="empty-note">No ${escapeHtml(label)} checklist items yet. Run agents to generate a report.</div>`;
    return;
  }
  const shopifyStatus = label === "SEO" ? checklist?.shopify_status || state.actionChecklists?.shopify_status : null;
  container.innerHTML = `
    <div class="action-source">
      <p class="eyebrow">Source</p>
      <strong>${escapeHtml(checklist.source_name || "Latest report")}</strong>
      <span>${escapeHtml(checklist.source_path || "")}</span>
      ${shopifyStatus ? shopifyStatusPanel(shopifyStatus) : ""}
      ${label === "SEO" ? `
        <div class="action-buttons">
          <button class="secondary" type="button" data-apply-approved-seo>Apply Approved SEO</button>
          <span class="status" data-shopify-apply-status>Writes require Shopify credentials and SHOPIFY_WRITE_ENABLED=true.</span>
        </div>
      ` : ""}
    </div>
    ${items.map((item) => actionChecklistItem(item, label)).join("")}
  `;
  bindStateControls(container);
  bindActionChecklistControls(container, label);
}

function actionChecklistItem(item, label) {
  const itemType = label === "SEO" ? "seo_action" : "ad_action";
  const preview = item.shopify_preview || {};
  return `
    <article class="action-item" data-action-item data-item-type="${escapeForAttribute(itemType)}" data-item-id="${escapeForAttribute(item.id)}">
      <label class="action-check">
        <input type="checkbox" />
        <span>
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(item.status || "Needs Review")} / ${escapeHtml(item.risk || "Low")} risk / ${escapeHtml(titleize(item.action_type || itemType))}</small>
        </span>
      </label>
      ${label === "SEO" ? shopifyPreviewPanel(preview) : ""}
      ${label === "Ads" ? adReadinessPanel(item.ad_readiness || {}) : ""}
      <textarea data-action-detail>${escapeHtml(item.detail || "")}</textarea>
      ${item.state_notes ? `<p class="state-note">${escapeHtml(item.state_notes)}</p>` : ""}
      ${stateControls(itemType, item.id, item.status || "Needs Review", item.title, "action-state-actions")}
      <div class="action-buttons">
        <button class="secondary" type="button" data-save-action-item>Save Changes</button>
        <button class="secondary" type="button" disabled>${label === "SEO" ? "Apply Approved Later" : "Launch Later"}</button>
        <button class="secondary" type="button" disabled>Ask Agent To Revise Later</button>
      </div>
      <p class="status" data-action-save-status></p>
    </article>
  `;
}

function adReadinessPanel(readiness) {
  const checks = readiness.checks || {};
  const checkRows = Object.entries(checks).map(([key, value]) => `
    <span class="${value ? "ready" : "missing"}">${escapeHtml(titleize(key))}</span>
  `).join("");
  return `
    <div class="ad-readiness">
      <div>
        <p class="eyebrow">Ad Readiness</p>
        <strong>${Number(readiness.score || 0)} / 100</strong>
      </div>
      <div class="readiness-checks">${checkRows}</div>
      <div class="readiness-detail">
        <span><strong>Destination:</strong> ${escapeHtml(readiness.mapped_destination || "Needs mapping")}</span>
        <span><strong>Creative:</strong> ${escapeHtml((readiness.required_creatives || []).join(" / ") || "Needs creative list")}</span>
        <span><strong>CTA:</strong> ${escapeHtml((readiness.cta_variants || []).join(" / ") || "Needs CTA variants")}</span>
        <span><strong>Copy:</strong> ${escapeHtml((readiness.copy_variants || []).slice(0, 2).join(" | ") || "Needs copy variants")}</span>
        <span>${escapeHtml(readiness.launch_note || "Launch stays locked until approved.")}</span>
      </div>
    </div>
  `;
}

function shopifyStatusPanel(status) {
  const enabled = Boolean(status.enabled);
  const missing = (status.missing || []).join(", ");
  return `
    <div class="shopify-status ${enabled ? "connected" : ""}">
      <strong>${enabled ? "Shopify read-only preview connected" : "Shopify preview not connected"}</strong>
      <span>${enabled ? `${escapeHtml(status.store_domain || "")} / ${escapeHtml(status.api_version || "")}` : `Missing: ${escapeHtml(missing || "credentials")}`}</span>
      ${status.error ? `<span>${escapeHtml(status.error)}</span>` : ""}
    </div>
  `;
}

function shopifyPreviewPanel(preview) {
  const value = preview.current_value || "";
  return `
    <div class="shopify-preview">
      <p class="eyebrow">Current Shopify Value</p>
      <strong>${escapeHtml(preview.matched_product || titleize(preview.resource_type || "SEO field"))}</strong>
      <span>${escapeHtml(preview.message || "Read-only preview will appear here once Shopify is connected.")}</span>
      <div>${value ? escapeHtml(value) : "No current value available yet."}</div>
    </div>
  `;
}

function bindActionChecklistControls(container, label) {
  container.querySelectorAll("[data-save-action-item]").forEach((button) => {
    button.addEventListener("click", () => saveActionChecklistItem(button.closest("[data-action-item]"), label));
  });
  container.querySelector("[data-apply-approved-seo]")?.addEventListener("click", applyApprovedSeo);
}

async function applyApprovedSeo() {
  const status = document.querySelector("[data-shopify-apply-status]");
  if (status) status.textContent = "Checking approved SEO actions...";
  const response = await fetch("/api/shopify/seo-actions/apply", { method: "POST" });
  if (!response.ok) {
    if (status) status.textContent = "Could not run Shopify SEO execution.";
    return;
  }
  const data = await response.json();
  const applied = (data.results || []).filter((item) => item.applied).length;
  const blocked = (data.results || []).filter((item) => item.blocked).length;
  if (status) status.textContent = `${data.approved_count || 0} approved checked. ${applied} applied. ${blocked} blocked safely.`;
  state.contentStates = data.states || state.contentStates;
  await loadActionChecklists();
  renderActionChecklists();
}

async function saveActionChecklistItem(article, label) {
  if (!article) return;
  const status = article.querySelector("[data-action-save-status]");
  if (status) status.textContent = "Saving checklist item...";
  const item = ((label === "SEO" ? state.actionChecklists?.seo?.items : state.actionChecklists?.ads?.items) || [])
    .find((entry) => entry.id === article.dataset.itemId) || {};
  const response = await fetch("/api/action-checklists/item", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      item_type: article.dataset.itemType,
      item_id: article.dataset.itemId,
      status: item.status || "Needs Review",
      title: item.title || article.dataset.itemId,
      detail: article.querySelector("[data-action-detail]")?.value || "",
      metadata: {
        action_type: item.action_type || "",
        source_path: (label === "SEO" ? state.actionChecklists?.seo?.source_path : state.actionChecklists?.ads?.source_path) || "",
      },
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not save this checklist item.";
    return;
  }
  if (status) status.textContent = "Saved.";
  await Promise.all([loadActionChecklists(), loadContentStates()]);
  renderActionChecklists();
}

function stateControls(itemType, itemId, currentStatus, title, className = "") {
  if (!itemId) return "";
  const status = currentStatus || "Draft";
  return `
    <div class="state-controls ${className}" data-state-controls>
      <span class="state-pill">${escapeHtml(status)}</span>
      <button type="button" data-state-update data-item-type="${escapeForAttribute(itemType)}" data-item-id="${escapeForAttribute(itemId)}" data-title="${escapeForAttribute(title || itemId)}" data-status="Approved">Approve</button>
      <button type="button" data-state-update data-item-type="${escapeForAttribute(itemType)}" data-item-id="${escapeForAttribute(itemId)}" data-title="${escapeForAttribute(title || itemId)}" data-status="Rejected">Reject</button>
      <button type="button" data-state-update data-item-type="${escapeForAttribute(itemType)}" data-item-id="${escapeForAttribute(itemId)}" data-title="${escapeForAttribute(title || itemId)}" data-status="Needs Review">Needs Review</button>
    </div>
  `;
}

function bindStateControls(root = document) {
  root.querySelectorAll("[data-state-update]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      updateContentState(button.dataset.itemType, button.dataset.itemId, button.dataset.status, button.dataset.title || "");
    });
  });
}

async function updateContentState(itemType, itemId, status, title = "", notes = "") {
  const response = await fetch("/api/content-state", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_type: itemType, item_id: itemId, status, title, notes }),
  });
  if (!response.ok) return;
  const data = await response.json();
  state.contentStates = data.states || state.contentStates;
  await Promise.all([loadCalendar(), loadHighlights(), loadActionChecklists()]);
  renderDashboard();
}

function renderHighlights() {
  if (!highlightGrid) return;
  if (!state.highlights.length) {
    highlightGrid.innerHTML = '<div class="empty-note">No highlights yet. Refresh highlights after adding Drive assets.</div>';
    return;
  }
  highlightGrid.innerHTML = state.highlights.map((highlight) => `
    <section class="highlight-card">
      <div class="highlight-head">
        <div>
          <p class="eyebrow">${escapeHtml(highlight.status || "Draft")}</p>
          <input class="highlight-title-input" data-highlight-title="${escapeForAttribute(highlight.id)}" value="${escapeForAttribute(highlight.title || "")}" />
          ${stateControls("highlight", highlight.id, highlight.status || "Draft", highlight.title, "highlight-state-actions")}
        </div>
        <span>${escapeHtml((highlight.frames || []).length)} frames</span>
      </div>
      <div class="highlight-cover">
        ${highlightAssetThumb(highlight.cover_asset_name)}
        <div>
          <textarea class="highlight-purpose-input" data-highlight-purpose="${escapeForAttribute(highlight.id)}">${escapeHtml(highlight.purpose || "")}</textarea>
          <p>${escapeHtml(highlight.curator_note || "")}</p>
          <div class="highlight-actions">
            <button class="secondary compact-action" type="button" data-save-highlight="${escapeForAttribute(highlight.id)}">Save Highlight</button>
            <button class="secondary compact-action" type="button" data-regenerate-highlight="${escapeForAttribute(highlight.id)}">Regenerate This</button>
            <button class="secondary compact-action" type="button" data-regenerate-cover="${escapeForAttribute(highlight.id)}">Regenerate Cover</button>
          </div>
        </div>
      </div>
      ${highlightWarnings(highlight)}
      <div class="highlight-frames">
        ${(highlight.frames || []).map((frame, index) => highlightFrameButton(highlight, frame, index)).join("")}
      </div>
      ${highlightFramePicker(highlight)}
    </section>
  `).join("");
  bindHighlightActions();
}

function highlightFrameButton(highlight, frame, index) {
  const selected = state.selectedHighlightFrame?.highlightId === highlight.id && state.selectedHighlightFrame?.frameIndex === index;
  return `
    <button class="highlight-frame ${selected ? "active" : ""}" type="button" data-highlight-id="${escapeForAttribute(highlight.id)}" data-frame-index="${index}">
      <div class="highlight-frame-media">${highlightAssetThumb(frame.asset_name)}</div>
      <strong>${escapeHtml(frame.overlay_text || `Frame ${index + 1}`)}</strong>
      <span>${escapeHtml(frame.role || "frame")} / ${escapeHtml(frame.bucket || "")}</span>
    </button>
  `;
}

function highlightFramePicker(highlight) {
  const selected = state.selectedHighlightFrame?.highlightId === highlight.id;
  if (!selected) return "";
  const frame = (highlight.frames || [])[state.selectedHighlightFrame.frameIndex] || {};
  const assets = state.rawAssets.filter((asset) => isImageAsset(asset) || isVideoAsset(asset)).slice(0, 80);
  return `
    <div class="highlight-picker">
      <p class="eyebrow">Edit Selected Frame</p>
      <div class="highlight-frame-editor">
        <label>
          Overlay Text
          <input id="highlightFrameOverlay" value="${escapeForAttribute(frame.overlay_text || "")}" />
        </label>
        <label>
          Role
          <input id="highlightFrameRole" value="${escapeForAttribute(frame.role || "")}" />
        </label>
        <button class="secondary compact-action" type="button" data-save-highlight-frame="${escapeForAttribute(highlight.id)}">Save Frame Text</button>
      </div>
      <p class="eyebrow">Swap Selected Frame</p>
      <div class="highlight-picker-grid">
        ${assets.map((asset) => `
          <button class="library-asset" type="button" data-highlight-swap="${escapeForAttribute(highlight.id)}" data-asset-name="${escapeForAttribute(asset.name)}">
            ${assetThumb(asset)}
            <span>${escapeHtml(asset.name)}</span>
          </button>
        `).join("")}
      </div>
    </div>
  `;
}

function highlightWarnings(highlight) {
  const warnings = highlight.warnings || [];
  if (!warnings.length) return '<div class="highlight-warning ok">No highlight warnings.</div>';
  return `
    <div class="highlight-warnings">
      ${warnings.map((warning) => `<div class="highlight-warning">${escapeHtml(warning.note || warning)}</div>`).join("")}
    </div>
  `;
}

function highlightAssetThumb(assetName) {
  const asset = findRawAsset(assetName);
  if (asset) return assetThumb(asset);
  return `<div class="asset-placeholder">${escapeHtml(assetName ? "FILE" : "ADD")}</div>`;
}

function bindHighlightActions() {
  highlightGrid.querySelectorAll("[data-highlight-id][data-frame-index]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedHighlightFrame = {
        highlightId: button.dataset.highlightId,
        frameIndex: Number(button.dataset.frameIndex),
      };
      renderHighlights();
    });
  });
  highlightGrid.querySelectorAll("[data-highlight-swap]").forEach((button) => {
    button.addEventListener("click", () => updateHighlightFrame(button.dataset.highlightSwap, button.dataset.assetName));
  });
  highlightGrid.querySelectorAll("[data-save-highlight-frame]").forEach((button) => {
    button.addEventListener("click", () => saveHighlightFrameText(button.dataset.saveHighlightFrame));
  });
  highlightGrid.querySelectorAll("[data-save-highlight]").forEach((button) => {
    button.addEventListener("click", () => saveHighlight(button.dataset.saveHighlight));
  });
  highlightGrid.querySelectorAll("[data-regenerate-highlight]").forEach((button) => {
    button.addEventListener("click", () => regenerateHighlight(button.dataset.regenerateHighlight));
  });
  highlightGrid.querySelectorAll("[data-regenerate-cover]").forEach((button) => {
    button.addEventListener("click", () => regenerateHighlightCover(button.dataset.regenerateCover));
  });
  bindStateControls(highlightGrid);
}

async function updateHighlightFrame(highlightId, assetName) {
  if (!state.selectedHighlightFrame || state.selectedHighlightFrame.highlightId !== highlightId) return;
  const response = await fetch(`/api/highlights/${encodeURIComponent(highlightId)}/frame`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ frame_index: state.selectedHighlightFrame.frameIndex, asset_name: assetName }),
  });
  if (!response.ok) return;
  state.highlights = (await response.json()).highlights || [];
  renderHighlights();
}

async function saveHighlightFrameText(highlightId) {
  if (!state.selectedHighlightFrame || state.selectedHighlightFrame.highlightId !== highlightId) return;
  const response = await fetch(`/api/highlights/${encodeURIComponent(highlightId)}/frame`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      frame_index: state.selectedHighlightFrame.frameIndex,
      overlay_text: document.getElementById("highlightFrameOverlay")?.value || "",
      role: document.getElementById("highlightFrameRole")?.value || "",
    }),
  });
  if (!response.ok) return;
  state.highlights = (await response.json()).highlights || [];
  renderHighlights();
}

async function saveHighlight(highlightId) {
  const response = await fetch(`/api/highlights/${encodeURIComponent(highlightId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: highlightGrid.querySelector(`[data-highlight-title="${cssEscape(highlightId)}"]`)?.value || "",
      purpose: highlightGrid.querySelector(`[data-highlight-purpose="${cssEscape(highlightId)}"]`)?.value || "",
    }),
  });
  if (!response.ok) return;
  state.highlights = (await response.json()).highlights || [];
  renderHighlights();
}

async function regenerateHighlight(highlightId) {
  const response = await fetch(`/api/highlights/${encodeURIComponent(highlightId)}/regenerate`, { method: "POST" });
  if (!response.ok) return;
  state.highlights = (await response.json()).highlights || [];
  state.selectedHighlightFrame = null;
  renderHighlights();
}

async function regenerateHighlightCover(highlightId) {
  const response = await fetch(`/api/highlights/${encodeURIComponent(highlightId)}/regenerate-cover`, { method: "POST" });
  if (!response.ok) return;
  state.highlights = (await response.json()).highlights || [];
  renderHighlights();
}

function renderBuilder() {
  if (!builderPreview || !builderWorkspace) return;
  const item = state.selectedCalendarItem;
  const candidate = state.selectedCandidate;
  if (!item) {
    builderTitle.textContent = "Select a post to build.";
    builderPreview.className = "phone-preview empty";
    builderPreview.textContent = "Choose a calendar or feed item.";
    builderWorkspace.className = "workspace empty";
    builderWorkspace.textContent = "No post selected.";
    builderAssetTray.innerHTML = "";
    builderAssetLibrary.innerHTML = "";
    builderAssetFilters.innerHTML = "";
    return;
  }

  const slots = builderSlots(item);
  if (state.builderSlotIndex >= slots.length) state.builderSlotIndex = 0;
  const activeSlot = slots[state.builderSlotIndex] || null;
  builderTitle.textContent = item.hook || candidate?.hook || candidate?.title || "Visual direction";
  builderStatus.value = item.status || "Draft";
  builderPreview.className = `phone-preview ${formatGroup(item.format).toLowerCase().replaceAll(" ", "-")}`;
  builderPreview.innerHTML = `
    <div class="phone-frame">
      <div class="phone-media">${activeSlot ? slotThumb(activeSlot) : calendarVisualThumb(item)}</div>
      <div class="phone-caption">
        ${activeSlot ? `<span class="slot-kicker">Slide ${state.builderSlotIndex + 1} / ${escapeHtml(titleize(activeSlot.role || "slot"))}</span>` : ""}
        <strong>${escapeHtml(item.hook || candidate?.hook || "")}</strong>
        <p>${formatInlineText(item.caption || candidate?.caption || "")}</p>
      </div>
    </div>
  `;
  builderWorkspace.className = "workspace";
  builderWorkspace.innerHTML = `
    ${builderPostActions(item)}
    ${builderSlotEditor(item, activeSlot)}
    ${textSlideEditor(item)}
    ${candidate ? candidateBrief(candidate) : visualItemBrief(item)}
  `;
  bindBuilderPostActions(item);
  builderAssetTray.innerHTML = slots.map((slot, index) => {
    return `
    <button class="asset-chip ${state.builderSlotIndex === index ? "active" : ""}" type="button" title="${escapeHtml(slot.name || slot.asset_name || "Slide")}" data-slot="${index}">
      ${slotThumb(slot)}
      <span>${index + 1}. ${escapeHtml(slot.name || slot.asset_name || "Slide")}</span>
    </button>
  `;
  }).join("") || '<div class="empty-note">No source assets selected.</div>';
  builderAssetTray.querySelectorAll("[data-slot]").forEach((button) => {
    button.addEventListener("click", () => {
      state.builderSlotIndex = Number(button.dataset.slot);
      renderBuilder();
    });
  });
  renderBuilderAssetLibrary();
}

function builderPostActions(item) {
  const concepts = item.ai_visual_concepts || [];
  return `
    <section class="brief-card builder-actions-card">
      <p class="eyebrow">Post Controls</p>
      <div class="builder-meta-row">
        <span>${escapeHtml(feedPositionLabel(item))}</span>
        <span>${escapeHtml(item.scheduled_date || "Unscheduled")}</span>
        <span>${escapeHtml(item.status || "Draft")}</span>
        ${item.quality_score ? `<span>Q ${escapeHtml(String(item.quality_score.overall || 0))}</span>` : ""}
      </div>
      ${(item.needs_work || []).length ? `<div class="duplicate-badge">${escapeHtml((item.needs_work || []).map((entry) => titleize(entry.type)).join(" / "))}</div>` : ""}
      <label>
        Hook
        <input id="builderHookInput" type="text" value="${escapeForAttribute(item.hook || "")}" />
      </label>
      <label>
        Caption
        <textarea id="builderCaptionInput" placeholder="Final caption">${escapeHtml(item.caption || "")}</textarea>
      </label>
      <label>
        Reviewer Notes
        <textarea id="builderReviewerNotes" placeholder="What changed, why this is moving forward, what the agents should learn.">${escapeHtml(item.reviewer_notes || "")}</textarea>
      </label>
      <div class="builder-action-row">
        <button class="secondary" type="button" data-save-post-edits>Save Post Edits</button>
        <button class="secondary" type="button" data-improve-design>Improve Design</button>
      </div>
      <p id="builderEditStatus" class="status"></p>
      ${item.calendar_note ? `<div class="duplicate-badge">${escapeHtml(item.calendar_note)}</div>` : ""}
      ${item.edit_history?.length ? briefList("Recent Changes", item.edit_history.slice(-3).map((entry) => `${entry.created_at}: ${Object.keys(entry.changes || {}).join(", ")}`)) : ""}
      ${stateControls("post", item.id, item.status || "Draft", item.hook || item.id, "builder-state-actions")}
      <label>
        AI Visual Direction
        <textarea id="visualConceptDirection" placeholder="Model wearing this product in a realistic editorial shoot, brush stroke process detail, digital file close-up, pencil/studio evidence..."></textarea>
      </label>
      <div class="builder-action-row">
        <button class="secondary" type="button" data-ai-visual="model_shoot">Generate Model Image</button>
        <button class="secondary" type="button" data-ai-visual="process_detail">Generate Process Image</button>
        <button class="mini-danger" type="button" data-remove-selected-draft>Remove Draft</button>
      </div>
      <p id="visualConceptStatus" class="status"></p>
      <div id="visualConceptOpen" class="generated-open-slot"></div>
      ${productTruthCard(item)}
      ${compositionPlanCard(item)}
      ${concepts.length ? `
        <div class="concept-links">
          ${concepts.map((concept) => `
            <button class="concept-link" type="button" data-concept-path="${escapeForAttribute(concept.image_path || concept.path)}" data-concept-kind="${concept.image_path ? "image" : "text"}">
              ${concept.image_path ? `<img src="/media?path=${encodeURIComponent(concept.image_path)}" alt="${escapeHtml(concept.concept_type || "concept")}" loading="lazy" />` : ""}
              <span><strong>${escapeHtml(titleize(concept.concept_type || "visual concept"))}</strong><small>${concept.image_path ? "Open Generated Image" : escapeHtml(shortPath(concept.path))}</small>${concept.visual_qa ? `<small>QA: ${escapeHtml(titleize(concept.visual_qa.status || "needs_review"))}</small>` : ""}</span>
            </button>
            ${concept.image_path ? `
              <div class="builder-action-row concept-actions">
                <button class="secondary" type="button" data-qa-concept="${escapeForAttribute(concept.image_path)}" data-qa-type="${escapeForAttribute(concept.concept_type || "model_shoot")}">Run Visual QA</button>
                <button class="secondary" type="button" data-iterate-qa="${escapeForAttribute(concept.image_path)}" data-qa-type="${escapeForAttribute(concept.concept_type || "model_shoot")}">Iterate With QA Fixes</button>
                ${concept.product_composite?.image_path ? `<button class="secondary" type="button" data-open-generated-image="${escapeForAttribute(concept.product_composite.image_path)}" data-open-generated-item="${escapeForAttribute(item.id)}" data-open-generated-concept="${escapeForAttribute(concept.concept_type || "model_shoot")}">Open Composite</button>` : ""}
              </div>
              ${concept.product_composite?.image_path ? `<p class="helper-text">Composite fallback created from ${escapeHtml(shortPath(concept.product_composite.reference_path || ""))}. Use it as a product-accuracy reference, not a final retouch.</p>` : ""}
              ${visualQaCard(concept.visual_qa)}
            ` : ""}
          `).join("")}
        </div>
      ` : ""}
    </section>
  `;
}

function productTruthCard(item) {
  const profiles = item.product_truth || [];
  if (!profiles.length && !item.product_reference_requirements) return "";
  return `
    <details class="composition-plan-card product-truth-card" open>
      <summary>Product Truth</summary>
      ${profiles.map((profile) => `
        <article>
          <strong>${escapeHtml(profile.display_name || profile.product_key || "Product")}</strong>
          <p>${escapeHtml(profile.silhouette || "")}</p>
          <p>${escapeHtml(profile.fabric_wash || "")}</p>
          <small>Front refs: ${escapeHtml((profile.reference_files?.front || []).slice(0, 4).join(", ") || "none")}</small>
          <small>Back refs: ${escapeHtml((profile.reference_files?.back || []).slice(0, 4).join(", ") || "none")}</small>
          ${profile.front_graphic_policy ? `<small>Front policy: ${escapeHtml(titleize(profile.front_graphic_policy))}</small>` : ""}
          ${profile.back_graphic_policy ? `<small>Back policy: ${escapeHtml(titleize(profile.back_graphic_policy))}</small>` : ""}
          ${referenceRoleList(profile)}
          ${profile.reference_role_notes?.length ? `<ul>${profile.reference_role_notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>` : ""}
        </article>
      `).join("")}
      ${item.product_reference_requirements ? productRequirementsPanel(item.product_reference_requirements) : ""}
    </details>
  `;
}

function productRequirementsPanel(text) {
  const lines = String(text || "").split(/\n+/).map((line) => line.trim()).filter(Boolean);
  const groups = [
    ["Product", ["Product:", "Garment type:", "Silhouette:", "Fabric/wash:", "Front graphic policy:", "Back graphic policy:"]],
    ["References", ["Design sources:", "Fit/model sources:", "Material/detail sources:", "Front refs:", "Back refs:", "Detail refs:"]],
    ["Rules", ["Use blank_fit_model", "Use front_design", "Front requirements:", "Back requirements:", "Detail requirements:"]],
    ["Guardrails", ["Must never omit:", "Must not invent:"]],
  ].map(([title, prefixes]) => ({
    title,
    lines: lines.filter((line) => prefixes.some((prefix) => line.startsWith(prefix))),
  })).filter((group) => group.lines.length);
  const covered = new Set(groups.flatMap((group) => group.lines));
  const other = lines.filter((line) => !covered.has(line));
  if (other.length) groups.push({ title: "Other", lines: other });
  return `
    <div class="requirements-panel">
      ${groups.map((group) => `
        <section>
          <h4>${escapeHtml(group.title)}</h4>
          <dl>
            ${group.lines.map(requirementLine).join("")}
          </dl>
        </section>
      `).join("")}
    </div>
  `;
}

function requirementLine(line) {
  const parts = line.split(":");
  if (parts.length > 1 && !line.startsWith("Use ")) {
    const label = parts.shift();
    return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(parts.join(":").trim())}</dd></div>`;
  }
  return `<div class="full"><dd>${escapeHtml(line)}</dd></div>`;
}

function referenceRoleList(profile) {
  const roles = profile.reference_roles || {};
  const rows = [
    ["Actual Design", roles.front_design || []],
    ["Back Design", roles.back_design || []],
    ["Fit Model Only", roles.blank_fit_model || []],
    ["Material Detail", roles.material_detail || []],
    ["Folded Surface", roles.folded_surface || []],
    ["Unknown", roles.unknown || []],
  ].filter(([, files]) => files.length);
  if (!rows.length) return "";
  return `
    <div class="reference-role-list">
      ${rows.map(([label, files]) => `
        <div>
          <span>${escapeHtml(label)}</span>
          <small>${escapeHtml(files.slice(0, 5).join(", "))}${files.length > 5 ? ` +${files.length - 5}` : ""}</small>
        </div>
      `).join("")}
    </div>
  `;
}

function visualQaCard(qa) {
  if (!qa) return "";
  return `
    <details class="composition-plan-card visual-qa-card">
      <summary>Visual QA / ${escapeHtml(titleize(qa.status || "needs_review"))}</summary>
      <p>${escapeHtml(qa.summary || "")}</p>
      ${(qa.checks || []).length ? `<ul>${qa.checks.map((check) => `<li>${escapeHtml(titleize(check.status || "check"))}: ${escapeHtml(check.note || check.check || "")}</li>`).join("")}</ul>` : ""}
      ${(qa.fixes || []).length ? `<p class="eyebrow">Iteration Fixes</p><ul>${qa.fixes.map((fix) => `<li>${escapeHtml(fix)}</li>`).join("")}</ul>` : ""}
    </details>
  `;
}

function textSlideEditor(item) {
  if (!item.text_dominant && !(item.text_slides || []).length) return "";
  const slides = item.text_slides || [];
  return `
    <section class="brief-card text-slide-editor">
      <p class="eyebrow">Text Slide Editor</p>
      <p class="helper-text">Edit copy and simple placement. Save rerenders the slide images and logs your changes for future agent learning.</p>
      ${slides.map((slide, slideIndex) => `
        <details ${slideIndex === 0 ? "open" : ""}>
          <summary>Slide ${slideIndex + 1} / ${escapeHtml(slide.palette || "dark")}</summary>
          ${(slide.blocks || []).map((block, blockIndex) => textBlockEditor(slideIndex, blockIndex, block)).join("")}
        </details>
      `).join("")}
      <div class="builder-action-row">
        <button class="secondary" type="button" data-save-text-slides>Rerender Text Slides</button>
      </div>
      <p id="textSlideStatus" class="status"></p>
    </section>
  `;
}

function compositionPlanCard(item) {
  const plan = item.composition_plan;
  if (!plan) return "";
  return `
    <details class="composition-plan-card" open>
      <summary>Creative Composition Plan</summary>
      <p>${escapeHtml(plan.summary || "Composition plan saved.")}</p>
      ${(plan.quality_bar || []).length ? `<ul>${plan.quality_bar.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>` : ""}
      ${(plan.slide_plan || []).length ? `
        <div class="composition-slide-list">
          ${plan.slide_plan.map((slide) => `
            <article>
              <strong>Slide ${Number(slide.slot || 0) + 1} / ${escapeHtml(titleize(slide.role || "slot"))}</strong>
              <span>${escapeHtml(slide.asset_name || shortPath(slide.image_path || "") || "Current slot")}</span>
              <p>${escapeHtml(slide.reason || slide.treatment || "")}</p>
            </article>
          `).join("")}
        </div>
      ` : ""}
    </details>
  `;
}

function builderSlotEditor(item, slot) {
  if (!slot) return "";
  return `
    <section class="brief-card slot-editor-card">
      <p class="eyebrow">Active Slide Slot</p>
      <div class="slot-editor-layout">
        <div class="slot-editor-preview">${slotThumb(slot)}</div>
        <div class="slot-editor-fields">
          <strong>Slide ${state.builderSlotIndex + 1}: ${escapeHtml(slot.name || "Untitled slot")}</strong>
          <label>Role
            <select id="builderSlotRole">
              ${["hero", "product_clarity", "on_body", "text_backdrop", "texture_backdrop", "canvas_surface", "feed_breaker", "transition_slide", "process_proof", "design_system", "motion", "supporting"].map((role) => `<option value="${role}" ${slot.role === role ? "selected" : ""}>${titleize(role)}</option>`).join("")}
            </select>
          </label>
          <label>Overlay Text
            <input id="builderSlotOverlay" value="${escapeForAttribute(slot.overlay_text || "")}" placeholder="Optional text intended for this slide" />
          </label>
          <label>Slide Notes
            <textarea id="builderSlotNotes" placeholder="Why this slide belongs here, what it should teach the curator, or what should change.">${escapeHtml(slot.notes || "")}</textarea>
          </label>
          <div class="builder-action-row">
            <button class="secondary" type="button" data-save-slot-notes>Save Slide Notes</button>
          </div>
          <p id="builderSlotStatus" class="status"></p>
        </div>
      </div>
    </section>
  `;
}

function textBlockEditor(slideIndex, blockIndex, block) {
  return `
    <div class="text-block-editor" data-slide-index="${slideIndex}" data-block-index="${blockIndex}">
      <label>Text<textarea data-text-block-field="text">${escapeHtml(block.text || "")}</textarea></label>
      <div class="text-block-grid">
        <label>Role
          <select data-text-block-field="role">
            ${["brand", "display", "mono"].map((role) => `<option value="${role}" ${block.role === role ? "selected" : ""}>${titleize(role)}</option>`).join("")}
          </select>
        </label>
        <label>X<input type="number" data-text-block-field="x" value="${escapeForAttribute(block.x ?? 72)}" /></label>
        <label>Y<input type="number" data-text-block-field="y" value="${escapeForAttribute(block.y ?? 390)}" /></label>
        <label>Size<input type="number" data-text-block-field="size" value="${escapeForAttribute(block.size ?? 34)}" /></label>
        <label>Wrap<input type="number" data-text-block-field="wrap" value="${escapeForAttribute(block.wrap ?? 24)}" /></label>
      </div>
    </div>
  `;
}

function bindBuilderPostActions(item) {
  builderWorkspace.querySelectorAll("[data-ai-visual]").forEach((button) => {
    button.addEventListener("click", () => createVisualConcept(item.id, button.dataset.aiVisual));
  });
  builderWorkspace.querySelector("[data-save-post-edits]")?.addEventListener("click", () => saveBuilderPostEdits(item.id));
  builderWorkspace.querySelector("[data-improve-design]")?.addEventListener("click", () => improveBuilderDesign(item.id));
  builderWorkspace.querySelector("[data-save-text-slides]")?.addEventListener("click", () => saveTextSlides(item.id));
  builderWorkspace.querySelector("[data-save-slot-notes]")?.addEventListener("click", () => saveBuilderSlot(item.id));
  builderWorkspace.querySelector("[data-remove-selected-draft]")?.addEventListener("click", () => removeCalendarItem(item.id));
  builderWorkspace.querySelectorAll("[data-visual-slot]").forEach((button) => {
    button.addEventListener("click", () => {
      state.builderSlotIndex = Number(button.dataset.visualSlot || 0);
      renderBuilder();
    });
  });
  bindStateControls(builderWorkspace);
  builderWorkspace.querySelectorAll("[data-concept-path]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.conceptKind === "image") {
        openImageModal({
          imagePath: button.dataset.conceptPath,
          itemId: item.id,
          conceptType: conceptTypeFromPath(button.dataset.conceptPath),
          title: item.hook || "AI visual",
        });
        return;
      }
      selectItem({
        path: button.dataset.conceptPath,
        name: shortPath(button.dataset.conceptPath),
        category: "image_concepts",
        kind: button.dataset.conceptKind || "text",
      });
    });
  });
  builderWorkspace.querySelectorAll("[data-qa-concept]").forEach((button) => {
    button.addEventListener("click", () => runVisualQa(item.id, button.dataset.qaConcept, button.dataset.qaType || "model_shoot"));
  });
  builderWorkspace.querySelectorAll("[data-iterate-qa]").forEach((button) => {
    button.addEventListener("click", () => iterateWithQaFixes(item.id, button.dataset.iterateQa, button.dataset.qaType || "model_shoot"));
  });
  bindGeneratedImageButtons(builderWorkspace);
}

async function runVisualQa(itemId, imagePath, conceptType) {
  const status = document.getElementById("visualConceptStatus");
  if (status) status.textContent = "Running visual QA...";
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}/visual-concept/qa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_path: imagePath, concept_type: conceptType }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Visual QA failed.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || state.calendar;
  state.strategy = data.strategy || state.strategy;
  state.selectedCalendarItem = state.calendar.find((entry) => entry.id === itemId) || state.selectedCalendarItem;
  if (status) status.textContent = `Visual QA: ${titleize(data.qa?.status || "needs_review")}`;
  renderCalendar();
  renderFeed();
  renderBuilder();
}

async function iterateWithQaFixes(itemId, imagePath, conceptType) {
  const status = document.getElementById("visualConceptStatus");
  if (status) status.textContent = "Iterating with QA fixes...";
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}/visual-concept/iterate-qa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      image_path: imagePath,
      concept_type: conceptType,
      direction: document.getElementById("visualConceptDirection")?.value || "",
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "QA iteration failed.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || state.calendar;
  state.selectedCalendarItem = state.calendar.find((entry) => entry.id === itemId) || state.selectedCalendarItem;
  if (status) status.textContent = data.image_error
    ? `QA iteration brief saved, render failed: ${data.image_error}`
    : `QA iteration rendered: ${shortPath(data.concept?.image_path || "")}`;
  renderCalendar();
  renderFeed();
  renderBuilder();
}

async function saveTextSlides(itemId) {
  const item = state.calendar.find((entry) => entry.id === itemId);
  if (!item) return;
  const status = document.getElementById("textSlideStatus");
  if (status) status.textContent = "Rerendering text slides...";
  const slides = JSON.parse(JSON.stringify(item.text_slides || []));
  builderWorkspace.querySelectorAll("[data-slide-index][data-block-index]").forEach((editor) => {
    const slideIndex = Number(editor.dataset.slideIndex);
    const blockIndex = Number(editor.dataset.blockIndex);
    const block = slides[slideIndex]?.blocks?.[blockIndex];
    if (!block) return;
    editor.querySelectorAll("[data-text-block-field]").forEach((field) => {
      const key = field.dataset.textBlockField;
      block[key] = ["x", "y", "size", "wrap"].includes(key) ? Number(field.value || 0) : field.value;
    });
  });
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}/text-slides`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slides }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not rerender text slides.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || state.calendar;
  state.selectedCalendarItem = state.calendar.find((entry) => entry.id === itemId) || state.selectedCalendarItem;
  if (status) status.textContent = "Text slides rerendered and logged.";
  renderCalendar();
  renderFeed();
  renderBuilder();
}

async function saveBuilderPostEdits(itemId) {
  const status = document.getElementById("builderEditStatus");
  if (status) status.textContent = "Saving edits...";
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      hook: document.getElementById("builderHookInput")?.value || "",
      caption: document.getElementById("builderCaptionInput")?.value || "",
      reviewer_notes: document.getElementById("builderReviewerNotes")?.value || "",
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not save edits.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.selectedCalendarItem = state.calendar.find((entry) => entry.id === itemId) || state.selectedCalendarItem;
  if (status) status.textContent = "Edits saved for future agent context.";
  renderCalendar();
  renderFeed();
  renderBuilder();
}

async function improveBuilderDesign(itemId) {
  const status = document.getElementById("builderEditStatus");
  if (status) status.textContent = "Asking creative composition agent...";
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      direction: document.getElementById("builderReviewerNotes")?.value || "",
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not improve design.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || state.calendar;
  state.strategy = data.strategy || state.strategy;
  state.selectedCalendarItem = state.calendar.find((entry) => entry.id === itemId) || state.selectedCalendarItem;
  if (status) status.textContent = "Creative composition plan saved and applied to slots.";
  renderCalendar();
  renderFeed();
  renderBuilder();
}

async function createVisualConcept(itemId, conceptType) {
  const status = document.getElementById("visualConceptStatus");
  if (status) status.textContent = "Creating brief and rendering image...";
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}/visual-concept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      concept_type: conceptType,
      direction: document.getElementById("visualConceptDirection")?.value || "",
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Visual brief failed.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || state.calendar;
  state.selectedCalendarItem = state.calendar.find((entry) => entry.id === itemId) || state.selectedCalendarItem;
  preview.className = "preview";
  selectedTitle.textContent = `${titleize(conceptType)} Visual Concept`;
  selectedKind.textContent = "image concept";
  feedbackPath.value = data.concept?.image_path || data.concept?.path || "";
  if (data.concept?.image_path) {
    preview.innerHTML = `
      <button class="expandable-image" type="button" data-expand-image="${escapeForAttribute(data.concept.image_path)}" data-expand-item="${escapeForAttribute(itemId)}" data-expand-concept="${escapeForAttribute(conceptType)}">
        <img src="/media?path=${encodeURIComponent(data.concept.image_path)}&v=${Date.now()}" alt="${escapeHtml(conceptType)} visual concept" />
      </button>
      <details open>
        <summary>Image brief</summary>
        <pre>${escapeHtml(data.content || "")}</pre>
      </details>
    `;
    bindExpandableImages(preview);
  } else {
    preview.innerHTML = `<pre>${escapeHtml(data.content || "")}</pre>`;
  }
  if (status) status.textContent = data.image_error
    ? `Brief saved, render failed: ${data.image_error}`
    : `Rendered: ${shortPath(data.concept?.image_path || "")}`;
  renderCalendar();
  renderFeed();
  renderBuilder();
  const openSlot = document.getElementById("visualConceptOpen");
  if (openSlot && data.concept?.image_path) {
    openSlot.innerHTML = generatedImageButton(data.concept.image_path, itemId, conceptType, "Open Generated Image");
    bindGeneratedImageButtons(openSlot);
  }
}

function conceptTypeFromPath(path) {
  const text = String(path || "").toLowerCase();
  if (text.includes("process")) return "process_detail";
  if (text.includes("iteration")) return "model_shoot";
  return "model_shoot";
}

function builderSlots(item) {
  if (item.visual_slots?.length) return item.visual_slots;
  const selected = item.selected_assets?.length ? item.selected_assets : item.source_files || [];
  if (selected.length) {
    return selected.map((name, index) => ({
      index,
      name,
      asset_name: name,
      source: "drive_asset",
      role: index === 0 ? "hero" : "supporting",
      notes: "Original source asset slot.",
    }));
  }
  const images = item.visual_group?.images || [];
  return images.map((image, index) => ({
    index,
    name: image.name,
    image_path: image.path,
    source: "generated_visual",
    role: item.text_dominant ? "text_backdrop" : "supporting",
    notes: "Generated visual slide.",
  }));
}

function slotThumb(slot) {
  if (slot.asset_name) {
    const asset = findRawAsset(slot.asset_name);
    return asset ? assetThumb(asset) : `<div class="asset-placeholder">${escapeHtml((slot.asset_name.split(".").pop() || "FILE").toUpperCase())}</div>`;
  }
  if (slot.image_path) {
    return `<img src="/media?path=${encodeURIComponent(slot.image_path)}" alt="${escapeHtml(slot.name || "slide")}" loading="lazy" />`;
  }
  return '<div class="asset-placeholder">SLOT</div>';
}

function visualItemBrief(item) {
  const images = item.visual_group?.images || [];
  return `
    <section class="candidate-brief">
      <div class="brief-topline">
        <span>${escapeHtml(item.format || "Post")}</span>
        <span>${escapeHtml(item.pillar || "Visual Direction")}</span>
        ${item.rating ? `<span>Rated ${escapeHtml(item.rating)}/5</span>` : ""}
      </div>
      <div class="brief-card hero">
        <p class="eyebrow">Visual Set</p>
        <h4>${escapeHtml(item.hook || "Generated visual direction")}</h4>
      </div>
      <div class="source-preview-grid">
        ${images.map((image, index) => `
          <button class="source-preview source-preview-button ${state.builderSlotIndex === index ? "active" : ""}" type="button" data-visual-slot="${escapeForAttribute(String(index))}">
            <div class="source-preview-media"><img src="/media?path=${encodeURIComponent(image.path)}" alt="${escapeHtml(image.name)}" loading="lazy" /></div>
            <strong>${escapeHtml(image.name)}</strong>
            <span>${escapeHtml(shortPath(image.path))}</span>
          </button>
        `).join("") || '<div class="empty-note">No rendered slides found.</div>'}
      </div>
      ${item.curator_reason ? briefCard("Curator Note", item.curator_reason) : ""}
      ${briefCard("Builder Note", "Use the Drive library to replace any slot, or rank this visual set in the run review so the curator knows how strongly to use it.")}
    </section>
  `;
}

function renderBuilderAssetLibrary() {
  const buckets = ["All", "Generated Assets", "AI Generated", "Text Backdrops", "Feed Breakers", "Store Products", "Shoot Photos", "Photoshoot / Campaign", "Process / Studio", "Design Assets", "Video"];
  builderAssetFilters.innerHTML = buckets.map((bucket) => `
    <button class="filter-chip ${state.builderAssetFilter === bucket ? "active" : ""}" type="button" data-filter="${escapeHtml(bucket)}">${escapeHtml(bucket)}</button>
  `).join("");
  builderAssetFilters.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      state.builderAssetFilter = button.dataset.filter;
      renderBuilderAssetLibrary();
    });
  });

  const assets = state.rawAssets
    .filter((asset) => {
      if (state.builderAssetFilter === "All") return true;
      if (state.builderAssetFilter === "Generated Assets") return asset.source === "generated_asset";
      if (state.builderAssetFilter === "Text Backdrops") return (asset.designRoles || []).some((role) => ["text_backdrop", "texture_backdrop", "canvas_surface"].includes(role));
      if (state.builderAssetFilter === "Feed Breakers") return (asset.designRoles || []).includes("feed_breaker") || Number(asset.designSurfaceScore || 0) >= 5;
      return asset.creativeBucket === state.builderAssetFilter;
    })
    .sort((a, b) => {
      const ratingDiff = Number(b.rating || 0) - Number(a.rating || 0);
      if (ratingDiff) return ratingDiff;
      const scoreDiff = Number(b.designSurfaceScore || 0) - Number(a.designSurfaceScore || 0);
      if (scoreDiff) return scoreDiff;
      return String(a.name || "").localeCompare(String(b.name || ""));
    })
    .slice(0, 96);
  builderAssetLibrary.innerHTML = assets.map((asset) => `
    <button class="library-asset" type="button" title="${escapeHtml(asset.name)}" data-asset-name="${escapeForAttribute(asset.name)}" data-asset-path="${escapeForAttribute(asset.path || "")}" data-asset-source="${escapeForAttribute(asset.source || "drive_asset")}">
      ${assetThumb(asset)}
      <span>${escapeHtml(asset.name)}</span>
      ${asset.rating ? `<small>Rated ${escapeHtml(String(asset.rating))}/5</small>` : ""}
      ${(asset.designRoles || []).length ? `<small>${escapeHtml((asset.designRoles || []).slice(0, 3).map(titleize).join(" / "))}</small>` : ""}
      ${asset.source === "generated_asset" ? `<small>${escapeHtml(asset.creativeBucket || "Generated")}</small>` : ""}
    </button>
  `).join("") || '<div class="empty-note">No Drive assets found for this filter.</div>';
  builderAssetLibrary.querySelectorAll("[data-asset-name]").forEach((button) => {
    button.addEventListener("click", () => updateBuilderAsset({
      name: button.dataset.assetName,
      path: button.dataset.assetPath,
      source: button.dataset.assetSource,
    }));
  });
}

async function updateBuilderAsset(asset) {
  if (!state.selectedCalendarItem) return;
  const isGenerated = asset.source === "generated_asset" && asset.path;
  const response = await fetch(`/api/calendar/${encodeURIComponent(state.selectedCalendarItem.id)}/slots/${state.builderSlotIndex}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      asset_name: isGenerated ? undefined : asset.name,
      image_path: isGenerated ? asset.path : undefined,
      role: document.getElementById("builderSlotRole")?.value || undefined,
      notes: document.getElementById("builderSlotNotes")?.value || "",
      overlay_text: document.getElementById("builderSlotOverlay")?.value || "",
    }),
  });
  if (!response.ok) return;
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.selectedCalendarItem = state.calendar.find((item) => item.id === state.selectedCalendarItem?.id) || null;
  renderCalendar();
  renderFeed();
  renderBuilder();
}

async function saveBuilderSlot(itemId) {
  const status = document.getElementById("builderSlotStatus");
  if (status) status.textContent = "Saving slide slot...";
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}/slots/${state.builderSlotIndex}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      role: document.getElementById("builderSlotRole")?.value || "",
      notes: document.getElementById("builderSlotNotes")?.value || "",
      overlay_text: document.getElementById("builderSlotOverlay")?.value || "",
    }),
  });
  if (!response.ok) {
    if (status) status.textContent = "Could not save slide slot.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.selectedCalendarItem = state.calendar.find((item) => item.id === itemId) || state.selectedCalendarItem;
  if (status) status.textContent = "Slide slot saved for curator learning.";
  renderCalendar();
  renderFeed();
  renderBuilder();
}

function renderWorkspace() {
  if (!state.selectedCandidate) {
    workspaceTitle.textContent = "Select a candidate.";
    workspace.className = "workspace empty";
    workspace.textContent = "No candidate selected.";
    return;
  }

  const candidate = state.selectedCandidate;
  workspaceTitle.textContent = candidate.hook || candidate.title;
  workspace.className = "workspace";
  workspace.innerHTML = `
    <div class="source-preview-grid">
      ${candidateSourceAssets(candidate).map((asset) => sourcePreview(asset)).join("") || '<div class="empty-note">No previewable sources found.</div>'}
    </div>
    ${candidateBrief(candidate)}
  `;
}

function candidateBrief(candidate) {
  return `
    <section class="candidate-brief">
      <div class="brief-topline">
        <span>${escapeHtml(candidate.format || "Draft")}</span>
        <span>${escapeHtml(candidate.pillar || "General")}</span>
        ${candidate.posting_priority ? `<span>Priority ${escapeHtml(candidate.posting_priority)}</span>` : ""}
      </div>
      <div class="brief-card hero">
        <p class="eyebrow">Hook</p>
        <h4>${escapeHtml(candidate.hook || candidate.title)}</h4>
      </div>
      ${candidate.caption ? briefCard("Caption", candidate.caption) : ""}
      ${candidate.on_screen_text?.length ? briefList("On-screen Text", candidate.on_screen_text) : ""}
      ${candidate.structure ? briefSteps("Structure", candidate.structure) : ""}
      ${candidate.asset_roles ? briefCard("Asset Roles", candidate.asset_roles) : ""}
      ${candidate.edit_notes ? briefCard("Edit Notes", candidate.edit_notes) : ""}
      ${candidate.why ? briefCard("Why It Fits", candidate.why) : ""}
      ${candidate.source_files?.length ? briefList("Source Files", candidate.source_files) : ""}
      <details>
        <summary>Raw candidate markdown</summary>
        <pre>${escapeHtml(candidate.body)}</pre>
      </details>
    </section>
  `;
}

function briefCard(label, value) {
  return `
    <div class="brief-card">
      <p class="eyebrow">${escapeHtml(label)}</p>
      <p>${formatInlineText(value)}</p>
    </div>
  `;
}

function briefList(label, items) {
  return `
    <div class="brief-card">
      <p class="eyebrow">${escapeHtml(label)}</p>
      <ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
  `;
}

function briefSteps(label, value) {
  const items = value.split("\n").map((line) => line.trim()).filter(Boolean);
  return `
    <div class="brief-card">
      <p class="eyebrow">${escapeHtml(label)}</p>
      <ol>${items.map((item) => `<li>${escapeHtml(item.replace(/^\d+\.\s*/, ""))}</li>`).join("")}</ol>
    </div>
  `;
}

function candidateSourceAssets(candidate) {
  return candidate.source_files
    .map((name) => findRawAsset(name))
    .filter(Boolean);
}

function findRawAsset(name) {
  return state.rawAssets.find((asset) => asset.name === name) || null;
}

function assetThumb(asset) {
  if (isImageAsset(asset)) {
    return `<img src="${driveMediaUrl(asset)}" alt="${escapeHtml(asset.name)}" loading="lazy" onerror="this.replaceWith(assetFallback('${escapeForAttribute(assetLabel(asset))}'))" />`;
  }
  if (isVideoAsset(asset)) {
    return `
      <video src="${driveMediaUrl(asset)}#t=0.1" muted playsinline preload="metadata" controls
        onerror="this.replaceWith(assetFallback('${escapeForAttribute(assetLabel(asset))}'))"></video>
    `;
  }
  return `<div class="asset-placeholder">${escapeHtml(assetLabel(asset))}</div>`;
}

function sourcePreview(asset) {
  return `
    <article class="source-preview">
      <div class="source-preview-media">${assetThumb(asset)}</div>
      <strong>${escapeHtml(asset.name)}</strong>
      <span>${escapeHtml(asset.creativeBucket || "Raw")} · ${escapeHtml(asset.sizeLabel || "")}</span>
    </article>
  `;
}

function isPreviewableImage(asset) {
  return isImageAsset(asset);
}

function isImageAsset(asset) {
  return ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"].includes(asset.mimeType);
}

function isVideoAsset(asset) {
  return asset.mimeType?.startsWith("video/");
}

function assetLabel(asset) {
  if (isVideoAsset(asset)) return "MOV";
  return (asset.name.split(".").pop() || "FILE").toUpperCase();
}

function driveMediaUrl(asset) {
  if (asset.source === "generated_asset" || asset.path) {
    return `/media?path=${encodeURIComponent(asset.path)}`;
  }
  return `/drive-media?file_id=${encodeURIComponent(asset.id)}&name=${encodeURIComponent(asset.name)}&mime_type=${encodeURIComponent(asset.mimeType)}`;
}

async function selectItem(item) {
  state.selectedItem = item;
  selectedTitle.textContent = item.name;
  selectedKind.textContent = item.category.replace("_", " ");
  feedbackPath.value = item.path;
  feedbackStatus.textContent = "";
  replaceStatus.textContent = "";
  replacementFile.value = "";
  preview.className = "preview";
  preview.textContent = "Loading...";
  replaceForm.classList.toggle("hidden", item.kind !== "image");
  drivePicker.classList.toggle("hidden", item.kind !== "image");

  renderPosts();
  renderReports();

  const response = await fetch(`/api/file?path=${encodeURIComponent(item.path)}`);
  const data = await response.json();

  if (data.kind === "image") {
    preview.innerHTML = `
      <button class="expandable-image" type="button" data-expand-image="${escapeForAttribute(item.path)}">
        <img src="${data.url}&v=${Date.now()}" alt="${item.name}" />
      </button>
      ${stateControls("output", item.path, item.status || "Draft", item.name, "output-state-actions")}
    `;
    bindExpandableImages(preview);
    bindStateControls(preview);
  } else {
    preview.innerHTML = "";
    const pre = document.createElement("pre");
    pre.textContent = data.content;
    preview.appendChild(pre);
    preview.insertAdjacentHTML("beforeend", stateControls("output", item.path, item.status || "Draft", item.name, "output-state-actions"));
    bindStateControls(preview);
  }
  if (item.kind === "image") {
    await loadRawAssets();
    renderDriveAssets();
  }
  renderInlineComments();
}

function bindExpandableImages(root = document) {
  root.querySelectorAll("[data-expand-image]").forEach((button) => {
    button.addEventListener("click", () => openImageModal({
      imagePath: button.dataset.expandImage,
      itemId: button.dataset.expandItem || state.selectedCalendarItem?.id || "",
      conceptType: button.dataset.expandConcept || "model_shoot",
      title: selectedTitle.textContent || "Generated image",
    }));
  });
}

function openImageModal({ imagePath, itemId = "", conceptType = "model_shoot", title = "Generated image" }) {
  if (!imageModal || !imagePath) return;
  document.getElementById("imageModalTitle").textContent = title || "Generated image";
  imageModalMedia.innerHTML = `<img src="/media?path=${encodeURIComponent(imagePath)}&v=${Date.now()}" alt="${escapeHtml(title)}" />`;
  document.getElementById("iterationItemId").value = itemId || "";
  document.getElementById("iterationBasePath").value = imagePath || "";
  document.getElementById("iterationConceptType").value = conceptType || "model_shoot";
  document.getElementById("iterationDirection").value = "";
  document.getElementById("iterationReferences").value = "";
  iterationStatus.textContent = itemId ? "" : "Open this image from a Builder post to generate iterations.";
  iterationForm.classList.toggle("hidden", !itemId);
  imageModal.classList.remove("hidden");
}

function closeImageViewer() {
  imageModal?.classList.add("hidden");
}

function clearSelection() {
  state.selectedItem = null;
  selectedTitle.textContent = "Choose a preview or report.";
  selectedKind.textContent = "Select";
  feedbackPath.value = "";
  preview.className = "preview empty";
  preview.textContent = "Nothing selected yet.";
  replaceForm.classList.add("hidden");
  drivePicker.classList.add("hidden");
  renderInlineComments();
}

async function loadRawAssets() {
  if (state.rawAssetsLoaded) return;
  if (driveAssetList) driveAssetList.innerHTML = '<div class="empty-note">Loading Drive images...</div>';
  const response = await fetch("/api/raw-assets?kind=all");
  if (!response.ok) {
    if (driveAssetList) driveAssetList.innerHTML = '<div class="empty-note">Could not load Drive images.</div>';
    return;
  }
  state.rawAssets = (await response.json()).assets;
  state.rawAssetsLoaded = true;
}

function renderDriveAssets() {
  if (!state.selectedItem || state.selectedItem.kind !== "image") return;
  const assets = state.rawAssets.filter((asset) => asset.source !== "generated_asset").filter(isPreviewableImage).slice(0, 120);
  if (!assets.length) {
    driveAssetList.innerHTML = '<div class="empty-note">No web-safe Drive images found.</div>';
    return;
  }
  driveAssetList.innerHTML = "";
  assets.forEach((asset) => {
    const button = document.createElement("button");
    button.className = "drive-asset-button";
    button.innerHTML = `<strong>${escapeHtml(asset.name)}</strong><span>${escapeHtml(asset.creativeBucket || "Raw")} / ${escapeHtml(asset.sizeLabel || "")}</span>`;
    button.addEventListener("click", () => replaceFromDrive(asset));
    driveAssetList.appendChild(button);
  });
}

async function replaceFromDrive(asset) {
  if (!state.selectedItem) return;
  driveReplaceStatus.textContent = `Replacing with ${asset.name}...`;
  const response = await fetch("/api/replace-image-from-drive", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      output_path: state.selectedItem.path,
      drive_file_id: asset.id,
      drive_file_name: asset.name,
      mime_type: asset.mimeType,
    }),
  });
  if (!response.ok) {
    driveReplaceStatus.textContent = "Drive replacement failed.";
    return;
  }
  driveReplaceStatus.textContent = "Image switched. Previous version was backed up.";
  await selectItem(state.selectedItem);
}

function renderInlineComments() {
  const container = document.getElementById("inlineComments");
  if (!state.selectedItem) {
    container.innerHTML = '<div class="empty-note">Select an item to see comments.</div>';
    return;
  }

  const comments = state.feedback.filter((entry) => entry.output_path === state.selectedItem.path);
  const stateEntry = state.selectedItem.state || state.contentStates[`output:${state.selectedItem.path}`];
  const stateHtml = stateEntry ? `
    <article class="comment state-history">
      <strong>${escapeHtml(stateEntry.status || "Draft")}</strong>
      <p>${escapeHtml(stateEntry.title || state.selectedItem.name)}</p>
      ${stateEntry.notes ? `<small>${escapeHtml(stateEntry.notes)}</small>` : ""}
      ${stateEntry.updated_at ? `<small>${escapeHtml(stateEntry.updated_at)}</small>` : ""}
    </article>
  ` : "";
  if (!comments.length) {
    container.innerHTML = stateHtml || '<div class="empty-note">No comments yet.</div>';
    return;
  }

  container.innerHTML = stateHtml + comments
    .slice()
    .reverse()
    .map((entry) => `
      <article class="comment">
        <strong>${entry.rating}/5</strong>
        <p>${escapeHtml(entry.comment || "No comment.")}</p>
        ${entry.improvement_request ? `<small>${escapeHtml(entry.improvement_request)}</small>` : ""}
      </article>
    `)
    .join("");
}

document.getElementById("feedbackForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!feedbackPath.value) {
    feedbackStatus.textContent = "Select an item first.";
    return;
  }

  const payload = {
    output_path: feedbackPath.value,
    rating: Number(document.getElementById("rating").value),
    comment: document.getElementById("comment").value,
    improvement_request: document.getElementById("improvement").value,
    category: state.selectedItem?.category || "general",
  };

  const response = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    feedbackStatus.textContent = "Comment failed to save.";
    return;
  }

  document.getElementById("comment").value = "";
  document.getElementById("improvement").value = "";
  feedbackStatus.textContent = "Comment saved.";
  await loadDashboard();
});

replaceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedItem || state.selectedItem.kind !== "image") {
    replaceStatus.textContent = "Select an image first.";
    return;
  }
  if (!replacementFile.files.length) {
    replaceStatus.textContent = "Choose an image file.";
    return;
  }

  const formData = new FormData();
  formData.append("file", replacementFile.files[0]);
  replaceStatus.textContent = "Replacing image...";

  const response = await fetch(`/api/replace-image?path=${encodeURIComponent(state.selectedItem.path)}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    replaceStatus.textContent = "Image replacement failed.";
    return;
  }

  replaceStatus.textContent = "Image replaced. Previous file was backed up.";
  await selectItem(state.selectedItem);
});

runAgentsButton.addEventListener("click", async () => {
  const startedAt = new Date();
  setRunState("running", `Running agents... started ${startedAt.toLocaleTimeString()}`);
  const response = await fetch("/api/run", { method: "POST" });
  if (!response.ok) {
    setRunState("error", "Run failed. Check terminal logs.");
    return;
  }
  const data = await response.json();
  const finishedAt = new Date();
  const seconds = Math.max(1, Math.round((finishedAt - startedAt) / 1000));
  setRunState("done", `Agents finished at ${finishedAt.toLocaleTimeString()} after ${seconds}s.`, data.paths || {});
  await loadDashboard();
  await openRunReview();
});

function setRunState(stateName, message, paths = {}) {
  runStatus.textContent = message;
  runNotice.className = `run-notice ${stateName}`;
  runAgentsButton.disabled = stateName === "running";
  runAgentsButton.textContent = stateName === "running" ? "Running..." : "Run Today";

  const pathEntries = Object.entries(paths);
  runNotice.innerHTML = `
    <strong>${stateName === "done" ? "Run complete" : stateName === "error" ? "Run failed" : "Agents running"}</strong>
    <span>${escapeHtml(message)}</span>
    ${pathEntries.length ? `<ul>${pathEntries.map(([key, value]) => `<li>${escapeHtml(titleize(key))}: ${escapeHtml(shortPath(value))}</li>`).join("")}</ul>` : ""}
    ${stateName === "done" ? '<button id="reviewLatestRun" class="secondary" type="button">Review Outputs</button>' : ""}
  `;
  document.getElementById("reviewLatestRun")?.addEventListener("click", openRunReview);
}

async function openRunReview() {
  if (!reviewModal || !state.selectedDay) return;
  reviewModalStatus.textContent = "Loading today's outputs...";
  reviewModal.classList.remove("hidden");
  const response = await fetch(`/api/review-items?date=${encodeURIComponent(state.selectedDay.date)}`);
  if (!response.ok) {
    reviewModalStatus.textContent = "Could not load review items.";
    return;
  }
  state.reviewItems = (await response.json()).items || [];
  renderReviewModal();
}

function closeReview() {
  reviewModal?.classList.add("hidden");
}

function renderReviewModal() {
  reviewModalStatus.textContent = state.reviewItems.length
    ? "Rank the strongest pieces. Ratings of 4 or 5 are promoted into the curator feed pool."
    : "No reviewable outputs found for this day.";
  reviewItems.innerHTML = state.reviewItems.map((item) => `
    <article class="review-card" data-review-path="${escapeForAttribute(item.path)}">
      <div class="review-card-media">
        ${reviewMedia(item)}
      </div>
      <div class="review-card-copy">
        <p class="eyebrow">${escapeHtml(item.type.replace("_", " "))}</p>
        <h4>${escapeHtml(item.title)}</h4>
        <span>${escapeHtml(item.subtitle || "")}</span>
        <label>
          Rank
          <select data-review-rating>
            <option value="0" ${Number(item.rating || 0) === 0 ? "selected" : ""}>Unranked</option>
            <option value="5" ${Number(item.rating || 0) === 5 ? "selected" : ""}>5 - strongest</option>
            <option value="4" ${Number(item.rating || 0) === 4 ? "selected" : ""}>4 - use this</option>
            <option value="3" ${Number(item.rating || 0) === 3 ? "selected" : ""}>3 - needs edits</option>
            <option value="2" ${Number(item.rating || 0) === 2 ? "selected" : ""}>2 - weak</option>
            <option value="1" ${Number(item.rating || 0) === 1 ? "selected" : ""}>1 - reject</option>
          </select>
        </label>
        <label>
          Note
          <textarea data-review-note placeholder="Why it works, or what to change."></textarea>
        </label>
      </div>
    </article>
  `).join("");
}

function reviewMedia(item) {
  const images = item.images || item.group?.images || [];
  if (images.length) {
    return images.slice(0, 4).map((image) => `<img src="/media?path=${encodeURIComponent(image.path)}" alt="${escapeHtml(image.name)}" loading="lazy" />`).join("");
  }
  const candidateAssets = item.candidate ? candidateSourceAssets(item.candidate).slice(0, 3) : [];
  if (candidateAssets.length) return candidateAssets.map((asset) => assetThumb(asset)).join("");
  return '<div class="asset-placeholder">TEXT</div>';
}

function collectReviewRatings() {
  return [...reviewItems.querySelectorAll(".review-card")]
    .map((card) => {
      const rating = Number(card.querySelector("[data-review-rating]").value);
      const reviewItem = state.reviewItems.find((item) => item.path === card.dataset.reviewPath);
      if (!rating || !reviewItem) return null;
      return {
        output_path: reviewItem.path,
        rating,
        comment: card.querySelector("[data-review-note]").value,
        improvement_request: rating >= 4 ? "Use this direction when curating the feed." : "Learn from this ranking for the next run.",
        category: reviewItem.category || reviewItem.type || "run_review",
      };
    })
    .filter(Boolean);
}

async function submitReviewRatings({ curate = false } = {}) {
  const ratings = collectReviewRatings();
  if (!ratings.length) {
    reviewModalStatus.textContent = "Choose at least one rank first.";
    return false;
  }
  reviewModalStatus.textContent = curate ? "Saving ranks and asking the curator to rework the grid..." : "Saving ranks...";
  const response = await fetch("/api/review-ratings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ratings }),
  });
  if (!response.ok) {
    reviewModalStatus.textContent = "Could not save ranks.";
    return false;
  }
  const data = await response.json();
  state.feedback = data.feedback || state.feedback;
  state.calendar = data.items || state.calendar;
  state.strategy = data.strategy || state.strategy;
  state.curation = data.curation || state.curation;
  if (curate) await curateFeed();
  renderDashboard();
  reviewModalStatus.textContent = curate ? "Ranks saved. Feed curator updated the grid." : "Ranks saved.";
  return true;
}

document.querySelectorAll(".mode-button").forEach((button) => {
  button.addEventListener("click", async () => {
    state.mode = button.dataset.mode;
    renderMode();
    await ensureModeData(state.mode);
    renderDashboard();
  });
});

document.getElementById("generateCalendar").addEventListener("click", async () => {
  const response = await fetch("/api/calendar/generate", { method: "POST" });
  if (!response.ok) return;
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.mode = "calendar";
  renderCalendar();
  renderFeed();
  renderBuilder();
  renderMode();
});

document.getElementById("launchRecovery")?.addEventListener("click", async () => {
  const button = document.getElementById("launchRecovery");
  button.disabled = true;
  button.textContent = "Building...";
  const response = await fetch("/api/calendar/launch-recovery", { method: "POST" });
  button.disabled = false;
  button.textContent = "Launch Recovery";
  if (!response.ok) return;
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.curation = data.curation || state.curation;
  state.mode = "calendar";
  renderCalendar();
  renderFeed();
  renderBuilder();
  renderMode();
});

document.getElementById("curateFeed").addEventListener("click", curateFeed);
refreshHighlightsButton?.addEventListener("click", async () => {
  refreshHighlightsButton.disabled = true;
  refreshHighlightsButton.textContent = "Refreshing...";
  const response = await fetch("/api/highlights/generate", { method: "POST" });
  refreshHighlightsButton.disabled = false;
  refreshHighlightsButton.textContent = "Refresh Highlights";
  if (!response.ok) return;
  state.highlights = (await response.json()).highlights || [];
  state.selectedHighlightFrame = null;
  renderHighlights();
});
refreshShootPlanButton?.addEventListener("click", async () => {
  refreshShootPlanButton.disabled = true;
  refreshShootPlanButton.textContent = "Refreshing...";
  await loadShootPlan();
  refreshShootPlanButton.disabled = false;
  refreshShootPlanButton.textContent = "Refresh Shot List";
  renderShootPlan();
});
refreshMerchandisingButton?.addEventListener("click", async () => {
  refreshMerchandisingButton.disabled = true;
  refreshMerchandisingButton.textContent = "Refreshing...";
  await loadMerchandising();
  refreshMerchandisingButton.disabled = false;
  refreshMerchandisingButton.textContent = "Refresh Product Plan";
  renderMerchandising();
});
refreshLaunchPlanButton?.addEventListener("click", async () => {
  refreshLaunchPlanButton.disabled = true;
  refreshLaunchPlanButton.textContent = "Refreshing...";
  await loadLaunchPlan();
  refreshLaunchPlanButton.disabled = false;
  refreshLaunchPlanButton.textContent = "Refresh Launch Plan";
  renderLaunchPlan();
});
refreshCommunityFaqButton?.addEventListener("click", async () => {
  refreshCommunityFaqButton.disabled = true;
  refreshCommunityFaqButton.textContent = "Refreshing...";
  await loadCommunityFaq();
  refreshCommunityFaqButton.disabled = false;
  refreshCommunityFaqButton.textContent = "Refresh FAQ";
  renderCommunityFaq();
});
refreshOwnedPlanButton?.addEventListener("click", async () => {
  refreshOwnedPlanButton.disabled = true;
  refreshOwnedPlanButton.textContent = "Refreshing...";
  await loadOwnedPlan();
  refreshOwnedPlanButton.disabled = false;
  refreshOwnedPlanButton.textContent = "Refresh Email / SMS";
  renderOwnedPlan();
});
refreshCampaignMemoryButton?.addEventListener("click", refreshCampaignMemory);
openReviewModalButton?.addEventListener("click", openRunReview);
closeReviewModal?.addEventListener("click", closeReview);
reviewModal?.addEventListener("click", (event) => {
  if (event.target === reviewModal) closeReview();
});
saveReviewRatings?.addEventListener("click", () => submitReviewRatings());
saveReviewAndCurate?.addEventListener("click", () => submitReviewRatings({ curate: true }));
closeImageModal?.addEventListener("click", closeImageViewer);
imageModal?.addEventListener("click", (event) => {
  if (event.target === imageModal) closeImageViewer();
});
iterationForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const itemId = document.getElementById("iterationItemId").value;
  if (!itemId) return;
  iterationStatus.textContent = "Generating iteration...";
  const formData = new FormData();
  formData.append("direction", document.getElementById("iterationDirection").value);
  formData.append("base_image_path", document.getElementById("iterationBasePath").value);
  formData.append("concept_type", document.getElementById("iterationConceptType").value || "model_shoot");
  [...document.getElementById("iterationReferences").files].forEach((file) => formData.append("reference_files", file));
  const response = await fetch(`/api/calendar/${encodeURIComponent(itemId)}/visual-concept/iterate`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    iterationStatus.textContent = "Iteration failed.";
    return;
  }
  const data = await response.json();
  state.calendar = data.items || state.calendar;
  state.selectedCalendarItem = state.calendar.find((entry) => entry.id === itemId) || state.selectedCalendarItem;
  if (data.concept?.image_path) {
    openImageModal({
      imagePath: data.concept.image_path,
      itemId,
      conceptType: data.concept.concept_type || "model_shoot_iteration",
      title: "AI visual iteration",
    });
    preview.className = "preview";
    selectedTitle.textContent = "AI Visual Iteration";
    selectedKind.textContent = "image concept";
    feedbackPath.value = data.concept.image_path;
    preview.innerHTML = `
      <button class="expandable-image" type="button" data-expand-image="${escapeForAttribute(data.concept.image_path)}" data-expand-item="${escapeForAttribute(itemId)}" data-expand-concept="${escapeForAttribute(data.concept.concept_type || "model_shoot_iteration")}">
        <img src="/media?path=${encodeURIComponent(data.concept.image_path)}&v=${Date.now()}" alt="AI visual iteration" />
      </button>
    `;
    bindExpandableImages(preview);
  }
  iterationStatus.innerHTML = data.image_error
    ? `Brief saved, render failed: ${escapeHtml(data.image_error)}`
    : `Iteration generated. ${generatedImageButton(data.concept?.image_path || "", itemId, data.concept?.concept_type || "model_shoot_iteration", "Open Generated Image")}`;
  bindGeneratedImageButtons(iterationStatus);
  renderCalendar();
  renderFeed();
  renderVisualArchive();
  renderBuilder();
});

builderStatus.addEventListener("change", async () => {
  if (!state.selectedCalendarItem) return;
  const response = await fetch(`/api/calendar/${encodeURIComponent(state.selectedCalendarItem.id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: builderStatus.value }),
  });
  if (!response.ok) return;
  const data = await response.json();
  state.calendar = data.items || [];
  state.strategy = data.strategy || null;
  state.selectedCalendarItem = state.calendar.find((item) => item.id === state.selectedCalendarItem?.id) || null;
  renderCalendar();
  renderFeed();
  renderBuilder();
});

document.getElementById("productUploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("productImageFile");
  const status = document.getElementById("productUploadStatus");
  if (!fileInput.files.length) {
    status.textContent = "Choose a product image.";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("product_name", document.getElementById("productName").value);
  formData.append("notes", document.getElementById("productNotes").value);
  status.textContent = "Uploading product...";

  const response = await fetch("/api/product-inventory", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    status.textContent = "Product upload failed.";
    return;
  }

  fileInput.value = "";
  document.getElementById("productName").value = "";
  document.getElementById("productNotes").value = "";
  status.textContent = "Product added.";
  state.products = (await response.json()).products;
});

document.querySelectorAll("[data-regen]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.selectedCandidate) {
      regenStatus.textContent = "Select a candidate first.";
      return;
    }
    const section = button.dataset.regen;
    regenStatus.textContent = `Regenerating ${section}...`;
    const response = await fetch("/api/regenerate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_path: state.selectedCandidate.source_path,
        section,
        direction: document.getElementById("regenDirection").value,
      }),
    });

    if (!response.ok) {
      regenStatus.textContent = "Regeneration failed.";
      return;
    }

    const data = await response.json();
    regenStatus.textContent = `Saved variation: ${data.path}`;
    preview.className = "preview";
    preview.innerHTML = "";
    const pre = document.createElement("pre");
    pre.textContent = data.content;
    preview.appendChild(pre);
    selectedTitle.textContent = `${titleize(section)} Variation`;
    selectedKind.textContent = "content variation";
  });
});

function reportLabel(item) {
  return item.category.replace("_", " ");
}

function titleize(value) {
  return value.replace(/[-_]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortPath(value) {
  const text = String(value || "");
  const marker = "outputs";
  const index = text.lastIndexOf(marker);
  return index >= 0 ? text.slice(index) : text;
}

function formatInlineText(value) {
  return escapeHtml(value || "").replace(/\n/g, "<br>");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function escapeForAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

function cssEscape(value) {
  if (window.CSS?.escape) return window.CSS.escape(value);
  return String(value).replace(/["\\]/g, "\\$&");
}

function assetFallback(label) {
  const fallback = document.createElement("div");
  fallback.className = "asset-placeholder";
  fallback.textContent = label;
  return fallback;
}

loadDashboard();
