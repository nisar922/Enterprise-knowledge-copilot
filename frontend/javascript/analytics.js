const statsBox = document.querySelector("#stats");
const errorBox = document.querySelector("#error");

const pct = (v) => (v === null || v === undefined ? "n/a" : `${Math.round(v * 100)}%`);

function stat(label, value, hint) {
  const card = el("div", "card stat");
  card.append(el("div", "muted", label), el("div", "value", String(value)));
  if (hint) card.append(el("div", "muted small", hint));
  return card;
}

function renderChart(daily) {
  const chart = document.querySelector("#chart");
  chart.replaceChildren();
  const max = Math.max(1, ...daily.map((d) => d.queries));
  for (const d of daily) {
    const col = el("div", "bar-col");
    const area = el("div", "bar-area");
    const bar = el("div", "bar");
    bar.style.height = `${(d.queries / max) * 100}%`;
    area.append(bar);
    col.append(el("div", "bar-count", String(d.queries)), area, el("div", "bar-label", d.date.slice(5)));
    chart.append(col);
  }
}

async function loadSummary() {
  try {
    const s = await apiFetch("/analytics/summary");
    statsBox.replaceChildren(
      stat("Documents", s.documents, `${s.ready_documents} ready`),
      stat("Queries", s.queries, `${s.conversations} conversations`),
      stat("Avg latency", `${Math.round(s.avg_latency_ms)} ms`, `p95: ${Math.round(s.p95_latency_ms)} ms`),
      stat("Tokens used", s.prompt_tokens + s.completion_tokens, `${s.prompt_tokens} in / ${s.completion_tokens} out`),
      stat("Est. cost", `$${s.estimated_cost_usd}`, "estimate from config prices"),
      stat("No-answer rate", pct(s.no_answer_rate), "questions with no relevant docs"),
      stat("Retrieval score", s.avg_retrieval_score ?? "n/a", "avg top source (reranker)"),
      stat("Faithfulness", pct(s.avg_faithfulness), `judged: ${s.evaluated_turns} answers`),
      stat("Answer relevance", pct(s.avg_answer_relevance), `judged: ${s.evaluated_turns} answers`)
    );
    renderChart(s.daily_usage);
  } catch (err) {
    errorBox.textContent = err.message;
  }
}

async function runQuality() {
  const btn = document.querySelector("#quality-btn");
  const out = document.querySelector("#quality-out");
  btn.disabled = true;
  out.textContent = "Judging answers... this can take 10-30 seconds.";
  try {
    const r = await apiFetch("/analytics/evaluate?limit=5", { method: "POST" });
    out.textContent = `Evaluated ${r.evaluated}, skipped ${r.skipped}. This batch: faithfulness ${pct(r.avg_faithfulness)}, relevance ${pct(r.avg_answer_relevance)}.`;
    await loadSummary();
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

async function runRetrieval() {
  const btn = document.querySelector("#retrieval-btn");
  const out = document.querySelector("#retrieval-out");
  const table = document.querySelector("#retrieval-table");
  const body = document.querySelector("#retrieval-body");
  btn.disabled = true;
  out.textContent = "Running...";
  try {
    const r = await apiFetch("/analytics/retrieval-eval", { method: "POST" });
    out.textContent = `${r.cases} cases · hit rate@${r.k}: ${pct(r.hit_rate)} · MRR: ${r.mrr}`;
    body.replaceChildren();
    for (const c of r.results) {
      const tr = el("tr");
      tr.append(el("td", "", c.question), el("td", "", c.expected_filename), el("td", "", c.rank ?? "-"));
      const hit = el("td");
      hit.append(el("span", `badge ${c.hit ? "badge-ready" : "badge-failed"}`, c.hit ? "hit" : "miss"));
      tr.append(hit);
      body.append(tr);
    }
    table.classList.remove("hidden");
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

document.querySelector("#quality-btn").addEventListener("click", runQuality);
document.querySelector("#retrieval-btn").addEventListener("click", runRetrieval);

(async () => {
  const user = await requireAuth();
  if (!user) return;
  renderNav(user, "analytics");
  if (user.role === "admin") document.querySelector("#admin-card").classList.remove("hidden");
  loadSummary();
})();