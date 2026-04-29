let state = {
  outputs: [],
  feedback: [],
  filter: "all",
  selected: null,
};

const outputList = document.getElementById("outputList");
const preview = document.getElementById("preview");
const selectedTitle = document.getElementById("selectedTitle");
const selectedCategory = document.getElementById("selectedCategory");
const feedbackPath = document.getElementById("feedbackPath");
const feedbackStatus = document.getElementById("feedbackStatus");
const runStatus = document.getElementById("runStatus");

async function loadDashboard() {
  const [outputsResponse, feedbackResponse] = await Promise.all([
    fetch("/api/outputs"),
    fetch("/api/feedback"),
  ]);
  state.outputs = (await outputsResponse.json()).outputs;
  state.feedback = (await feedbackResponse.json()).feedback;
  document.getElementById("outputCount").textContent = state.outputs.length;
  document.getElementById("feedbackCount").textContent = state.feedback.length;
  renderOutputs();
}

function renderOutputs() {
  const outputs = state.outputs.filter((item) => state.filter === "all" || item.category === state.filter);
  outputList.innerHTML = "";

  if (!outputs.length) {
    outputList.innerHTML = '<div class="output-item"><strong>No outputs yet</strong><span>Run agents to generate content.</span></div>';
    return;
  }

  outputs.forEach((item) => {
    const button = document.createElement("button");
    button.className = `output-item ${state.selected?.path === item.path ? "active" : ""}`;
    button.innerHTML = `<strong>${item.name}</strong><span>${item.category} / ${item.kind}</span>`;
    button.addEventListener("click", () => selectOutput(item));
    outputList.appendChild(button);
  });
}

async function selectOutput(item) {
  state.selected = item;
  selectedTitle.textContent = item.name;
  selectedCategory.textContent = item.category.replace("_", " ");
  feedbackPath.value = item.path;
  preview.className = "preview";
  preview.textContent = "Loading...";
  renderOutputs();

  const response = await fetch(`/api/file?path=${encodeURIComponent(item.path)}`);
  const data = await response.json();

  if (data.kind === "image") {
    preview.innerHTML = `<img src="${data.url}" alt="${item.name}" />`;
  } else {
    const pre = document.createElement("pre");
    pre.textContent = data.content;
    preview.innerHTML = "";
    preview.appendChild(pre);
  }
}

document.querySelectorAll(".nav").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.filter = button.dataset.filter;
    renderOutputs();
  });
});

document.getElementById("feedbackForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!feedbackPath.value) {
    feedbackStatus.textContent = "Select an output first.";
    return;
  }

  const payload = {
    output_path: feedbackPath.value,
    rating: Number(document.getElementById("rating").value),
    comment: document.getElementById("comment").value,
    improvement_request: document.getElementById("improvement").value,
    category: state.selected?.category || "general",
  };

  const response = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    feedbackStatus.textContent = "Feedback failed to save.";
    return;
  }

  document.getElementById("comment").value = "";
  document.getElementById("improvement").value = "";
  feedbackStatus.textContent = "Feedback saved. Future runs will use it.";
  await loadDashboard();
});

document.getElementById("runAgents").addEventListener("click", async () => {
  runStatus.textContent = "Running agents...";
  const response = await fetch("/api/run", { method: "POST" });
  if (!response.ok) {
    runStatus.textContent = "Run failed. Check terminal logs.";
    return;
  }
  runStatus.textContent = "Run complete.";
  await loadDashboard();
});

loadDashboard();
