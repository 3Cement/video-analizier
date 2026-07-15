const state = {
  sources: [],
  selectedId: null,
  pollTimer: null,
};

const el = {
  sourceList: document.getElementById("source-list"),
  statusLine: document.getElementById("status-line"),
  detailMeta: document.getElementById("detail-meta"),
  summaryBox: document.getElementById("summary-box"),
  transcriptPre: document.getElementById("transcript-pre"),
  answerBox: document.getElementById("answer-box"),
  refreshBtn: document.getElementById("refresh-btn"),
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
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

function setStatus(text) {
  el.statusLine.textContent = text;
}

function renderSources() {
  el.sourceList.innerHTML = "";
  if (!state.sources.length) {
    el.sourceList.innerHTML = "<li class='muted'>Brak źródeł.</li>";
    return;
  }
  for (const source of state.sources) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `source-item${source.id === state.selectedId ? " active" : ""}`;
    btn.innerHTML = `<strong>${source.title || "Bez tytułu"}</strong>
      <span class="muted">${source.source_type} · ${source.status} · segmenty: ${source.segment_count}</span>`;
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
    setStatus(`Przetwarzanie #${busy.id}: ${busy.status}`);
    schedulePoll();
  } else if (state.sources.some((s) => s.status === "failed")) {
    setStatus("Część zadań zakończyła się błędem.");
  } else {
    setStatus("Gotowe.");
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
    }
  }, 2500);
}

async function selectSource(id, resetAnswer = true) {
  state.selectedId = id;
  renderSources();
  const detail = await api(`/sources/${id}`);
  el.detailMeta.textContent = [
    detail.title,
    detail.transcript_method || "brak metody",
    detail.duration_seconds ? `${Math.round(detail.duration_seconds)}s` : null,
    detail.status,
    detail.error ? `błąd: ${detail.error}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const latestSummary = (detail.summaries || []).at(-1);
  el.summaryBox.textContent = latestSummary
    ? latestSummary.content
    : "Brak podsumowania. Ustaw OPENAI_API_KEY lub wygeneruj briefing później.";

  el.transcriptPre.textContent = (detail.segments || [])
    .map((s) => `[${formatTs(s.start)}] ${s.text}`)
    .join("\n");

  if (resetAnswer) el.answerBox.textContent = "";
  if (!["ready", "failed"].includes(detail.status)) schedulePoll();
}

function bindTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".tab-panel");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.querySelector(`[data-panel="${tab.dataset.tab}"]`).classList.add("active");
    });
  });
}

document.getElementById("youtube-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    setStatus("Dodawanie źródła YouTube...");
    const payload = {
      url: document.getElementById("youtube-url").value.trim(),
      language: "pl",
      auto_summarize: document.getElementById("youtube-summarize").checked,
    };
    const created = await api("/sources/youtube", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.selectedId = created.id;
    await refreshSources();
    await selectSource(created.id);
  } catch (err) {
    setStatus(err.message);
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
    body.append("auto_summarize", document.getElementById("upload-summarize").checked);
    setStatus("Wgrywanie pliku...");
    const created = await api("/sources/upload", { method: "POST", body });
    state.selectedId = created.id;
    await refreshSources();
    await selectSource(created.id);
  } catch (err) {
    setStatus(err.message);
  }
});

document.getElementById("text-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const payload = {
      title: document.getElementById("text-title").value.trim() || "Notatka",
      text: document.getElementById("text-body").value,
      language: "pl",
      auto_summarize: document.getElementById("text-summarize").checked,
    };
    setStatus("Dodawanie tekstu...");
    const created = await api("/sources/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.selectedId = created.id;
    await refreshSources();
    await selectSource(created.id);
  } catch (err) {
    setStatus(err.message);
  }
});

document.getElementById("ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selectedId) {
    setStatus("Najpierw wybierz źródło.");
    return;
  }
  try {
    setStatus("Generowanie odpowiedzi...");
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
    el.answerBox.textContent = `${data.answer}\n\nCytowania:\n${cites || "(brak)"}`;
    setStatus("Odpowiedź gotowa.");
  } catch (err) {
    setStatus(err.message);
  }
});

el.refreshBtn.addEventListener("click", () => refreshSources().catch((e) => setStatus(e.message)));

bindTabs();
refreshSources().catch((e) => setStatus(e.message));