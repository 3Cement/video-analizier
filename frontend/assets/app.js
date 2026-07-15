const state = {
  sources: [],
  selectedId: null,
  pollTimer: null,
  summaryText: "",
  videoUrl: "",
};

const el = {
  statusLine: document.getElementById("status-line"),
  errorBox: document.getElementById("error-box"),
  steps: document.getElementById("steps"),
  result: document.getElementById("result"),
  resultTitle: document.getElementById("result-title"),
  resultMeta: document.getElementById("result-meta"),
  resultLink: document.getElementById("result-link"),
  summaryBox: document.getElementById("summary-box"),
  transcriptPre: document.getElementById("transcript-pre"),
  answerBox: document.getElementById("answer-box"),
  askForm: document.getElementById("ask-form"),
  sourceList: document.getElementById("source-list"),
  submitBtn: document.getElementById("submit-btn"),
  youtubeUrl: document.getElementById("youtube-url"),
  retryBtn: document.getElementById("retry-btn"),
  forceAsrBtn: document.getElementById("force-asr-btn"),
  deleteBtn: document.getElementById("delete-btn"),
  llmToggle: document.getElementById("llm-toggle"),
  llmSettings: document.getElementById("llm-settings"),
  llmForm: document.getElementById("llm-form"),
  llmProvider: document.getElementById("llm-provider"),
  llmStatusLine: document.getElementById("llm-status-line"),
};

function formatTs(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function parseTimestampToSeconds(raw) {
  const parts = raw.split(":").map((p) => parseInt(p, 10));
  if (parts.some(Number.isNaN)) return 0;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] || 0;
}

function youtubeTimestampUrl(baseUrl, seconds) {
  if (!baseUrl) return null;
  const sep = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${sep}t=${Math.max(0, Math.floor(seconds))}s`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function linkifyTimestamps(html, videoUrl) {
  if (!videoUrl) return html;
  return html.replace(
    /\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g,
    (_match, ts) => {
      const seconds = parseTimestampToSeconds(ts);
      const href = youtubeTimestampUrl(videoUrl, seconds);
      return `<a class="ts-link" href="${href}" target="_blank" rel="noreferrer">[${ts}]</a>`;
    }
  );
}

function inlineMarkdown(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function renderMarkdown(text, videoUrl = "") {
  if (!text) return "<p class='muted'>Brak treści.</p>";
  const lines = text.split("\n");
  const out = [];
  let inList = false;

  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line.trim()) {
      closeList();
      continue;
    }
    if (line.startsWith("### ")) {
      closeList();
      out.push(`<h3>${linkifyTimestamps(inlineMarkdown(line.slice(4)), videoUrl)}</h3>`);
      continue;
    }
    if (line.startsWith("## ")) {
      closeList();
      out.push(`<h2>${linkifyTimestamps(inlineMarkdown(line.slice(3)), videoUrl)}</h2>`);
      continue;
    }
    if (line.startsWith("# ")) {
      closeList();
      out.push(`<h1>${linkifyTimestamps(inlineMarkdown(line.slice(2)), videoUrl)}</h1>`);
      continue;
    }
    if (line.startsWith("- ")) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${linkifyTimestamps(inlineMarkdown(line.slice(2)), videoUrl)}</li>`);
      continue;
    }
    closeList();
    out.push(`<p>${linkifyTimestamps(inlineMarkdown(line), videoUrl)}</p>`);
  }
  closeList();
  return out.join("");
}

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch (_) {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

function setStatus(text) {
  el.statusLine.textContent = text;
}

function setError(detail) {
  if (!detail) {
    el.errorBox.hidden = true;
    el.errorBox.textContent = "";
    return;
  }
  el.errorBox.hidden = false;
  el.errorBox.textContent = detail;
}

function setBusy(busy) {
  el.submitBtn.disabled = busy;
  el.submitBtn.textContent = busy ? "Analizuję…" : "Podsumuj film";
}

function updateSteps(status) {
  const order = ["downloading", "transcribing", "summarizing", "ready"];
  const idx = order.indexOf(status);
  el.steps.hidden = false;
  el.steps.querySelectorAll("li").forEach((li) => {
    const step = li.dataset.step;
    const stepIdx = order.indexOf(step);
    li.classList.toggle("active", step === status);
    li.classList.toggle("done", idx >= 0 && stepIdx >= 0 && stepIdx < idx);
    if (status === "ready" && step === "ready") li.classList.add("done");
    if (status === "failed") li.classList.remove("active", "done");
  });
}

function renderSources() {
  el.sourceList.innerHTML = "";
  if (!state.sources.length) {
    el.sourceList.innerHTML = "<li class='muted'>Brak analiz — wklej pierwszy link powyżej.</li>";
    return;
  }
  for (const source of state.sources) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `source-item${source.id === state.selectedId ? " active" : ""}`;
    btn.innerHTML = `<strong>${escapeHtml(source.title || "Bez tytułu")}</strong>
      <span class="muted">${source.source_type} · ${source.status}${
        source.segment_count ? ` · ${source.segment_count} seg.` : ""
      }</span>`;
    btn.addEventListener("click", () => selectSource(source.id));
    li.appendChild(btn);
    el.sourceList.appendChild(li);
  }
}

async function refreshSources() {
  state.sources = await api("/sources");
  renderSources();
  const busy = state.sources.find((s) => !["ready", "failed"].includes(s.status));
  if (busy) {
    setStatus(`Przetwarzanie: ${busy.status}`);
    updateSteps(busy.status);
    setBusy(true);
    schedulePoll();
  } else {
    setBusy(false);
  }
}

function schedulePoll() {
  if (state.pollTimer) return;
  state.pollTimer = setTimeout(async () => {
    state.pollTimer = null;
    try {
      await refreshSources();
      if (state.selectedId) await selectSource(state.selectedId, false);
    } catch (err) {
      setStatus(err.message);
      setBusy(false);
    }
  }, 2000);
}

function renderTranscript(segments, videoUrl) {
  el.transcriptPre.innerHTML = "";
  for (const seg of segments || []) {
    const line = document.createElement("div");
    line.className = "transcript-line";
    const href = youtubeTimestampUrl(videoUrl, seg.start);
    if (href) {
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.className = "ts-link";
      link.textContent = `[${formatTs(seg.start)}]`;
      line.appendChild(link);
      line.appendChild(document.createTextNode(` ${seg.text}`));
    } else {
      line.textContent = `[${formatTs(seg.start)}] ${seg.text}`;
    }
    el.transcriptPre.appendChild(line);
  }
}

async function selectSource(id, resetAnswer = true) {
  state.selectedId = id;
  renderSources();
  const detail = await api(`/sources/${id}`);
  el.result.hidden = false;
  el.resultTitle.textContent = detail.title || "Bez tytułu";
  el.resultMeta.textContent = [
    detail.transcript_method || "brak metody",
    detail.duration_seconds ? `${Math.round(detail.duration_seconds / 60)} min` : null,
    detail.status,
  ]
    .filter(Boolean)
    .join(" · ");

  state.videoUrl = detail.url || "";
  if (detail.url) {
    el.resultLink.href = detail.url;
    el.resultLink.hidden = false;
  } else {
    el.resultLink.hidden = true;
  }

  const latestSummary = (detail.summaries || []).at(-1);
  state.summaryText = latestSummary?.content || "";
  el.summaryBox.innerHTML =
    renderMarkdown(state.summaryText, state.videoUrl) ||
    (detail.status === "ready"
      ? "<p class='muted'>Brak podsumowania — spróbuj przetworzyć ponownie.</p>"
      : "<p class='muted'>Podsumowanie pojawi się po zakończeniu analizy…</p>");

  renderTranscript(detail.segments || [], state.videoUrl);

  if (resetAnswer) {
    el.answerBox.hidden = true;
    el.answerBox.innerHTML = "";
    el.askForm.hidden = true;
  }

  el.retryBtn.hidden = detail.status !== "failed";
  el.forceAsrBtn.hidden = detail.status !== "ready" || detail.source_type !== "youtube";
  el.deleteBtn.hidden = false;

  if (detail.status === "failed") {
    const hint = detail.error_hint ? ` ${detail.error_hint}` : "";
    setError(`${detail.error_code || "error"}: ${detail.error || "Analiza nie powiodła się."}${hint}`);
    setStatus("Analiza nie powiodła się.");
    setBusy(false);
  } else {
    setError(null);
  }

  updateSteps(detail.status);
  if (detail.status === "ready") {
    setStatus("Podsumowanie gotowe.");
    setBusy(false);
  } else if (detail.status !== "failed") {
    setStatus(`Przetwarzanie: ${detail.status}`);
    setBusy(true);
    schedulePoll();
  }
}

async function reprocessSource({ forceAsr = false } = {}) {
  if (!state.selectedId) return;
  try {
    setBusy(true);
    setStatus(forceAsr ? "Ponowna transkrypcja ASR…" : "Ponowna analiza…");
    setError(null);
    await api(`/sources/${state.selectedId}/reprocess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prefer_captions: !forceAsr,
        force_asr: forceAsr,
        auto_summarize: true,
      }),
    });
    await refreshSources();
    await selectSource(state.selectedId);
  } catch (err) {
    setStatus(err.message);
    setBusy(false);
  }
}

async function deleteSelectedSource() {
  if (!state.selectedId) return;
  if (!window.confirm("Usunąć tę analizę?")) return;
  try {
    await api(`/sources/${state.selectedId}`, { method: "DELETE" });
    state.selectedId = null;
    el.result.hidden = true;
    setError(null);
    setStatus("Analiza usunięta.");
    await refreshSources();
  } catch (err) {
    setStatus(err.message);
  }
}

document.getElementById("youtube-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    setBusy(true);
    setStatus("Startuję analizę YouTube…");
    setError(null);
    el.steps.hidden = false;
    updateSteps("downloading");
    const created = await api("/sources/youtube", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: el.youtubeUrl.value.trim(),
        language: "pl",
        auto_summarize: true,
      }),
    });
    state.selectedId = created.id;
    await refreshSources();
    await selectSource(created.id);
  } catch (err) {
    setStatus(err.message);
    setBusy(false);
  }
});

document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const file = document.getElementById("upload-file").files[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    body.append("language", "pl");
    body.append("auto_summarize", "true");
    setBusy(true);
    setStatus("Wgrywanie pliku…");
    setError(null);
    const created = await api("/sources/upload", { method: "POST", body });
    state.selectedId = created.id;
    await refreshSources();
    await selectSource(created.id);
  } catch (err) {
    setStatus(err.message);
    setBusy(false);
  }
});

document.getElementById("text-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    setBusy(true);
    setError(null);
    const created = await api("/sources/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: document.getElementById("text-title").value.trim() || "Notatka",
        text: document.getElementById("text-body").value,
        language: "pl",
        auto_summarize: true,
      }),
    });
    state.selectedId = created.id;
    await refreshSources();
    await selectSource(created.id);
  } catch (err) {
    setStatus(err.message);
    setBusy(false);
  }
});

document.getElementById("ask-toggle").addEventListener("click", () => {
  el.askForm.hidden = !el.askForm.hidden;
});

document.getElementById("transcript-toggle").addEventListener("click", () => {
  const box = document.getElementById("transcript-box");
  box.open = !box.open;
});

document.getElementById("copy-summary").addEventListener("click", async () => {
  if (!state.summaryText) {
    setStatus("Brak podsumowania do skopiowania.");
    return;
  }
  try {
    await navigator.clipboard.writeText(state.summaryText);
    setStatus("Podsumowanie skopiowane.");
  } catch (_) {
    setStatus("Nie udało się skopiować do schowka.");
  }
});

document.getElementById("ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selectedId) return;
  try {
    setStatus("Szukam odpowiedzi w materiale…");
    const data = await api("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_id: state.selectedId,
        question: document.getElementById("ask-input").value.trim(),
      }),
    });
    const cites = (data.citations || [])
      .map((c) => `[${c.timestamp}] ${c.text}`)
      .join("\n");
    el.answerBox.hidden = false;
    el.answerBox.innerHTML = `${renderMarkdown(data.answer, state.videoUrl)}<p><strong>Cytowania:</strong></p><pre class="cites">${escapeHtml(cites || "(brak)")}</pre>`;
    setStatus("Odpowiedź gotowa.");
  } catch (err) {
    setStatus(err.message);
  }
});

el.retryBtn.addEventListener("click", () => reprocessSource({ forceAsr: false }));
el.forceAsrBtn.addEventListener("click", () => reprocessSource({ forceAsr: true }));
el.deleteBtn.addEventListener("click", () => deleteSelectedSource());

document.getElementById("refresh-btn").addEventListener("click", () => {
  refreshSources().catch((e) => setStatus(e.message));
});

function syncProviderFields() {
  const provider = el.llmProvider.value;
  document.querySelectorAll(".provider-fields").forEach((block) => {
    block.hidden = block.dataset.provider !== provider;
  });
}

async function loadLlmStatus() {
  const status = await api("/llm/status");
  el.llmProvider.value = status.provider || "openai";
  document.getElementById("openai-model").value = status.models?.openai || "";
  document.getElementById("anthropic-model").value = status.models?.anthropic || "";
  document.getElementById("cursor-model").value = status.models?.cursor || "";
  document.getElementById("cursor-base-url").value = status.base_urls?.cursor || "";
  syncProviderFields();
  const flags = status.configured || {};
  const labels = [
    flags.openai ? "OpenAI ✓" : "OpenAI —",
    flags.anthropic ? "Anthropic ✓" : "Anthropic —",
    flags.cursor ? "Cursor ✓" : "Cursor —",
  ];
  el.llmStatusLine.textContent = `Aktywny: ${status.provider}. ${labels.join(" · ")}. Klucze nie są pokazywane po zapisaniu.`;
}

el.llmToggle.addEventListener("click", () => {
  el.llmSettings.open = !el.llmSettings.open;
});

el.llmProvider.addEventListener("change", syncProviderFields);

el.llmForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const provider = el.llmProvider.value;
  const payload = { llm_provider: provider };
  if (provider === "openai") {
    const key = document.getElementById("openai-api-key").value.trim();
    const model = document.getElementById("openai-model").value.trim();
    if (key) payload.openai_api_key = key;
    if (model) payload.openai_model = model;
  } else if (provider === "anthropic") {
    const key = document.getElementById("anthropic-api-key").value.trim();
    const model = document.getElementById("anthropic-model").value.trim();
    if (key) payload.anthropic_api_key = key;
    if (model) payload.anthropic_model = model;
  } else {
    const key = document.getElementById("cursor-api-key").value.trim();
    const model = document.getElementById("cursor-model").value.trim();
    const base = document.getElementById("cursor-base-url").value.trim();
    if (key) payload.cursor_api_key = key;
    if (model) payload.cursor_model = model;
    if (base) payload.cursor_base_url = base;
  }
  try {
    await api("/llm/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    document.getElementById("openai-api-key").value = "";
    document.getElementById("anthropic-api-key").value = "";
    document.getElementById("cursor-api-key").value = "";
    await loadLlmStatus();
    setStatus(`Zapisano ustawienia LLM (${provider}).`);
  } catch (err) {
    setStatus(err.message);
  }
});

refreshSources()
  .then(() => loadLlmStatus())
  .then(() => {
    const ready = state.sources.find((s) => s.status === "ready");
    if (ready) return selectSource(ready.id);
  })
  .catch((e) => setStatus(e.message));
