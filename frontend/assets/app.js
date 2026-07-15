const state = {
  sources: [],
  selectedId: null,
  pollTimer: null,
  summaryText: "",
};

const el = {
  statusLine: document.getElementById("status-line"),
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
};

function formatTs(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
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
    btn.innerHTML = `<strong>${source.title || "Bez tytułu"}</strong>
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
    detail.error ? `błąd: ${detail.error}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  if (detail.url) {
    el.resultLink.href = detail.url;
    el.resultLink.hidden = false;
  } else {
    el.resultLink.hidden = true;
  }

  const latestSummary = (detail.summaries || []).at(-1);
  state.summaryText = latestSummary?.content || "";
  el.summaryBox.textContent =
    state.summaryText ||
    (detail.status === "ready"
      ? "Brak podsumowania — spróbuj przetworzyć ponownie."
      : "Podsumowanie pojawi się po zakończeniu analizy…");

  el.transcriptPre.textContent = (detail.segments || [])
    .map((s) => `[${formatTs(s.start)}] ${s.text}`)
    .join("\n");

  if (resetAnswer) {
    el.answerBox.hidden = true;
    el.answerBox.textContent = "";
    el.askForm.hidden = true;
  }

  updateSteps(detail.status);
  if (detail.status === "ready") {
    setStatus("Podsumowanie gotowe.");
    setBusy(false);
  } else if (detail.status === "failed") {
    setStatus(detail.error || "Analiza nie powiodła się.");
    setBusy(false);
  } else {
    setStatus(`Przetwarzanie: ${detail.status}`);
    setBusy(true);
    schedulePoll();
  }
}

document.getElementById("youtube-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    setBusy(true);
    setStatus("Startuję analizę YouTube…");
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
    el.answerBox.textContent = `${data.answer}\n\nCytowania:\n${cites || "(brak)"}`;
    setStatus("Odpowiedź gotowa.");
  } catch (err) {
    setStatus(err.message);
  }
});

document.getElementById("refresh-btn").addEventListener("click", () => {
  refreshSources().catch((e) => setStatus(e.message));
});

refreshSources()
  .then(() => {
    const ready = state.sources.find((s) => s.status === "ready");
    if (ready) return selectSource(ready.id);
  })
  .catch((e) => setStatus(e.message));
