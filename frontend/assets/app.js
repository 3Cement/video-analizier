const state = {
  sources: [],
  selectedId: null,
  pollTimer: null,
  summaryText: "",
  videoUrl: "",
  lastDetailKey: "",
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
  shareBtn: document.getElementById("share-btn"),
  extractFactsBtn: document.getElementById("extract-facts-btn"),
  summarizeBtn: document.getElementById("summarize-btn"),
  exportMdBtn: document.getElementById("export-md-btn"),
  shareUrlLine: document.getElementById("share-url-line"),
  quotaLine: document.getElementById("quota-line"),
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

function authHeaders() { return {}; }

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  options = { ...options, headers, credentials: "same-origin" };
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

async function pollJobStatus() {
  if (!state.selectedId) {
    await refreshSources();
    return;
  }
  const status = await api(`/sources/${state.selectedId}/status`);
  updateSteps(status.status);
      if (typeof status.progress_pct === "number") setProgress(status.progress_pct, status.progress_message || status.progress);
  const item = state.sources.find((s) => s.id === state.selectedId);
  if (item) item.status = status.status;
  renderSources();

  if (status.status === "ready" || status.status === "failed") {
    await refreshSources();
    await selectSource(state.selectedId, false);
    return;
  }
  setStatus(`Przetwarzanie: ${status.status}`);
  setBusy(true);
  schedulePoll();
}

function schedulePoll() {
  if (state.pollTimer) return;
  state.pollTimer = setTimeout(async () => {
    state.pollTimer = null;
    try {
      await pollJobStatus();
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

  const briefingSummary = (detail.summaries || []).find((s) => s.kind === "briefing");
  const factsSummary = (detail.summaries || []).find((s) => s.kind === "facts");
  let summaryText = "";
  if (briefingSummary && factsSummary) {
    summaryText = `${briefingSummary.content}

---

${factsSummary.content}`;
  } else {
    summaryText = (briefingSummary || factsSummary || (detail.summaries || []).at(-1))?.content || "";
  }
  state.summaryText = summaryText;
  const detailKey = `${detail.id}:${detail.status}:${detail.updated_at}:${state.summaryText.length}:${(detail.segments || []).length}`;
  if (detailKey !== state.lastDetailKey) {
    state.lastDetailKey = detailKey;
    el.summaryBox.innerHTML =
      renderMarkdown(state.summaryText, state.videoUrl) ||
      (detail.status === "ready"
        ? "<p class='muted'>Brak podsumowania — spróbuj przetworzyć ponownie.</p>"
        : "<p class='muted'>Podsumowanie pojawi się po zakończeniu analizy…</p>");
    renderTranscript(detail.segments || [], state.videoUrl);
  }

  if (resetAnswer) {
    el.answerBox.hidden = true;
    el.answerBox.innerHTML = "";
    el.askForm.hidden = true;
  }

  el.retryBtn.hidden = detail.status !== "failed";
  el.forceAsrBtn.hidden = detail.status !== "ready" || detail.source_type !== "youtube";
  el.shareBtn.hidden = detail.status !== "ready";
  el.exportMdBtn.hidden = detail.status !== "ready";
  if (el.extractFactsBtn) el.extractFactsBtn.hidden = detail.status !== "ready";
  if (el.summarizeBtn) el.summarizeBtn.hidden = detail.status !== "ready";
  const docxBtn = document.getElementById("export-docx-btn");
  if (docxBtn) docxBtn.hidden = detail.status !== "ready";
  const tagForm = document.getElementById("tag-form");
  const noteForm = document.getElementById("note-form");
  if (tagForm) tagForm.hidden = detail.status !== "ready";
  if (noteForm) noteForm.hidden = detail.status !== "ready";
  if (detail.status === "ready") loadNotes(detail.id);
  const tagsLine = document.getElementById("tags-line");
  if (tagsLine) tagsLine.textContent = (detail.tags || []).map((x) => `#${x}`).join(" ");
  el.deleteBtn.hidden = false;
  if (detail.share_slug) {
    el.shareUrlLine.hidden = false;
    el.shareUrlLine.innerHTML = `Publiczny link: <a class="ts-link" href="/s/${detail.share_slug}" target="_blank" rel="noreferrer">/s/${detail.share_slug}</a>`;
  } else {
    el.shareUrlLine.hidden = true;
    el.shareUrlLine.textContent = "";
  }

  if (detail.status === "failed") {
    const hint = detail.error_hint ? ` ${detail.error_hint}` : "";
    setError(`${detail.error_code || "error"}: ${detail.error || "Analiza nie powiodła się."}${hint}`);
    setStatus("Analiza nie powiodła się.");
    setBusy(false);
  } else {
    setError(null);
  }

  updateSteps(detail.status);
  if (typeof detail.progress === "number") setProgress(detail.progress, detail.progress_message);
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
        auto_summarize: wantsAutoSummarize(),
      }),
    });
    await refreshSources();
    await selectSource(state.selectedId);
  } catch (err) {
    setStatus(err.message);
    setBusy(false);
  }
}

function wantsAutoSummarize() {
  const box = document.getElementById("transcript-only");
  return !(box && box.checked);
}

function isYoutubeUrl(url) {
  return /(?:youtube\.com|youtu\.be)\//i.test(url || "");
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
    const url = el.youtubeUrl.value.trim();
    const auto_summarize = wantsAutoSummarize();
    const endpoint = isYoutubeUrl(url) ? "/sources/youtube" : "/sources/url";
    setStatus(isYoutubeUrl(url) ? "Startuję analizę YouTube…" : "Startuję analizę URL…");
    const created = await api(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        language: "pl",
        auto_summarize,
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
    body.append("auto_summarize", wantsAutoSummarize() ? "true" : "false");
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

async function loadQuota() {
  try {
    const q = await api("/quota");
    el.quotaLine.textContent = `Źródła: ${q.sources.used}/${q.sources.limit} · pytania: ${q.questions.used}/${q.questions.limit}`;
  } catch (_) {
    el.quotaLine.textContent = "";
  }
}

el.shareBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  try {
    const data = await api(`/sources/${state.selectedId}/share`, { method: "POST" });
    el.shareUrlLine.hidden = false;
    el.shareUrlLine.innerHTML = `Publiczny link: <a class="ts-link" href="${data.share_url}" target="_blank" rel="noreferrer">${data.share_url}</a>`;
    setStatus("Link udostępniania gotowy.");
    await refreshSources();
  } catch (err) {
    setStatus(err.message);
  }
});

el.exportMdBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  try {
    const res = await fetch(`/api/sources/${state.selectedId}/export.md`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Nie udało się wyeksportować");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `source-${state.selectedId}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus("Eksport Markdown pobrany.");
  } catch (err) {
    setStatus(err.message);
  }
});

document.getElementById("playlist-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const raw = document.getElementById("playlist-urls").value;
  const urls = raw.split(/\n+/).map((u) => u.trim()).filter(Boolean);
  if (!urls.length) return;
  try {
    setBusy(true);
    setStatus(`Dodaję playlistę (${urls.length})…`);
    const created = await api("/sources/playlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls, language: "pl", auto_summarize: wantsAutoSummarize() }),
    });
    state.selectedId = created[0]?.id || state.selectedId;
    await loadQuota();
    await refreshSources();
    if (state.selectedId) await selectSource(state.selectedId);
  } catch (err) {
    setStatus(err.message);
    setBusy(false);
  }
});

refreshSources()
  .then(() => loadQuota())
  .then(() => {
    const ready = state.sources.find((s) => s.status === "ready");
    if (ready) return selectSource(ready.id);
  })
  .catch((e) => setStatus(e.message));


document.getElementById("article-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    setBusy(true);
    setStatus("Pobieranie artykułu…");
    setError(null);
    const created = await api("/sources/article", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: document.getElementById("article-url").value.trim(),
        language: "pl",
        auto_summarize: wantsAutoSummarize(),
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

document.getElementById("podcast-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const url = document.getElementById("podcast-url").value.trim();
    const maxEpisodes = Number(document.getElementById("podcast-max").value || 3);
    const looksRss = /rss|feed|atom|xml/i.test(url);
    setBusy(true);
    setStatus(looksRss ? "Parsowanie RSS podcastu…" : "Pobieranie odcinka…");
    setError(null);
    let created;
    if (looksRss) {
      const items = await api("/sources/podcast/rss", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feed_url: url,
          max_episodes: maxEpisodes,
          language: "pl",
          auto_summarize: wantsAutoSummarize(),
        }),
      });
      created = items[0];
    } else {
      created = await api("/sources/podcast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          language: "pl",
          auto_summarize: wantsAutoSummarize(),
        }),
      });
    }
    if (!created) throw new Error("Nie utworzono źródła podcastu");
    state.selectedId = created.id;
    await refreshSources();
    await selectSource(created.id);
  } catch (err) {
    setStatus(err.message);
    setBusy(false);
  }
});

async function runSummarizeKind(kind) {
  if (!state.selectedId) return;
  try {
    setBusy(true);
    setStatus(kind === "facts" ? "Wyciąganie danych…" : "Generowanie podsumowania…");
    await api(`/sources/${state.selectedId}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind }),
    });
    await selectSource(state.selectedId);
    setStatus(kind === "facts" ? "Ekstrakcja danych gotowa." : "Podsumowanie gotowe.");
  } catch (err) {
    setStatus(err.message);
  } finally {
    setBusy(false);
  }
}

document.getElementById("extract-facts-btn")?.addEventListener("click", () => runSummarizeKind("facts"));
document.getElementById("summarize-btn")?.addEventListener("click", () => runSummarizeKind("briefing"));


function setProgress(pct, label) {
  const wrap = document.getElementById("progress-wrap");
  const bar = document.getElementById("progress-bar");
  const lab = document.getElementById("progress-label");
  if (!wrap || !bar) return;
  if (pct == null) {
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;
  bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  if (lab) lab.textContent = label || `${Math.round(pct)}%`;
}

const _origPoll = typeof pollJobStatus === "function" ? pollJobStatus : null;

document.getElementById("auth-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("auth-email").value.trim();
  const password = document.getElementById("auth-password").value;
  try {
    const data = await api("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    document.getElementById("auth-status").textContent = `Zalogowano: ${data.email}`;
    document.getElementById("auth-summary").textContent = `Konto: ${data.email}`;
    await refreshSources();
    await loadCollections();
  } catch (err) {
    document.getElementById("auth-status").textContent = err.message;
  }
});

document.getElementById("auth-register")?.addEventListener("click", async () => {
  const email = document.getElementById("auth-email").value.trim();
  const password = document.getElementById("auth-password").value;
  try {
    const turnstileToken = window.turnstile?.getResponse() || "";
    await api("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, turnstile_token: turnstileToken }),
    });
    document.getElementById("auth-status").textContent = "Sprawdź skrzynkę i potwierdź adres e-mail.";
    window.turnstile?.reset();
  } catch (err) {
    document.getElementById("auth-status").textContent = err.message;
  }
});

document.getElementById("auth-logout")?.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch (_) {
    /* ignore */
  }
  document.getElementById("auth-status").textContent = "Wylogowano.";
  document.getElementById("auth-summary").textContent = "Konto";
  state.sources = [];
  renderSourceList();
});

document.getElementById("search-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = document.getElementById("search-q").value.trim();
  const list = document.getElementById("search-hits");
  if (!q) {
    list.hidden = true;
    return;
  }
  try {
    const data = await api(`/library/search?q=${encodeURIComponent(q)}`);
    list.hidden = false;
    list.innerHTML = (data.hits || [])
      .map(
        (h) => `<li><button type="button" data-id="${h.source_id}" class="source-btn">
          <strong>${escapeHtml(h.title || "Bez tytułu")}</strong>
          <span class="muted">${escapeHtml(h.match_kind)} · ${escapeHtml(h.source_type)}</span>
          <span>${escapeHtml(h.snippet || "")}</span>
        </button></li>`
      )
      .join("") || "<li class='muted'>Brak wyników</li>";
    list.querySelectorAll("button[data-id]").forEach((btn) => {
      btn.addEventListener("click", () => selectSource(Number(btn.dataset.id)));
    });
  } catch (err) {
    setStatus(err.message);
  }
});

async function loadCollections() {
  const list = document.getElementById("collection-list");
  if (!list) return;
  try {
    const rows = await api("/library/collections");
    list.innerHTML = rows
      .map((c) => `<li title="${c.source_ids.length} źródeł">${escapeHtml(c.name)} (${c.source_ids.length})</li>`)
      .join("");
  } catch (_) {
    list.innerHTML = "";
  }
}

document.getElementById("collection-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("collection-name").value.trim();
  if (!name) return;
  try {
    await api("/library/collections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    document.getElementById("collection-name").value = "";
    await loadCollections();
  } catch (err) {
    setStatus(err.message);
  }
});

document.getElementById("tag-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selectedId) return;
  const name = document.getElementById("tag-name").value.trim();
  if (!name) return;
  try {
    const tags = await api(`/library/sources/${state.selectedId}/tags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    document.getElementById("tags-line").textContent = tags.map((t) => `#${t.name}`).join(" ");
    document.getElementById("tag-name").value = "";
  } catch (err) {
    setStatus(err.message);
  }
});

document.getElementById("note-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selectedId) return;
  const body = document.getElementById("note-body").value.trim();
  if (!body) return;
  try {
    await api(`/library/sources/${state.selectedId}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body }),
    });
    document.getElementById("note-body").value = "";
    await loadNotes(state.selectedId);
  } catch (err) {
    setStatus(err.message);
  }
});

async function loadNotes(sourceId) {
  const list = document.getElementById("notes-list");
  if (!list) return;
  try {
    const notes = await api(`/library/sources/${sourceId}/notes`);
    list.innerHTML = notes.map((n) => `<li>${escapeHtml(n.body)}</li>`).join("");
  } catch (_) {
    list.innerHTML = "";
  }
}

document.getElementById("export-docx-btn")?.addEventListener("click", async () => {
  if (!state.selectedId) return;
  const headers = authHeaders();
  const res = await fetch(`/api/sources/${state.selectedId}/export.docx`, { headers });
  if (!res.ok) {
    setStatus("Eksport DOCX nieudany");
    return;
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `source-${state.selectedId}.docx`;
  a.click();
});

api("/auth/me").then((me) => {
  document.getElementById("auth-summary").textContent = `Konto: ${me.email}`;
  document.getElementById("auth-status").textContent = `Zalogowano: ${me.email}`;
  return loadCollections();
}).catch(() => {});

api("/auth/config").then((config) => {
  if (!config.turnstile_site_key) return;
  const render = () => {
    if (window.turnstile) window.turnstile.render("#turnstile-widget", { sitekey: config.turnstile_site_key });
    else window.setTimeout(render, 100);
  };
  render();
}).catch(() => {});


document.getElementById("password-reset-request")?.addEventListener("click", async () => {
  const email = document.getElementById("auth-email").value.trim();
  const status = document.getElementById("auth-status");
  try {
    await api("/auth/password-reset/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    status.textContent = "Jeśli konto istnieje, wyślemy instrukcję resetu.";
  } catch (err) {
    status.textContent = err.message;
  }
});

document.getElementById("password-reset-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const token = document.getElementById("reset-token").value.trim();
  const newPassword = document.getElementById("reset-password").value;
  const status = document.getElementById("auth-status");
  try {
    const data = await api("/auth/password-reset/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: newPassword }),
    });
    status.textContent = `Hasło zmienione. Zalogowano: ${data.email}`;
    document.getElementById("auth-summary").textContent = `Konto: ${data.email}`;
    await refreshSources();
  } catch (err) {
    status.textContent = err.message;
  }
});

const params = new URLSearchParams(window.location.search);
if (params.get("reset_token")) {
  const input = document.getElementById("reset-token");
  if (input) input.value = params.get("reset_token");
  const box = document.querySelector(".auth-box");
  if (box) box.open = true;
}
