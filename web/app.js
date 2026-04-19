const promptInput = document.getElementById("prompt-input");
const statusLine = document.getElementById("status-line");
const attachmentList = document.getElementById("attachment-list");
const fileInput = document.getElementById("file-input");
const sendButton = document.getElementById("send-button");
const output = document.getElementById("output");
const runId = document.getElementById("run-id");
const runState = document.getElementById("run-state");
const speakButton = document.getElementById("speak-button");
const stopSpeakingButton = document.getElementById("stop-speaking");
const startDictationButton = document.getElementById("start-dictation");
const stopDictationButton = document.getElementById("stop-dictation");

let attachments = [];
let latestAnswer = "";
let recognition = null;

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    promptInput.value = chip.dataset.prompt || "";
    promptInput.focus();
  });
});

fileInput.addEventListener("change", (event) => {
  const files = Array.from(event.target.files || []);
  attachments = attachments.concat(files);
  renderAttachmentList();
  fileInput.value = "";
});

sendButton.addEventListener("click", async () => {
  const prompt = promptInput.value.trim();
  if (!prompt) {
    statusLine.textContent = "Add a prompt before sending.";
    return;
  }

  setBusy(true);
  statusLine.textContent = "Sending request to Ara...";

  try {
    const response = await sendPrompt(prompt, attachments);
    if (!response.ok) {
      throw new Error(response.error || "Request failed.");
    }

    latestAnswer = String(response.output_text || "").trim();
    runId.textContent = String(response.raw_result?.run_id || "-");
    runState.textContent = response.used_local_fallback ? "local fallback" : String(response.raw_result?.result?.state || "completed");
    output.innerHTML = renderMarkdown(latestAnswer);
    output.classList.remove("empty");
    speakButton.disabled = !latestAnswer;
    stopSpeakingButton.disabled = false;
    statusLine.textContent = response.used_local_fallback
      ? "Displayed local fallback while Ara finishes behaving."
      : "Ara response ready.";
  } catch (error) {
    statusLine.textContent = error instanceof Error ? error.message : "Something went wrong.";
  } finally {
    setBusy(false);
  }
});

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

startDictationButton.addEventListener("click", () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    statusLine.textContent = "This browser does not support speech dictation.";
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
      promptInput.value = transcript;
    };
    recognition.onend = () => {
      startDictationButton.disabled = false;
      stopDictationButton.disabled = true;
    };
  }

  recognition.start();
  startDictationButton.disabled = true;
  stopDictationButton.disabled = false;
  statusLine.textContent = "Listening...";
});

stopDictationButton.addEventListener("click", () => {
  if (recognition) {
    recognition.stop();
  }
  startDictationButton.disabled = false;
  stopDictationButton.disabled = true;
  statusLine.textContent = "Dictation stopped.";
});

function setBusy(isBusy) {
  sendButton.disabled = isBusy;
  fileInput.disabled = isBusy;
  startDictationButton.disabled = isBusy || !!(recognition && startDictationButton.disabled);
}

function renderAttachmentList() {
  attachmentList.innerHTML = "";
  attachments.forEach((file, index) => {
    const item = document.createElement("li");
    item.innerHTML = `<span>${escapeHtml(file.name)} (${Math.round(file.size / 1024) || 1} KB)</span>`;
    const removeButton = document.createElement("button");
    removeButton.textContent = "Remove";
    removeButton.addEventListener("click", () => {
      attachments = attachments.filter((_, currentIndex) => currentIndex !== index);
      renderAttachmentList();
    });
    item.appendChild(removeButton);
    attachmentList.appendChild(item);
  });
}

async function sendPrompt(prompt, files) {
  if (files.length > 0) {
    const body = new FormData();
    body.append("prompt", prompt);
    files.forEach((file) => body.append("files", file, file.name));
    const response = await fetch("/api/research", { method: "POST", body });
    return readJson(response);
  }

  const response = await fetch("/api/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt })
  });
  return readJson(response);
}

async function readJson(response) {
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { ok: false, error: text || "Invalid server response." };
  }
  if (!response.ok) {
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

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
