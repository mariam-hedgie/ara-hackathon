const projectForm = document.getElementById("project-form");
const projectNameInput = document.getElementById("project-name");
const projectDescriptionInput = document.getElementById("project-description");
const projectList = document.getElementById("project-list");
const statusLine = document.getElementById("status-line");

const selectedProjectName = document.getElementById("selected-project-name");
const selectedProjectDescription = document.getElementById("selected-project-description");
const paperCount = document.getElementById("paper-count");
const memoryCount = document.getElementById("memory-count");
const contradictionCount = document.getElementById("contradiction-count");
const briefCount = document.getElementById("brief-count");

const promptInput = document.getElementById("prompt-input");
const sourceTitleInput = document.getElementById("source-title");
const pastedTextInput = document.getElementById("pasted-text-input");
const linkInput = document.getElementById("link-input");
const voiceNoteInput = document.getElementById("voice-note-input");
const memoryInput = document.getElementById("memory-input");

const fileInput = document.getElementById("file-input");
const attachmentList = document.getElementById("attachment-list");

const askButton = document.getElementById("ask-button");
const ingestButton = document.getElementById("ingest-button");
const compareButton = document.getElementById("compare-button");
const contradictionButton = document.getElementById("contradiction-button");
const briefButton = document.getElementById("brief-button");
const saveMemoryButton = document.getElementById("save-memory-button");
const startVoiceNoteButton = document.getElementById("start-voice-note");
const stopVoiceNoteButton = document.getElementById("stop-voice-note");

const outputKind = document.getElementById("output-kind");
const output = document.getElementById("output");
const speakButton = document.getElementById("speak-button");
const stopSpeakingButton = document.getElementById("stop-speaking");

const claimValue = document.getElementById("claim-value");
const evidenceValue = document.getElementById("evidence-value");
const gapValue = document.getElementById("gap-value");
const limitationValue = document.getElementById("limitation-value");
const relevanceValue = document.getElementById("relevance-value");

const paperList = document.getElementById("paper-list");
const memoryList = document.getElementById("memory-list");
const briefList = document.getElementById("brief-list");
const contradictionList = document.getElementById("contradiction-list");

const SELECTED_PROJECT_KEY = "voice-research-agent:selected-project";

let projects = [];
let currentProject = null;
let attachments = [];
let latestAnswer = "";
let recognition = null;

document.addEventListener("DOMContentLoaded", async () => {
  wireEvents();
  await loadProjects();
});

function wireEvents() {
  projectForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = projectNameInput.value.trim();
    const description = projectDescriptionInput.value.trim();
    if (!name) {
      setStatus("Project name is required.");
      return;
    }

    setStatus("Creating project...");
    try {
      const response = await apiFetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description })
      });
      projectNameInput.value = "";
      projectDescriptionInput.value = "";
      await loadProjects(response.project?.id);
      setStatus("Project created.");
    } catch (error) {
      setStatus(readError(error));
    }
  });

  fileInput.addEventListener("change", (event) => {
    const files = Array.from(event.target.files || []);
    attachments = attachments.concat(files);
    renderAttachmentList();
    fileInput.value = "";
  });

  askButton.addEventListener("click", () => runAction("ask"));
  ingestButton.addEventListener("click", () => runAction("ingest"));
  compareButton.addEventListener("click", () => runAction("compare"));
  contradictionButton.addEventListener("click", () => runAction("contradictions"));
  briefButton.addEventListener("click", () => runAction("brief"));
  saveMemoryButton.addEventListener("click", () => runAction("memory"));

  speakButton.addEventListener("click", () => {
    if (!latestAnswer) {
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(stripMarkdown(latestAnswer));
    window.speechSynthesis.speak(utterance);
  });

  stopSpeakingButton.addEventListener("click", () => {
    window.speechSynthesis.cancel();
  });

  startVoiceNoteButton.addEventListener("click", startVoiceNote);
  stopVoiceNoteButton.addEventListener("click", stopVoiceNote);
}

async function loadProjects(preferredProjectId = null) {
  setStatus("Loading projects...");
  try {
    const response = await apiFetch("/api/projects");
    projects = Array.isArray(response.projects) ? response.projects : [];
    renderProjectList();

    const savedProjectId = preferredProjectId || localStorage.getItem(SELECTED_PROJECT_KEY);
    const nextProjectId =
      (savedProjectId && projects.find((project) => project.id === savedProjectId)?.id) ||
      projects[0]?.id ||
      null;

    if (nextProjectId) {
      await loadProject(nextProjectId);
    } else {
      currentProject = null;
      renderEmptyProject();
      setStatus("Create a project to start the workflow.");
    }
  } catch (error) {
    setStatus(readError(error));
  }
}

async function loadProject(projectId) {
  try {
    const response = await apiFetch(`/api/projects/${projectId}`);
    currentProject = response.project || null;
    localStorage.setItem(SELECTED_PROJECT_KEY, projectId);
    renderProjectList();
    renderProject();
    setStatus("Project loaded.");
  } catch (error) {
    setStatus(readError(error));
  }
}

function renderProjectList() {
  projectList.innerHTML = "";
  if (!projects.length) {
    projectList.innerHTML = '<div class="item-card"><strong>No projects yet</strong><p>Create one to scope papers, memory, and briefs.</p></div>';
    return;
  }

  projects.forEach((project) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `project-item${project.id === currentProject?.id ? " active" : ""}`;
    button.innerHTML = `
      <strong>${escapeHtml(project.name || "Untitled project")}</strong>
      <small>${escapeHtml(project.description || "No description provided.")}</small>
      <small>${project.paper_count || 0} papers, ${project.memory_count || 0} memory items</small>
    `;
    button.addEventListener("click", () => loadProject(project.id));
    projectList.appendChild(button);
  });
}

function renderEmptyProject() {
  selectedProjectName.textContent = "Select or create a project";
  selectedProjectDescription.textContent =
    "All papers, notes, contradictions, and briefs stay scoped to the selected project.";
  paperCount.textContent = "0";
  memoryCount.textContent = "0";
  contradictionCount.textContent = "0";
  briefCount.textContent = "0";
  paperList.innerHTML = "";
  memoryList.innerHTML = "";
  briefList.innerHTML = "";
  contradictionList.innerHTML = "";
  resetStructuredExtraction();
}

function renderProject() {
  if (!currentProject) {
    renderEmptyProject();
    return;
  }

  selectedProjectName.textContent = currentProject.name || "Untitled project";
  selectedProjectDescription.textContent =
    currentProject.description || "No description provided yet for this project.";

  const summary = summarizeProject(currentProject);
  paperCount.textContent = String(summary.paperCount);
  memoryCount.textContent = String(summary.memoryCount);
  contradictionCount.textContent = String(summary.contradictionCount);
  briefCount.textContent = String(summary.briefCount);

  renderPaperList(currentProject.papers || []);
  renderMemoryList(currentProject.memories || []);
  renderBriefList(currentProject.briefs || []);
  renderContradictionList(
    (currentProject.comparisons || []).filter((item) => item.relation === "contradict")
  );

  const latestPaper = currentProject.papers?.[currentProject.papers.length - 1];
  if (latestPaper?.extraction) {
    renderStructuredExtraction(latestPaper.extraction);
  } else {
    resetStructuredExtraction();
  }
}

function summarizeProject(project) {
  const papers = Array.isArray(project?.papers) ? project.papers : [];
  const memories = Array.isArray(project?.memories) ? project.memories : [];
  const comparisons = Array.isArray(project?.comparisons) ? project.comparisons : [];
  const briefs = Array.isArray(project?.briefs) ? project.briefs : [];
  return {
    paperCount: papers.length,
    memoryCount: memories.length,
    contradictionCount: comparisons.filter((item) => item.relation === "contradict").length,
    briefCount: briefs.length
  };
}

function renderPaperList(papers) {
  paperList.innerHTML = "";
  if (!papers.length) {
    paperList.innerHTML = '<div class="item-card"><strong>No sources yet</strong><p>Ingest pasted text, links, Google Drive docs, repo links, or voice notes.</p></div>';
    return;
  }

  [...papers].reverse().forEach((paper) => {
    const extraction = paper.extraction || {};
    const card = document.createElement("div");
    card.className = "item-card";
    card.innerHTML = `
      <strong>${escapeHtml(paper.title || "Untitled source")}</strong>
      <small>${escapeHtml((paper.source_type || "source").replaceAll("_", " "))}</small>
      <p>${escapeHtml(extraction.claim || "No claim extracted yet.")}</p>
    `;
    paperList.appendChild(card);
  });
}

function renderMemoryList(memories) {
  memoryList.innerHTML = "";
  if (!memories.length) {
    memoryList.innerHTML = '<div class="item-card"><strong>No saved memory</strong><p>Stored claims, gaps, and manual notes will appear here.</p></div>';
    return;
  }

  [...memories].reverse().slice(0, 12).forEach((memory) => {
    const card = document.createElement("div");
    card.className = "item-card";
    card.innerHTML = `
      <strong>${escapeHtml((memory.kind || "note").replaceAll("_", " "))}</strong>
      <small>${formatTimestamp(memory.created_at)}</small>
      <p>${escapeHtml(memory.content || "")}</p>
    `;
    memoryList.appendChild(card);
  });
}

function renderBriefList(briefs) {
  briefList.innerHTML = "";
  if (!briefs.length) {
    briefList.innerHTML = '<div class="item-card"><strong>No briefs yet</strong><p>Generate a morning brief after you have at least one source and some stored memory.</p></div>';
    return;
  }

  [...briefs].reverse().slice(0, 6).forEach((brief) => {
    const card = document.createElement("div");
    card.className = "item-card";
    card.innerHTML = `
      <strong>${formatTimestamp(brief.created_at)}</strong>
      <p>${escapeHtml(brief.summary || "")}</p>
    `;
    briefList.appendChild(card);
  });
}

function renderContradictionList(contradictions) {
  contradictionList.innerHTML = "";
  if (!contradictions.length) {
    contradictionList.innerHTML = '<div class="item-card"><strong>No contradictions</strong><p>When stored papers conflict, this panel will track the disagreements.</p></div>';
    return;
  }

  contradictions.slice().reverse().slice(0, 8).forEach((comparison) => {
    const paperTitle = comparison.paper_title || comparison.paper || "Paper";
    const otherPaperTitle = comparison.other_paper_title || comparison.other_paper || "Paper";
    const card = document.createElement("div");
    card.className = "item-card";
    card.innerHTML = `
      <strong>${escapeHtml(paperTitle)} vs ${escapeHtml(otherPaperTitle)}</strong>
      <p>${escapeHtml(comparison.reasoning || "")}</p>
    `;
    contradictionList.appendChild(card);
  });
}

async function runAction(action) {
  if (!currentProject && action !== "create") {
    setStatus("Select or create a project first.");
    return;
  }

  try {
    switch (action) {
      case "ask":
        await askProject();
        break;
      case "ingest":
        await ingestSource();
        break;
      case "compare":
        await compareLatest();
        break;
      case "contradictions":
        await loadContradictions();
        break;
      case "brief":
        await generateBrief();
        break;
      case "memory":
        await saveMemory();
        break;
      default:
        break;
    }
  } catch (error) {
    setStatus(readError(error));
  }
}

async function askProject() {
  const prompt = promptInput.value.trim();
  if (!prompt) {
    setStatus("Add a project question before asking Ara.");
    return;
  }

  setBusy(true);
  setStatus("Asking Ara with project context...");
  try {
    const response = await postWithOptionalFiles(
      `/api/projects/${currentProject.id}/ask`,
      { prompt },
      attachments
    );
    currentProject = response.project || currentProject;
    renderProject();
    renderWorkflowOutput("Project agent answer", response.output_text || "");
    clearAttachments();
    setStatus(
      response.used_local_fallback
        ? "Displayed local fallback because Ara returned a generic answer."
        : "Project answer ready."
    );
  } finally {
    setBusy(false);
  }
}

async function ingestSource() {
  const title = sourceTitleInput.value.trim();
  const pastedText = pastedTextInput.value.trim();
  const link = linkInput.value.trim();
  const transcript = voiceNoteInput.value.trim();

  if (!title && !pastedText && !link && !transcript && !attachments.length) {
    setStatus("Add source text, a link, a transcript, or an attachment before ingesting.");
    return;
  }

  setBusy(true);
  setStatus("Ingesting source into the project...");
  try {
    const response = await postWithOptionalFiles(
      `/api/projects/${currentProject.id}/ingest`,
      {
        title,
        pasted_text: pastedText,
        link,
        transcript
      },
      attachments
    );
    currentProject = response.project || currentProject;
    syncProjectSummary(response.summary);
    renderProject();
    renderWorkflowOutput("Paper intake", response.output_text || "");
    if (response.paper?.extraction) {
      renderStructuredExtraction(response.paper.extraction);
    }
    clearSourceInputs();
    clearAttachments();
    setStatus("Source ingested and stored in project memory.");
  } finally {
    setBusy(false);
  }
}

async function compareLatest() {
  setBusy(true);
  setStatus("Comparing the latest paper against project evidence...");
  try {
    const response = await apiFetch(`/api/projects/${currentProject.id}/compare`, { method: "POST" });
    currentProject = response.project || currentProject;
    syncProjectSummary(response.summary);
    renderProject();
    renderWorkflowOutput("Comparison review", response.output_text || "");
    setStatus("Comparison review ready.");
  } finally {
    setBusy(false);
  }
}

async function loadContradictions() {
  setBusy(true);
  setStatus("Loading contradiction report...");
  try {
    const response = await apiFetch(`/api/projects/${currentProject.id}/contradictions`);
    currentProject = response.project || currentProject;
    syncProjectSummary(response.summary);
    renderProject();
    renderWorkflowOutput("Contradiction finder", response.output_text || "");
    renderContradictionList(response.contradictions?.items || []);
    setStatus("Contradiction report ready.");
  } finally {
    setBusy(false);
  }
}

async function generateBrief() {
  setBusy(true);
  setStatus("Generating daily brief...");
  try {
    const response = await apiFetch(`/api/projects/${currentProject.id}/brief`, { method: "POST" });
    currentProject = response.project || currentProject;
    syncProjectSummary(response.summary);
    renderProject();
    renderWorkflowOutput("Daily what matters brief", response.output_text || "");
    setStatus("Daily brief generated.");
  } finally {
    setBusy(false);
  }
}

async function saveMemory() {
  const content = memoryInput.value.trim();
  if (!content) {
    setStatus("Add a memory note before saving.");
    return;
  }

  setBusy(true);
  setStatus("Saving project memory...");
  try {
    const response = await apiFetch(`/api/projects/${currentProject.id}/memory`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content })
    });
    currentProject = response.project || currentProject;
    syncProjectSummary(response.summary);
    memoryInput.value = "";
    renderProject();
    renderWorkflowOutput("Memory saved", response.output_text || "");
    setStatus("Project memory saved.");
  } finally {
    setBusy(false);
  }
}

function renderWorkflowOutput(title, markdown) {
  outputKind.textContent = title;
  latestAnswer = String(markdown || "").trim();
  output.innerHTML = latestAnswer ? renderMarkdown(latestAnswer) : "No output available.";
  output.classList.toggle("empty", !latestAnswer);
  speakButton.disabled = !latestAnswer;
  stopSpeakingButton.disabled = false;
}

function renderStructuredExtraction(extraction) {
  claimValue.textContent = extraction.claim || "No claim captured yet.";
  evidenceValue.textContent = extraction.evidence || "No evidence captured yet.";
  gapValue.textContent = extraction.gap || "No gap captured yet.";
  limitationValue.textContent = extraction.limitation || "No limitation captured yet.";
  relevanceValue.textContent = extraction.relevance_to_project || "No relevance captured yet.";
}

function resetStructuredExtraction() {
  claimValue.textContent = "Waiting for the first ingestion.";
  evidenceValue.textContent = "Waiting for the first ingestion.";
  gapValue.textContent = "Waiting for the first ingestion.";
  limitationValue.textContent = "Waiting for the first ingestion.";
  relevanceValue.textContent = "Waiting for the first ingestion.";
}

function syncProjectSummary(summary) {
  if (!summary || !currentProject) {
    return;
  }
  const match = projects.find((project) => project.id === currentProject.id);
  if (match) {
    Object.assign(match, {
      paper_count: summary.paper_count ?? match.paper_count,
      memory_count: summary.memory_count ?? match.memory_count,
      contradiction_count: summary.contradiction_count ?? match.contradiction_count,
      brief_count: summary.brief_count ?? match.brief_count,
      updated_at: summary.updated_at ?? match.updated_at
    });
  }
  renderProjectList();
}

function renderAttachmentList() {
  attachmentList.innerHTML = "";
  attachments.forEach((file, index) => {
    const item = document.createElement("li");
    item.innerHTML = `<span>${escapeHtml(file.name)} (${Math.round(file.size / 1024) || 1} KB)</span>`;
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.textContent = "Remove";
    removeButton.addEventListener("click", () => {
      attachments = attachments.filter((_, currentIndex) => currentIndex !== index);
      renderAttachmentList();
    });
    item.appendChild(removeButton);
    attachmentList.appendChild(item);
  });
}

function clearAttachments() {
  attachments = [];
  renderAttachmentList();
}

function clearSourceInputs() {
  sourceTitleInput.value = "";
  pastedTextInput.value = "";
  linkInput.value = "";
  voiceNoteInput.value = "";
}

function setBusy(isBusy) {
  askButton.disabled = isBusy;
  ingestButton.disabled = isBusy;
  compareButton.disabled = isBusy;
  contradictionButton.disabled = isBusy;
  briefButton.disabled = isBusy;
  saveMemoryButton.disabled = isBusy;
  fileInput.disabled = isBusy;
}

function setStatus(message) {
  statusLine.textContent = message;
}

function startVoiceNote() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    setStatus("This browser does not support voice-note transcription.");
    return;
  }

  if (!recognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      voiceNoteInput.value = transcript;
    };
    recognition.onend = () => {
      startVoiceNoteButton.disabled = false;
      stopVoiceNoteButton.disabled = true;
    };
  }

  recognition.start();
  startVoiceNoteButton.disabled = true;
  stopVoiceNoteButton.disabled = false;
  setStatus("Listening for a voice note...");
}

function stopVoiceNote() {
  if (recognition) {
    recognition.stop();
  }
  startVoiceNoteButton.disabled = false;
  stopVoiceNoteButton.disabled = true;
  setStatus("Voice note transcription stopped.");
}

async function postWithOptionalFiles(path, fields, files) {
  if (files.length) {
    const body = new FormData();
    Object.entries(fields).forEach(([key, value]) => {
      if (value) {
        body.append(key, value);
      }
    });
    files.forEach((file) => body.append("files", file, file.name));
    return apiFetch(path, { method: "POST", body });
  }

  return apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields)
  });
}

async function apiFetch(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { ok: false, error: text || "Invalid server response." };
  }

  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || "Request failed.");
  }

  return payload;
}

function renderMarkdown(markdown) {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let inList = false;

  for (const line of lines) {
    if (!line.trim()) {
      if (inList) {
        html.push("</ol>");
        inList = false;
      }
      continue;
    }

    if (line.startsWith("### ")) {
      if (inList) {
        html.push("</ol>");
        inList = false;
      }
      html.push(`<h3>${formatInline(line.slice(4))}</h3>`);
      continue;
    }

    const listMatch = line.match(/^\d+\.\s+(.*)$/);
    if (listMatch) {
      if (!inList) {
        html.push("<ol>");
        inList = true;
      }
      html.push(`<li>${formatInline(listMatch[1])}</li>`);
      continue;
    }

    if (inList) {
      html.push("</ol>");
      inList = false;
    }
    html.push(`<p>${formatInline(line)}</p>`);
  }

  if (inList) {
    html.push("</ol>");
  }

  return html.join("");
}

function formatInline(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function stripMarkdown(text) {
  return text
    .replace(/^###\s+/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/^\d+\.\s+/gm, "")
    .trim();
}

function formatTimestamp(value) {
  if (!value) {
    return "Unknown time";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function readError(error) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
