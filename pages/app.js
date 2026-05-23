let dashboardData = { days: [] };
let selectedDay = null;

const dayNav = document.getElementById("dayNav");
const gallery = document.getElementById("gallery");
const reports = document.getElementById("reports");
const selectedDayLabel = document.getElementById("selectedDayLabel");
const reportCount = document.getElementById("reportCount");
const imageCount = document.getElementById("imageCount");
const categoryCount = document.getElementById("categoryCount");

async function boot() {
  const response = await fetch("data.json", { cache: "no-store" });
  dashboardData = await response.json();
  selectedDay = dashboardData.days[0] || null;
  render();
}

function render() {
  renderDays();
  renderMetrics();
  renderGallery();
  renderReports();
}

function renderDays() {
  dayNav.innerHTML = "";
  if (!dashboardData.days.length) {
    dayNav.innerHTML = '<div class="empty">No outputs have been published yet.</div>';
    return;
  }

  dashboardData.days.forEach((day) => {
    const button = document.createElement("button");
    button.className = `day-button ${selectedDay?.date === day.date ? "active" : ""}`;
    button.type = "button";
    button.innerHTML = `<strong>${escapeHtml(day.date)}</strong><span>${day.reports.length} reports / ${day.images.length} images</span>`;
    button.addEventListener("click", () => {
      selectedDay = day;
      render();
    });
    dayNav.appendChild(button);
  });
}

function renderMetrics() {
  const categories = new Set((selectedDay?.reports || []).map((item) => item.category));
  selectedDayLabel.textContent = selectedDay ? selectedDay.date : "No Day";
  reportCount.textContent = selectedDay?.reports.length || 0;
  imageCount.textContent = selectedDay?.images.length || 0;
  categoryCount.textContent = categories.size;
}

function renderGallery() {
  const images = selectedDay?.images || [];
  gallery.innerHTML = "";
  if (!images.length) {
    gallery.innerHTML = '<div class="empty">No generated visuals for this day.</div>';
    return;
  }

  images.forEach((image) => {
    const card = document.createElement("article");
    card.className = "image-card";
    card.innerHTML = `
      <img src="${escapeForAttribute(image.publicPath)}" alt="${escapeForAttribute(image.name)}" loading="lazy" />
      <div class="card-copy">
        <h3>${escapeHtml(image.name)}</h3>
        <p>${escapeHtml(image.category)}</p>
      </div>
    `;
    gallery.appendChild(card);
  });
}

function renderReports() {
  const items = selectedDay?.reports || [];
  reports.innerHTML = "";
  if (!items.length) {
    reports.innerHTML = '<div class="empty">No reports for this day.</div>';
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "report-card";
    card.innerHTML = `
      <p class="eyebrow">${escapeHtml(item.category)}</p>
      <h3>${escapeHtml(item.name)}</h3>
      <pre>${escapeHtml(item.content)}</pre>
    `;
    reports.appendChild(card);
  });
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

boot().catch((error) => {
  reports.innerHTML = `<div class="empty">Dashboard failed to load: ${escapeHtml(error.message)}</div>`;
});
