const SCENARIOS = [
  {
    id: "v1",
    title: "v1 — Baseline pipeline",
    description: "Transcript in, structured summary out. No extra grounding.",
    audio: "/v1/output/recording.wav",
    transcript: "/v1/output/transcript.txt",
    variants: [
      { key: "baseline", label: "Summary", path: "/v1/output/summary.txt" },
    ],
  },
  {
    id: "v2",
    title: "v2 — Context-aware summarization",
    description: "Meeting context injected into the prompt before the transcript — baseline and context-aware summaries side by side.",
    audio: "/v2/output/recording.wav",
    transcript: "/v2/output/transcript.txt",
    variants: [
      { key: "baseline", label: "Baseline (no context)", path: "/v2/output/summary_baseline.txt" },
      { key: "with_context", label: "With context", path: "/v2/output/summary_with_context.txt" },
    ],
  },
  {
    id: "v3",
    title: "v3 — Checklist coverage check",
    description: "Same context-aware summarizer as v2, plus a deterministic checklist coverage section.",
    audio: "/v3/output/recording.wav",
    transcript: "/v3/output/transcript.txt",
    variants: [
      { key: "context_checklist", label: "Summary + Checklist", path: "/v3/output/summary.txt" },
    ],
  },
  {
    id: "v4",
    title: "v4 — AI Assistant as third actor",
    description: "A third voice (AI Assistant) joins the recording itself and takes notes live.",
    audio: "/v4/output/recording.wav",
    transcript: "/v4/output/transcript.txt",
    variants: [
      { key: "context_checklist_assistant", label: "Summary + Checklist", path: "/v4/output/summary.txt" },
    ],
  },
];

const STORY_MEETINGS = [1, 2, 3, 4, 5].map((week) => ({
  week,
  label: `Week ${week}`,
  audio: `/story/output/meeting-${week}/recording.wav`,
  transcript: `/story/output/meeting-${week}/transcript.txt`,
  baseline: `/story/output/meeting-${week}/summary_baseline.txt`,
  context: `/story/output/meeting-${week}/summary_with_context.txt`,
}));

// Findings from reading the actual generated text, not something the
// automated eval surfaced on its own (see eval/story_judge.py) — kept here
// as explicit, attributed human-review notes rather than folded into the
// scored data, so the UI never implies these came from the judge.
const STORY_CURATOR_NOTES = {
  3: "Baseline conflates two separate workstreams — it says things like \"Legal review for dark mode needs attention,\" mixing up dark mode (a design workstream) with the unrelated legal/privacy review. The context-aware version keeps them correctly separate. This was originally caught by manual reading only; the LLM-judge probe designed to check it got fooled (marked both variants as passing), so it was replaced with the deterministic \"Dark mode kept separate from legal/privacy review\" check below, which catches it reliably in both this run and an earlier independent regeneration.",
  5: "The context-aware summary lists Week 4's already-completed actions (\"finish validating analytics by Friday\", \"start preparing the stakeholder deck\") as if still pending in Week 5 — but the Week 5 transcript says both are already done. This is stale history leaking into current-meeting content, exactly what the system prompt was written to prevent. Both the holistic continuity score and an LLM-judge probe built specifically to catch this scored it a pass; only the deterministic \"No stale-action carryover\" check below (word-overlap against the accumulated history) catches it reliably.",
};

// ---------- tiny markdown-lite renderer (headings / bullets / paragraphs only) ----------
function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderMarkdownLite(text) {
  const lines = text.split("\n");
  let html = "";
  let inList = false;
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) { closeList(); continue; }
    const heading = line.match(/^#{1,6}\s*(.+)$/);
    if (heading) {
      closeList();
      html += `<h3>${escapeHtml(heading[1])}</h3>`;
      continue;
    }
    const bullet = line.match(/^[-*]\s*(.+)$/);
    if (bullet) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${escapeHtml(bullet[1])}</li>`;
      continue;
    }
    closeList();
    html += `<p>${escapeHtml(line)}</p>`;
  }
  closeList();
  return html;
}

function extractSection(text, headingName) {
  const lines = text.split("\n");
  const headingRe = new RegExp(`^#{1,6}\\s*${headingName}\\s*$`, "i");
  const anyHeadingRe = /^#{1,6}\s+\S/;
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    if (headingRe.test(lines[i].trim())) { start = i + 1; break; }
  }
  if (start === -1) return [];
  const collected = [];
  for (let i = start; i < lines.length; i++) {
    if (anyHeadingRe.test(lines[i].trim())) break;
    collected.push(lines[i]);
  }
  return collected;
}

function extractKeyPoints(text) {
  return extractSection(text, "Key Points")
    .map((l) => l.trim())
    .filter((l) => /^[-*]\s*/.test(l))
    .map((l) => l.replace(/^[-*]\s*/, ""));
}

// ---------- Scenarios page ----------
async function fetchText(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.text();
}

// Reused verbatim from ../app-documentation.md's "Technical stack" section —
// keep in sync with that file if the stack changes.
const TECH_CHIPS = [
  "Whisper (base)", "Qwen2.5-1.5B-Instruct", "pyttsx3 TTS",
  "pydub + ffmpeg", "Keyword-based checklist", "Fully offline",
];

const TECH_STACK = [
  { label: "Language", value: "Python 3" },
  { label: "Speech-to-text", value: "OpenAI Whisper (local, <code>base</code> model)" },
  { label: "Summarization", value: "local instruction-following LLM via Hugging Face <code>transformers</code> (<code>Qwen/Qwen2.5-1.5B-Instruct</code>), run on-device (Apple Silicon MPS acceleration where available)" },
  { label: "Text-to-speech (demo recordings)", value: "<code>pyttsx3</code>, using native OS voices" },
  { label: "Audio processing", value: "<code>pydub</code> (backed by <code>ffmpeg</code>)" },
  { label: "Checklist coverage check", value: "deterministic keyword matching against the transcript, with negation-awareness — chosen over an additional LLM call after testing showed the small local model was unreliable at that specific judgment" },
  { label: "Evaluation suite (eval/)", value: "Word Error Rate + noise-robustness testing (no new dependency), LLM-judged faithfulness/completeness/conciseness, and deterministic schema/checklist/extraction-efficiency checks — same \"prefer deterministic over LLM judgment\" principle as the checklist above" },
  { label: "Web UI (webapp/)", value: "framework-free HTML/CSS/JS, served by a stdlib-only Python <code>http.server</code> subclass — no new runtime dependency" },
  { label: "Dependencies", value: "<code>torch</code>, <code>accelerate</code>, <code>transformers</code>, <code>openai-whisper</code>, <code>pydub</code>, <code>pyttsx3</code>" },
  { label: "Infrastructure", value: "runs entirely offline/on-device after initial one-time model downloads (~3GB total); no external API keys or network calls required at runtime" },
];

function renderTechSummary() {
  const root = document.getElementById("tech-summary");
  root.innerHTML = `
    <div class="tech-card">
      <div class="block-label">Technology</div>
      <p class="tech-intro">Everything runs locally — no audio or transcript ever leaves the device, no third-party AI service is called, no per-use API costs.</p>
      <div class="tech-chips">${TECH_CHIPS.map((c) => `<span class="tech-chip">${escapeHtml(c)}</span>`).join("")}</div>
      <button class="full-toggle" data-target="tech-details">Show stack details &#9662;</button>
      <div class="tech-details full-text hidden" id="tech-details">
        ${TECH_STACK.map((row) => `<div class="tech-row"><span class="label">${escapeHtml(row.label)}:</span> ${row.value}</div>`).join("")}
      </div>
    </div>
  `;
  root.querySelector(".full-toggle").addEventListener("click", (e) => {
    const target = document.getElementById(e.target.dataset.target);
    const isHidden = target.classList.toggle("hidden");
    e.target.innerHTML = isHidden ? "Show stack details &#9662;" : "Hide stack details &#9652;";
  });
}

// ---------- Evaluation summary (plain-language, for a non-technical reader) ----------
// Everything here is derived from the same JSON the (much more detailed,
// jargon-heavy) Evaluation page renders — this just boils each dimension
// down to a short label + simple status color, no raw numbers/thresholds
// exposed beyond what's needed to read the verdict at a glance.
async function fetchJsonOrNull(path) {
  try {
    const res = await fetch(path);
    if (!res.ok) return null;
    return await res.json();
  } catch (_err) {
    return null;
  }
}

function labelForWer(wer) {
  if (wer === null || wer === undefined) return { label: "—", cls: "neutral" };
  const pct = (wer * 100).toFixed(1);
  if (wer < 0.05) return { label: `Excellent (${pct}% error rate)`, cls: "good" };
  if (wer < 0.08) return { label: `Good (${pct}% error rate)`, cls: "good" };
  return { label: `Fair (${pct}% error rate)`, cls: "critical" };
}

function labelForTrust(avgFaithfulness, unsupportedCount) {
  if (avgFaithfulness === null || Number.isNaN(avgFaithfulness)) return { label: "—", cls: "neutral" };
  if (avgFaithfulness >= 4) {
    return unsupportedCount > 0
      ? { label: `Good, ${unsupportedCount} claim(s) flagged for review`, cls: "good" }
      : { label: "Good — no invented facts found", cls: "good" };
  }
  if (avgFaithfulness >= 3) return { label: "Fair — spot-check recommended", cls: "critical" };
  return { label: "Needs review", cls: "critical" };
}

function labelForFormat(allCompliant, partial) {
  if (allCompliant === null) return { label: "—", cls: "neutral" };
  if (allCompliant) return { label: "Consistent", cls: "good" };
  return { label: partial ? "Minor drift (older format in one variant)" : "Formatting issues found", cls: "critical" };
}

function summaryPill(entry) {
  return `<span class="status-pill"><span class="status-dot ${entry.cls}"></span>${escapeHtml(entry.label)}</span>`;
}

function isVariantCompliant(variant) {
  return variant.layer1.schema.all_sections_present
    && variant.layer1.schema.heading_level_matches_spec
    && variant.layer1.actions.compliant !== false;
}

async function renderEvalSummaryTable() {
  const root = document.getElementById("eval-summary");
  root.innerHTML = "";

  const [results, storyResults, transcriptionQuality, pipelineStatus, evalHistory] = await Promise.all([
    fetchJsonOrNull("/eval/output/results.json"),
    fetchJsonOrNull("/eval/output/story_results.json"),
    fetchJsonOrNull("/eval/output/transcription_quality.json"),
    fetchJsonOrNull("/api/pipeline/status"),
    fetchJsonOrNull("/api/eval/history"),
  ]);

  if (!results && !storyResults && !transcriptionQuality) {
    return; // nothing generated yet — say nothing rather than show an empty table
  }

  const PROVIDER_LABELS = { local: "Local (Qwen)", mistral: "Local (Mistral)", claude: "Claude" };
  const PROVIDER_ORDER = ["local", "claude", "mistral"];  // fixed display order everywhere

  function formatTimestamp(ts) {
    return new Date(ts * 1000).toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    });
  }

  // scenario_id -> provider -> variantKey -> latest record for that exact
  // triple. variantKey folds in the meeting number for story/ (each of its
  // 5 meetings has its own "baseline"/"with_context" pair) so aggregating
  // "all of this provider's records for this scenario" below correctly
  // covers all 5 meetings instead of just whichever was judged last.
  const latestByScenarioProvider = {};
  if (evalHistory) {
    for (const r of evalHistory.records) {
      if (!PROVIDER_ORDER.includes(r.summarizer_provider)) continue;  // skip "unknown" (pre-tracking bulk runs)
      const variantKey = r.meeting != null ? `${r.variant}#${r.meeting}` : r.variant;
      const byProvider = latestByScenarioProvider[r.scenario_id] || (latestByScenarioProvider[r.scenario_id] = {});
      const byVariant = byProvider[r.summarizer_provider] || (byProvider[r.summarizer_provider] = {});
      if (!byVariant[variantKey] || r.timestamp > byVariant[variantKey].timestamp) {
        byVariant[variantKey] = r;
      }
    }
  }

  // Fallback for scenarios never judged (no run_history entry at all) —
  // still show *something* from the output file's mtime, provider unknown,
  // rather than going blank for every scenario that predates judging.
  const fallbackLastRunById = {};
  const fallbackProviderById = {};
  if (pipelineStatus) {
    for (const p of pipelineStatus.pipelines) {
      fallbackLastRunById[p.id] = p.last_run_at;
      fallbackProviderById[p.id] = p.provider;
    }
  }

  function formatCost(usd) {
    if (usd == null) return "—";
    if (usd === 0) return "Free (local)";
    return `$${usd.toFixed(4)}`;
  }

  // Cost column: summarization cost for the model this row is about, plus
  // judging cost as a separate line only when it's non-zero (i.e. the judge
  // was also Claude for at least one of these records) — keeps the "cost of
  // running this model" figure from being conflated with judging spend.
  function costCell(records) {
    const summarizerCosts = records.map((r) => r.summarizer_cost_usd).filter((v) => v != null);
    const judgeCosts = records.map((r) => r.judge_cost_usd).filter((v) => v != null);
    if (!summarizerCosts.length && !judgeCosts.length) return "—";
    const summarizerTotal = summarizerCosts.reduce((a, b) => a + b, 0);
    const judgeTotal = judgeCosts.reduce((a, b) => a + b, 0);
    let html = formatCost(summarizerCosts.length ? summarizerTotal : null);
    if (judgeTotal > 0) {
      html += `<br><span class="run-count">+ ${formatCost(judgeTotal)} judging</span>`;
    }
    return html;
  }

  function qualityFromRecords(records) {
    const faithArr = records.map((r) => r.layer2 && r.layer2.faithfulness).filter((v) => v != null);
    const avgFaith = faithArr.length ? faithArr.reduce((a, b) => a + b, 0) / faithArr.length : null;
    const claimsCount = records.reduce((sum, r) => sum + ((r.layer2 && r.layer2.unsupported_claims) || []).length, 0);
    const trust = labelForTrust(avgFaith, claimsCount);

    const compliantFlags = records.map(isVariantCompliant);
    const allCompliant = compliantFlags.length ? compliantFlags.every(Boolean) : null;
    const someCompliant = compliantFlags.some(Boolean);
    const format = labelForFormat(allCompliant, someCompliant && !allCompliant);

    let checklist = { label: "—", cls: "neutral" };
    const withChecklist = records.find((r) => r.checklist);
    if (withChecklist) {
      const c = withChecklist.checklist;
      const correct = c.tp + c.tn;
      checklist = { label: `${correct}/7 topics correct`, cls: correct === 7 ? "good" : "critical" };
    }
    return { trust, format, checklist };
  }

  const werById = {};
  if (transcriptionQuality) {
    for (const s of transcriptionQuality.scenarios) {
      werById[s.id] = s.tiers.clean.wer;
    }
  }

  function scenarioWer(id) {
    if (id !== "story") return werById[id] !== undefined ? labelForWer(werById[id]) : { label: "—", cls: "neutral" };
    const storyWerValues = [1, 2, 3, 4, 5].map((w) => werById[`story-week-${w}`]).filter((v) => v !== undefined);
    return storyWerValues.length
      ? labelForWer(storyWerValues.reduce((a, b) => a + b, 0) / storyWerValues.length)
      : { label: "—", cls: "neutral" };
  }

  // One row per (scenario, provider) that's actually been run — transcription
  // accuracy is Whisper-only so it's identical across providers within a
  // scenario, but trust/format/checklist come from that provider's own
  // judged output and genuinely differ.
  function scenarioRows(id, label, contextNote) {
    const wer = scenarioWer(id);
    const byProvider = latestByScenarioProvider[id];
    if (byProvider && Object.keys(byProvider).length) {
      return PROVIDER_ORDER.filter((p) => byProvider[p]).map((p) => {
        const records = Object.values(byProvider[p]);
        const q = qualityFromRecords(records);
        const latestTs = Math.max(...records.map((r) => r.timestamp));
        return {
          label, providerLabel: PROVIDER_LABELS[p], lastRun: formatTimestamp(latestTs),
          wer, trust: q.trust, format: q.format, checklist: q.checklist, contextNote,
          cost: costCell(records),
        };
      });
    }
    // No judged runs at all for this scenario — one fallback row from the
    // bulk eval/judge.py snapshot (results.json) + the file's mtime.
    const scenario = id === "story" ? null : (results ? results.scenarios.find((s) => s.id === id) : null);
    const scenarioResults = id === "story" ? storyResults : null;
    let records = [];
    if (scenario) records = scenario.variants;
    else if (scenarioResults) records = scenarioResults.meetings.flatMap((m) => [m.baseline, m.with_context]);
    const q = records.length ? qualityFromRecords(records) : { trust: { label: "—", cls: "neutral" }, format: { label: "—", cls: "neutral" }, checklist: { label: "—", cls: "neutral" } };
    const ts = fallbackLastRunById[id];
    const providerLabel = PROVIDER_LABELS[fallbackProviderById[id]] || "provider unknown";
    return [{
      label, providerLabel, lastRun: ts ? formatTimestamp(ts) : "—",
      wer, trust: q.trust, format: q.format, checklist: q.checklist, contextNote,
      cost: "—",  // no per-provider run history for this scenario — cost isn't known
    }];
  }

  const rows = [
    ...scenarioRows("v1", "v1 — Baseline", "—"),
    ...scenarioRows("v2", "v2 — Context-aware", "Mixed — sharper wording, but captured fewer real action items than the plain version in this test."),
    ...scenarioRows("v3", "v3 — Checklist coverage", "—"),
    ...scenarioRows("v4", "v4 — AI Assistant", "—"),
    ...scenarioRows("story", "Story (5 meetings)", "Mixed — correctly kept two topics separate in one week that the plain version confused, but repeated an earlier week's finished tasks as if still pending in another. See the Story page for details."),
  ];

  root.innerHTML = `
    <div class="tech-card">
      <div class="block-label">Evaluation Summary</div>
      <p class="tech-intro">A quick read on quality across every scenario, in plain language. Full technical detail (raw scores, evidence quotes, methodology) is on the <button class="inline-link" id="eval-summary-link" type="button">Evaluation page</button>.</p>
      <div class="eval-table-wrap">
        <table class="eval-table summary-table">
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Model</th>
              <th>Last Run</th>
              <th>Transcription Accuracy</th>
              <th>Summary Trustworthiness</th>
              <th>Format Compliance</th>
              <th>Checklist Coverage</th>
              <th>Cost</th>
              <th>Does Context Help?</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((r) => `
              <tr>
                <td>${escapeHtml(r.label)}</td>
                <td>${escapeHtml(r.providerLabel)}</td>
                <td>${escapeHtml(r.lastRun)}</td>
                <td>${summaryPill(r.wer)}</td>
                <td>${summaryPill(r.trust)}</td>
                <td>${summaryPill(r.format)}</td>
                <td>${summaryPill(r.checklist)}</td>
                <td>${r.cost}</td>
                <td>${escapeHtml(r.contextNote)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;

  const link = document.getElementById("eval-summary-link");
  if (link) {
    link.addEventListener("click", () => {
      document.querySelector('.nav-item[data-page="evaluation"]').click();
    });
  }
}

function renderScenarioGrid() {
  const grid = document.getElementById("scenario-grid");
  grid.innerHTML = "";
  for (const scenario of SCENARIOS) {
    const card = document.createElement("button");
    card.className = "scenario-card";
    card.innerHTML = `<h3>${scenario.title}</h3><p>${scenario.description}</p>`;
    card.addEventListener("click", () => showScenarioDetail(scenario));
    grid.appendChild(card);
  }
}

async function showScenarioDetail(scenario) {
  const list = document.getElementById("scenario-list");
  const detail = document.getElementById("scenario-detail");
  list.classList.add("hidden");
  detail.classList.remove("hidden");
  detail.innerHTML = `<p>Loading…</p>`;

  const [variantTexts, transcriptText] = await Promise.all([
    Promise.all(scenario.variants.map((v) => fetchText(v.path))),
    fetchText(scenario.transcript),
  ]);

  let html = `
    <button class="back-link">&larr; All scenarios</button>
    <div class="detail-header">
      <h2>${scenario.title}</h2>
      <p>${scenario.description}</p>
    </div>

    <div class="audio-block">
      <div class="block-label">Recording</div>
      <audio controls src="${scenario.audio}"></audio>
      <a class="audio-link" href="${scenario.audio}" download>Download audio</a>
    </div>

    <div class="transcript-block">
      <h4>Transcript</h4>
      <div class="transcript-text">${escapeHtml(transcriptText)}</div>
    </div>
  `;

  scenario.variants.forEach((variant, i) => {
    const text = variantTexts[i];
    const keyPoints = extractKeyPoints(text);
    const blockId = `full-${scenario.id}-${variant.key}`;
    html += `
      <div class="variant-block">
        <h4>${variant.label}</h4>
        <div class="key-points">
          <div class="key-points-label">Key Points</div>
          <ul>${keyPoints.map((k) => `<li>${escapeHtml(k)}</li>`).join("") || "<li>(none extracted)</li>"}</ul>
        </div>
        <button class="full-toggle" data-target="${blockId}">Show full output ▾</button>
        <div class="full-text hidden" id="${blockId}">${renderMarkdownLite(text)}</div>
      </div>
    `;
  });

  detail.innerHTML = html;

  detail.querySelector(".back-link").addEventListener("click", () => {
    detail.classList.add("hidden");
    list.classList.remove("hidden");
  });

  detail.querySelectorAll(".full-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      const isHidden = target.classList.toggle("hidden");
      btn.textContent = isHidden ? "Show full output ▾" : "Hide full output ▴";
    });
  });
}

// ---------- Evaluation page ----------
function statusPill(ok, labelTrue, labelFalse) {
  const cls = ok ? "good" : "critical";
  const label = ok ? labelTrue : labelFalse;
  return `<span class="status-pill"><span class="status-dot ${cls}"></span>${label}</span>`;
}

function scoreCell(value) {
  const pct = (value / 5) * 100;
  return `
    <div class="score-cell">
      <div class="score-bar-track"><div class="score-bar-fill" style="width:${pct}%"></div></div>
      <span class="score-num">${value}/5</span>
    </div>
  `;
}

function fmtPct(n) {
  return n === null || n === undefined ? "—" : `${Math.round(n * 100)}%`;
}

async function loadResults() {
  const res = await fetch("/eval/output/results.json");
  if (!res.ok) throw new Error(`Failed to load eval results: ${res.status}`);
  return res.json();
}

function flattenVariants(results) {
  const rows = [];
  for (const scenario of results.scenarios) {
    for (const variant of scenario.variants) {
      rows.push({ scenario, variant });
    }
  }
  return rows;
}

function renderEvaluationTable(rows) {
  let html = `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Variant</th>
            <th>Schema</th>
            <th>Actions format</th>
            <th>Faithfulness</th>
            <th>Completeness</th>
            <th>Conciseness</th>
            <th>Checklist accuracy</th>
          </tr>
        </thead>
        <tbody>
  `;
  for (const { scenario, variant } of rows) {
    const schemaOk = variant.layer1.schema.all_sections_present && variant.layer1.schema.heading_level_matches_spec;
    const actionsOk = variant.layer1.actions.compliant !== false;
    html += `
      <tr>
        <td>${scenario.id}</td>
        <td>${variant.variant}</td>
        <td>${statusPill(schemaOk, "OK", "Drift")}</td>
        <td>${statusPill(actionsOk, "OK", "Violation")}</td>
        <td>${scoreCell(variant.layer2.faithfulness)}</td>
        <td>${scoreCell(variant.layer2.completeness)}</td>
        <td>${scoreCell(variant.layer2.conciseness)}</td>
        <td>${variant.checklist ? fmtPct(variant.checklist.accuracy) : "—"}</td>
      </tr>
    `;
  }
  html += `</tbody></table></div>`;
  return html;
}

function renderEvaluationCard(scenario, variant) {
  const l1 = variant.layer1;
  const l2 = variant.layer2;
  const cl = variant.checklist;

  let html = `<div class="eval-card"><h4>${scenario.label} — ${variant.variant}</h4>`;

  html += `<div class="row"><span class="label">Schema:</span> ${statusPill(
    l1.schema.all_sections_present && l1.schema.heading_level_matches_spec,
    "all 4 sections present, heading level matches spec",
    l1.schema.heading_level_matches_spec === false
      ? "sections present but heading level drifted (### instead of ##)"
      : "missing required section(s)"
  )}</div>`;

  html += `<div class="row"><span class="label">Actions format:</span> ${statusPill(
    l1.actions.compliant !== false,
    "every bullet correctly prefixed",
    "prefix violation: " + l1.actions.violations.join("; ")
  )}</div>`;

  html += `<div class="row"><span class="label">Faithfulness:</span> ${l2.faithfulness}/5 — ${escapeHtml(l2.faithfulness_notes || "")}</div>`;
  html += `<div class="row"><span class="label">Completeness:</span> ${l2.completeness}/5 — ${escapeHtml(l2.completeness_notes || "")}</div>`;
  html += `<div class="row"><span class="label">Conciseness:</span> ${l2.conciseness}/5 — ${escapeHtml(l2.conciseness_notes || "")}</div>`;

  if (l2.unsupported_claims && l2.unsupported_claims.length) {
    html += `<div class="row"><span class="label">Unsupported claims:</span></div>`;
    for (const claim of l2.unsupported_claims) {
      html += `<div class="mismatch">${escapeHtml(claim)}</div>`;
    }
  }

  if (cl) {
    html += `<div class="row"><span class="label">Checklist:</span> precision ${fmtPct(cl.precision)}, recall ${fmtPct(cl.recall)}, accuracy ${fmtPct(cl.accuracy)}</div>`;
    for (const m of cl.mismatches) {
      html += `<div class="mismatch"><strong>${escapeHtml(m.topic)}</strong> — expected ${m.truth ? "Covered" : "Not covered"}, got ${m.predicted === null ? "missing" : (m.predicted ? "Covered" : "Not covered")}${m.evidence ? ` (evidence quoted: ${escapeHtml(m.evidence)})` : ""}</div>`;
    }
  }

  html += `</div>`;
  return html;
}

// ---------- Transcription quality (WER + noise robustness) ----------
async function loadTranscriptionQuality() {
  const res = await fetch("/eval/output/transcription_quality.json");
  if (!res.ok) throw new Error(`Failed to load transcription quality: ${res.status}`);
  return res.json();
}

function werCell(tier) {
  const pct = tier.wer * 100;
  const cls = tier.wer < 0.08 ? "good" : "critical";
  return `<span class="status-pill"><span class="status-dot ${cls}"></span>${pct.toFixed(1)}%</span>`;
}

function renderTranscriptionQualitySection(data) {
  let html = `<h3 class="eval-section-header">A. Speech Recognition &amp; Transcription Quality</h3>`;
  html += `<p class="eval-note">Whisper model: ${escapeHtml(data.whisper_model)}. ${escapeHtml(data.wer_benchmark_note)}</p>`;

  html += `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Clean WER</th>
            <th>Light noise WER</th>
            <th>Heavy noise WER</th>
            <th>Reference words</th>
          </tr>
        </thead>
        <tbody>
  `;
  for (const s of data.scenarios) {
    html += `
      <tr>
        <td>${escapeHtml(s.id)}</td>
        <td>${werCell(s.tiers.clean)}</td>
        <td>${werCell(s.tiers.light_noise)}</td>
        <td>${werCell(s.tiers.heavy_noise)}</td>
        <td>${s.tiers.clean.reference_word_count}</td>
      </tr>
    `;
  }
  html += `</tbody></table></div>`;
  html += `<p class="eval-note">${escapeHtml(data.noise_tiers_note)}</p>`;

  html += `<div class="eval-card"><h4>Speaker Diarization</h4><p class="eval-note" style="margin:0;">${escapeHtml(data.diarization_note)}</p></div>`;

  return html;
}

// ---------- Information extraction efficiency ----------
async function loadExtractionEfficiency() {
  const res = await fetch("/eval/output/extraction_efficiency.json");
  if (!res.ok) throw new Error(`Failed to load extraction efficiency: ${res.status}`);
  return res.json();
}

function renderExtractionEfficiencySection(data) {
  let html = `<h4 class="eval-subsection-header">Information Extraction Efficiency</h4>`;
  html += `<p class="eval-note">${escapeHtml(data.method_note)}</p>`;

  html += `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Variant</th>
            <th>Recall</th>
            <th>Precision</th>
            <th>Ground truth</th>
            <th>Generated</th>
          </tr>
        </thead>
        <tbody>
  `;
  for (const s of data.scenarios) {
    for (const v of s.variants) {
      html += `
        <tr>
          <td>${escapeHtml(s.id)}</td>
          <td>${escapeHtml(v.variant)}</td>
          <td>${fmtPct(v.recall)}</td>
          <td>${fmtPct(v.precision)}</td>
          <td>${v.ground_truth_count}</td>
          <td>${v.generated_count}</td>
        </tr>
      `;
    }
  }
  html += `</tbody></table></div>`;
  return html;
}

async function renderEvaluationPage() {
  const root = document.getElementById("evaluation-root");
  root.innerHTML = "<p>Loading…</p>";
  let html = "";

  try {
    const transcriptionData = await loadTranscriptionQuality();
    html += renderTranscriptionQualitySection(transcriptionData);
  } catch (err) {
    html += `<h3 class="eval-section-header">A. Speech Recognition &amp; Transcription Quality</h3><p class="eval-note">Could not load (${escapeHtml(err.message)}). Run <code>python eval/transcription_quality.py</code>.</p>`;
  }

  html += `<h3 class="eval-section-header">B. Summarization Quality</h3>`;

  try {
    const extractionData = await loadExtractionEfficiency();
    html += renderExtractionEfficiencySection(extractionData);
  } catch (err) {
    html += `<h4 class="eval-subsection-header">Information Extraction Efficiency</h4><p class="eval-note">Could not load (${escapeHtml(err.message)}). Run <code>python eval/extraction_efficiency.py</code>.</p>`;
  }

  try {
    const results = await loadResults();
    const rows = flattenVariants(results);

    html += `<h4 class="eval-subsection-header">Faithfulness / Low Hallucination &amp; Structure &amp; Format Control</h4>`;
    html += `<p class="eval-note">Judge model: ${escapeHtml(results.model)} (same local model used for summarization — self-preference bias is a known limitation, treat as a rough signal). Generated ${new Date(results.generated_at).toLocaleString()}.</p>`;
    html += renderEvaluationTable(rows);
    for (const { scenario, variant } of rows) {
      html += renderEvaluationCard(scenario, variant);
    }
  } catch (err) {
    html += `<h4 class="eval-subsection-header">Faithfulness &amp; Structure/Format Control</h4><p class="eval-note">Could not load (${escapeHtml(err.message)}). Run <code>python eval/judge.py</code>.</p>`;
  }

  try {
    const historyData = await fetchEvalHistory();
    html += renderProviderComparisonSection(historyData.records);
  } catch (err) {
    html += `<h3 class="eval-section-header">C. Provider Comparison — Local vs Claude, Across Runs</h3><p class="eval-note">Could not load run history (${escapeHtml(err.message)}).</p>`;
  }

  root.innerHTML = html;

  const pipelineLink = document.getElementById("eval-pipeline-link");
  if (pipelineLink) {
    pipelineLink.addEventListener("click", () => {
      document.querySelector('.nav-item[data-page="pipeline"]').click();
    });
  }
  root.querySelectorAll(".chart-table-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      const isHidden = target.classList.toggle("hidden");
      btn.textContent = isHidden ? "Show as table" : "Hide table";
    });
  });
}

// ---------- Provider comparison (run history) ----------
async function fetchEvalHistory() {
  const res = await fetch("/api/eval/history");
  if (!res.ok) throw new Error(`Failed to load run history: ${res.status}`);
  return res.json();
}

// Fixed categorical assignment for the three summarizer providers — slot
// order never changes regardless of which providers have data in a given
// view (dataviz non-negotiable: color follows identity, never reassigned).
const COMPARISON_PROVIDERS = [
  { key: "local", label: "Local (Qwen)", color: "var(--seq-500)" },
  { key: "claude", label: "Claude", color: "var(--cat-2)" },
  { key: "mistral", label: "Local (Mistral)", color: "var(--cat-3)" },
];

function groupHistoryForComparison(records) {
  const groups = new Map();
  let unknownCount = 0;
  for (const r of records) {
    if (!COMPARISON_PROVIDERS.some((p) => p.key === r.summarizer_provider)) {
      unknownCount += 1;  // e.g. bulk `eval/judge.py` runs against files of unknown origin
      continue;
    }
    const key = `${r.scenario_id}::${r.variant}`;
    if (!groups.has(key)) {
      const entry = { scenarioId: r.scenario_id, variant: r.variant };
      for (const p of COMPARISON_PROVIDERS) entry[p.key] = [];
      groups.set(key, entry);
    }
    groups.get(key)[r.summarizer_provider].push(r);
  }
  for (const g of groups.values()) {
    for (const p of COMPARISON_PROVIDERS) g[p.key].sort((a, b) => a.timestamp - b.timestamp);
  }
  return { groups: [...groups.values()], unknownCount };
}

function renderComparisonRow(group) {
  const fmt = (records) => {
    if (!records.length) return `<span class="eval-muted">No runs yet</span>`;
    const l2 = records[records.length - 1].layer2 || {};
    const nums = ["faithfulness", "completeness", "conciseness"].map((m) => (l2[m] != null ? l2[m] : "—")).join(" / ");
    return `${nums} <span class="run-count">(${records.length} run${records.length === 1 ? "" : "s"})</span>`;
  };
  const cells = COMPARISON_PROVIDERS.map((p) => `<td>${fmt(group[p.key])}</td>`).join("");
  return `<tr><td>${escapeHtml(group.scenarioId)} / ${escapeHtml(group.variant)}</td>${cells}</tr>`;
}

// Small, dependency-free line chart: up to 3 fixed series (COMPARISON_PROVIDERS,
// in that fixed order everywhere on this page), y = faithfulness score 1-5,
// x = run sequence (chronological order, not calendar time — runs land
// irregularly, so a literal time axis would read as mostly-empty space).
function buildLineChartSvg(seriesList, ariaLabel) {
  const width = 320, height = 120;
  const pad = { top: 10, right: 10, bottom: 8, left: 20 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const allX = seriesList.flatMap((s) => s.points.map((p) => p.x));
  const xMin = 1, xMax = Math.max(...allX, 1);
  const yMin = 1, yMax = 5;
  const xScale = (x) => pad.left + (xMax === xMin ? plotW / 2 : ((x - xMin) / (xMax - xMin)) * plotW);
  const yScale = (y) => pad.top + (1 - (y - yMin) / (yMax - yMin)) * plotH;

  const gridLines = [1, 3, 5].map((v) => `<line x1="${pad.left}" x2="${width - pad.right}" y1="${yScale(v).toFixed(1)}" y2="${yScale(v).toFixed(1)}" stroke="var(--gridline)" stroke-width="1"/>`).join("");
  const yLabels = [1, 3, 5].map((v) => `<text x="${pad.left - 4}" y="${(yScale(v) + 3).toFixed(1)}" font-size="9" fill="var(--text-muted)" text-anchor="end">${v}</text>`).join("");

  const seriesSvg = seriesList.map((s) => {
    if (!s.points.length) return "";
    const path = s.points.map((p, i) => `${i === 0 ? "M" : "L"}${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`).join(" ");
    const dots = s.points.map((p) => `<circle cx="${xScale(p.x).toFixed(1)}" cy="${yScale(p.y).toFixed(1)}" r="4" fill="${s.color}" stroke="var(--surface-1)" stroke-width="2"><title>${escapeHtml(p.label)}</title></circle>`).join("");
    return `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>${dots}`;
  }).join("");

  return `<svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="${escapeHtml(ariaLabel)}">${gridLines}${yLabels}${seriesSvg}</svg>`;
}

function renderTrendCard(group, index) {
  const toPoints = (records) => records
    .map((r, i) => ({
      x: i + 1,
      y: r.layer2 && r.layer2.faithfulness,
      label: `Run ${i + 1}: faithfulness ${r.layer2 && r.layer2.faithfulness != null ? r.layer2.faithfulness : "n/a"} (judged by ${r.judge_provider})`,
    }))
    .filter((p) => p.y != null);

  const seriesData = COMPARISON_PROVIDERS.map((p) => ({ provider: p, points: toPoints(group[p.key]) }));
  if (seriesData.every((s) => !s.points.length)) return "";

  const tableId = `trend-table-${index}`;
  const svg = buildLineChartSvg(
    seriesData.map((s) => ({ name: s.provider.label, color: s.provider.color, points: s.points })),
    `Faithfulness over runs — ${group.scenarioId} / ${group.variant}`,
  );

  const rows = COMPARISON_PROVIDERS
    .flatMap((p) => group[p.key].map((r) => ({ ...r, providerLabel: p.label })))
    .sort((a, b) => a.timestamp - b.timestamp);
  const tableRows = rows.map((r) => `<tr>
    <td>${escapeHtml(new Date(r.timestamp * 1000).toLocaleString())}</td>
    <td>${escapeHtml(r.providerLabel)}</td>
    <td>${escapeHtml(r.judge_provider)}</td>
    <td>${r.layer2 && r.layer2.faithfulness != null ? r.layer2.faithfulness : "—"}</td>
    <td>${r.layer2 && r.layer2.completeness != null ? r.layer2.completeness : "—"}</td>
    <td>${r.layer2 && r.layer2.conciseness != null ? r.layer2.conciseness : "—"}</td>
  </tr>`).join("");

  const legend = COMPARISON_PROVIDERS.map((p) => `<span class="legend-item"><span class="legend-swatch" style="background:${p.color}"></span>${escapeHtml(p.label)}</span>`).join("");

  return `
    <div class="trend-card">
      <h5>${escapeHtml(group.scenarioId)} / ${escapeHtml(group.variant)}</h5>
      <div class="trend-legend">${legend}</div>
      ${svg}
      <button class="chart-table-toggle" data-target="${tableId}" type="button">Show as table</button>
      <div class="eval-table-wrap hidden" id="${tableId}">
        <table class="eval-table">
          <thead><tr><th>Run</th><th>Summarizer</th><th>Judge</th><th>Faithful.</th><th>Complete.</th><th>Concise.</th></tr></thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>
    </div>
  `;
}

function renderProviderComparisonSection(records) {
  if (!records.length) {
    return `
      <h3 class="eval-section-header">C. Provider Comparison — Local vs Claude vs Mistral, Across Runs</h3>
      <p class="eval-note">No judged runs yet. Trigger a pipeline from the <button class="inline-link" id="eval-pipeline-link" type="button">Pipeline page</button> with a judge provider selected — every judged run is logged here.</p>
    `;
  }
  const { groups, unknownCount } = groupHistoryForComparison(records);
  const rows = groups.map(renderComparisonRow).join("");
  const cards = groups.map(renderTrendCard).filter(Boolean).join("");
  const headerCells = COMPARISON_PROVIDERS.map((p) => `<th>${escapeHtml(p.label)} (latest)</th>`).join("");
  const unknownNote = unknownCount
    ? ` ${unknownCount} older run${unknownCount === 1 ? "" : "s"} scored before provider tracking (bulk <code>eval/judge.py</code> runs against pre-existing files) ${unknownCount === 1 ? "is" : "are"} excluded from the comparison below.`
    : "";
  return `
    <h3 class="eval-section-header">C. Provider Comparison — Local vs Claude vs Mistral, Across Runs</h3>
    <p class="eval-note">Faithfulness / completeness / conciseness (1-5, latest run per provider). The summarizer and the judge are independently selectable per run from the Pipeline page — each trend chart's table view shows which judge scored which run.${unknownNote}</p>
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead><tr><th>Scenario / Variant</th>${headerCells}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p class="eval-note" style="margin-top:20px;">Faithfulness over runs, in run order:</p>
    <div class="trend-chart-grid">${cards}</div>
  `;
}

// ---------- Custom Audio page ----------
let customPollTimer = null;
let customListPollTimer = null;

async function fetchCustomAudioList() {
  const res = await fetch("/api/custom-audio");
  if (!res.ok) throw new Error(`Failed to load custom audio list: ${res.status}`);
  return res.json();
}

function customStatusPill(status) {
  const map = {
    not_run: { cls: "neutral", label: "Not run yet" },
    processing: { cls: "processing", label: "Processing…" },
    done: { cls: "good", label: "Done" },
    error: { cls: "critical", label: "Error" },
  };
  const { cls, label } = map[status] || map.not_run;
  return `<span class="status-pill"><span class="status-dot ${cls}"></span>${label}</span>`;
}

async function renderCustomItemOutputs(container, file) {
  const [transcriptText, summaryText] = await Promise.all([
    fetchText(file.transcript_url),
    fetchText(file.summary_url),
  ]);
  const keyPoints = extractKeyPoints(summaryText);
  const blockId = `custom-full-${file.filename.replace(/\W/g, "_")}`;
  container.innerHTML = `
    <div class="transcript-block">
      <h4>Transcript</h4>
      <div class="transcript-text">${escapeHtml(transcriptText)}</div>
    </div>
    <div class="variant-block">
      <h4>Summary</h4>
      <div class="key-points">
        <div class="key-points-label">Key Points</div>
        <ul>${keyPoints.map((k) => `<li>${escapeHtml(k)}</li>`).join("") || "<li>(none extracted)</li>"}</ul>
      </div>
      <button class="full-toggle" data-target="${blockId}">Show full output ▾</button>
      <div class="full-text hidden" id="${blockId}">${renderMarkdownLite(summaryText)}</div>
    </div>
  `;
  container.querySelector(".full-toggle").addEventListener("click", (e) => {
    const target = document.getElementById(e.target.dataset.target);
    const isHidden = target.classList.toggle("hidden");
    e.target.textContent = isHidden ? "Show full output ▾" : "Hide full output ▴";
  });
}

function renderCustomAudioList(data) {
  const root = document.getElementById("custom-root");
  root.innerHTML = `<p class="custom-intro">Files dropped into <code>custom/audio/</code> show up here automatically. Click "Run pipeline" to transcribe and summarize a new one (runs the plain v1 baseline pipeline — no scripted meeting context/checklist applies to real audio).</p>`;

  if (!data.files.length) {
    root.innerHTML += `<div class="custom-empty">No audio files found yet. Copy a .wav/.mp3/.m4a/.ogg/.flac file into <code>custom/audio/</code> and it'll appear here within a few seconds.</div>`;
    return;
  }

  for (const file of data.files) {
    const item = document.createElement("div");
    item.className = "custom-item";
    item.innerHTML = `
      <div class="custom-item-head">
        <h4>${escapeHtml(file.filename)}</h4>
        ${customStatusPill(file.status)}
      </div>
      <audio controls src="${file.audio_url}"></audio>
      <div class="custom-actions"></div>
      <div class="custom-outputs"></div>
    `;
    root.appendChild(item);

    const actions = item.querySelector(".custom-actions");
    const outputs = item.querySelector(".custom-outputs");

    if (file.status === "not_run" || file.status === "error") {
      const select = document.createElement("select");
      select.className = "provider-select";
      select.innerHTML = `
        <option value="local">Local (Qwen2.5)</option>
        <option value="mistral">Local (Mistral 7B)</option>
        <option value="claude">Claude (Haiku 4.5)</option>
      `;
      const btn = document.createElement("button");
      btn.className = "run-btn";
      btn.textContent = file.status === "error" ? "Retry pipeline" : "Run pipeline";
      btn.addEventListener("click", () => triggerRun(file.filename, btn, select.value));
      actions.appendChild(select);
      actions.appendChild(btn);
      if (file.status === "error") {
        actions.insertAdjacentHTML("beforeend", `<div class="custom-processing-note">Last error: ${escapeHtml(file.error || "unknown")}</div>`);
      }
    } else if (file.status === "processing") {
      actions.innerHTML = `<button class="run-btn" disabled>Processing…</button>
        <div class="custom-processing-note">Transcribing + summarizing — first run also loads Whisper and the local LLM, can take a couple of minutes.</div>`;
    } else if (file.status === "done") {
      renderCustomItemOutputs(outputs, file);
    }
  }
}

async function refreshCustomAudioList() {
  try {
    const data = await fetchCustomAudioList();
    renderCustomAudioList(data);
  } catch (err) {
    document.getElementById("custom-root").innerHTML =
      `<p>Could not load custom audio list (${escapeHtml(err.message)}). Make sure you're running <code>python webapp/server.py</code>, not a plain static server.</p>`;
  }
}

async function triggerRun(filename, btn, provider) {
  btn.disabled = true;
  btn.textContent = "Starting…";
  try {
    await fetch("/api/run-pipeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename, provider }),
    });
  } finally {
    refreshCustomAudioList();
  }
}

function startCustomPagePolling() {
  stopCustomPagePolling();
  refreshCustomAudioList();
  customListPollTimer = setInterval(refreshCustomAudioList, 4000);
}

function stopCustomPagePolling() {
  if (customListPollTimer) {
    clearInterval(customListPollTimer);
    customListPollTimer = null;
  }
}

// ---------- Pipeline page ----------
const PIPELINE_META = {
  v1: { desc: "Transcript in, structured summary out. No extra grounding." },
  v2: { desc: "Meeting context injected into the prompt — baseline and context-aware summaries side by side." },
  v3: { desc: "Context-aware summarizer plus a deterministic checklist coverage section." },
  v4: { desc: "A third voice (AI Assistant) joins the recording and takes notes live." },
  story: { desc: "5 weekly meetings — a summarizer with no memory of prior weeks vs. one given a running history." },
};

const PIPELINE_STAGE_LABELS = {
  recording: "Recording",
  transcribing: "Transcribing",
  summarizing: "Summarizing",
  summarizing_baseline: "Summarizing (baseline)",
  summarizing_context: "Summarizing (context)",
  judging: "Judging",
  judging_baseline: "Judging (baseline)",
  judging_context: "Judging (context)",
  done: "Done",
};

const PIPELINE_STATUS_LABELS = {
  done: "Done", error: "Error", running: "Running", not_run: "Not run",
};

// Provider/regenerate choices persist across polling refreshes, keyed by
// pipeline id, so a poll tick mid-decision doesn't reset the user's pick.
const PIPELINE_UI_STATE = {};
function pipelineUiState(id) {
  if (!PIPELINE_UI_STATE[id]) PIPELINE_UI_STATE[id] = { provider: "local", judgeProvider: "local", regenerate: false };
  return PIPELINE_UI_STATE[id];
}

let pipelinePollTimer = null;

async function fetchPipelineStatus() {
  const res = await fetch("/api/pipeline/status");
  if (!res.ok) throw new Error(`Failed to load pipeline status: ${res.status}`);
  return res.json();
}

function pipelineStatusDotClass(status) {
  if (status === "done") return "good";
  if (status === "error") return "critical";
  if (status === "running") return "processing";
  return "neutral";
}

function renderPipelineStats(pipelines) {
  const tiles = [
    { label: "Pipelines", value: pipelines.length },
    { label: "Running now", value: pipelines.filter((p) => p.status === "running").length },
    { label: "Completed", value: pipelines.filter((p) => p.status === "done").length },
    { label: "Errors", value: pipelines.filter((p) => p.status === "error").length },
  ];
  return `<div class="stat-row">${tiles.map((t) => `
    <div class="stat-tile">
      <div class="stat-value">${t.value}</div>
      <div class="stat-label">${escapeHtml(t.label)}</div>
    </div>
  `).join("")}</div>`;
}

function renderStageTrack(pipeline) {
  const stages = pipeline.stages.filter((s) => s !== "done");
  let currentIndex = pipeline.stage ? stages.indexOf(pipeline.stage) : -1;
  // Just-started: the subprocess hasn't written its first stage update yet.
  // Show the first stage as active rather than leaving the whole track
  // looking inert while that lands.
  if (pipeline.status === "running" && currentIndex === -1) currentIndex = 0;
  const chips = stages.map((stage, i) => {
    let state = "pending";
    if (pipeline.status === "done") {
      state = "complete";
    } else if (pipeline.status === "error") {
      state = i < currentIndex ? "complete" : i === currentIndex ? "error" : "pending";
    } else if (i < currentIndex) {
      state = "complete";
    } else if (i === currentIndex) {
      state = "active";
    }
    return `<div class="stage-chip ${state}"><span class="stage-dot"></span><span class="stage-name">${escapeHtml(PIPELINE_STAGE_LABELS[stage] || stage)}</span></div>`;
  });
  return `<div class="stage-track">${chips.join('<span class="stage-connector"></span>')}</div>`;
}

function renderPipelinePanel(pipeline) {
  const ui = pipelineUiState(pipeline.id);
  const running = pipeline.status === "running";
  const PROVIDER_LABELS = { claude: "Claude (Haiku 4.5)", local: "Local (Qwen2.5)", mistral: "Local (Mistral 7B)" };
  const providerLabel = PROVIDER_LABELS[pipeline.provider] || null;
  return `
    <div class="pipeline-panel" data-id="${pipeline.id}">
      <div class="pipeline-panel-head">
        <div>
          <h4>${escapeHtml(pipeline.label)}</h4>
          <p class="pipeline-desc">${escapeHtml((PIPELINE_META[pipeline.id] || {}).desc || "")}</p>
        </div>
        <span class="status-pill"><span class="status-dot ${pipelineStatusDotClass(pipeline.status)}"></span>${PIPELINE_STATUS_LABELS[pipeline.status] || pipeline.status}</span>
      </div>
      ${renderStageTrack(pipeline)}
      <div class="pipeline-meta">
        ${pipeline.detail ? `<span class="pipeline-detail">${escapeHtml(pipeline.detail)}</span>` : ""}
        ${providerLabel ? `<span class="pipeline-provider-used">Last run: ${escapeHtml(providerLabel)}</span>` : ""}
      </div>
      ${pipeline.error ? `<div class="pipeline-error">${escapeHtml(pipeline.error)}</div>` : ""}
      <div class="pipeline-controls">
        <label class="control-label">
          Summarize with
          <select class="provider-select" ${running ? "disabled" : ""}>
            <option value="local" ${ui.provider === "local" ? "selected" : ""}>Local (Qwen2.5)</option>
            <option value="mistral" ${ui.provider === "mistral" ? "selected" : ""}>Local (Mistral 7B)</option>
            <option value="claude" ${ui.provider === "claude" ? "selected" : ""}>Claude (Haiku 4.5)</option>
          </select>
        </label>
        <label class="control-label">
          Judge with
          <select class="judge-provider-select" ${running ? "disabled" : ""}>
            <option value="local" ${ui.judgeProvider === "local" ? "selected" : ""}>Local (Qwen2.5)</option>
            <option value="mistral" ${ui.judgeProvider === "mistral" ? "selected" : ""}>Local (Mistral 7B)</option>
            <option value="claude" ${ui.judgeProvider === "claude" ? "selected" : ""}>Claude (Haiku 4.5)</option>
          </select>
        </label>
        <label class="regenerate-label">
          <input type="checkbox" class="regenerate-check" ${ui.regenerate ? "checked" : ""} ${running ? "disabled" : ""}>
          Regenerate recording
        </label>
        <button class="run-btn" ${running ? "disabled" : ""}>${running ? "Running…" : pipeline.status === "error" ? "Retry" : "Run pipeline"}</button>
      </div>
    </div>
  `;
}

async function triggerPipelineRun(pipelineId, panel) {
  const ui = pipelineUiState(pipelineId);

  // Optimistic feedback — the server won't report "running" until the
  // subprocess has actually spawned, and the next poll may be up to 3s
  // away, so reflect the click immediately rather than leaving the button
  // looking inert while that round trip happens.
  const btn = panel.querySelector(".run-btn");
  btn.disabled = true;
  btn.textContent = "Starting…";
  panel.querySelector(".provider-select").disabled = true;
  panel.querySelector(".judge-provider-select").disabled = true;
  panel.querySelector(".regenerate-check").disabled = true;

  try {
    await fetch("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pipeline: pipelineId, provider: ui.provider,
        judge_provider: ui.judgeProvider, regenerate: ui.regenerate,
      }),
    });
  } finally {
    refreshPipelinePage();
    // One quick follow-up refresh so the first real stage (recording /
    // transcribing) shows up well before the next regular 3s poll tick.
    setTimeout(refreshPipelinePage, 600);
  }
}

async function refreshPipelinePage() {
  const root = document.getElementById("pipeline-root");
  try {
    const data = await fetchPipelineStatus();
    root.innerHTML = `
      <p class="pipeline-intro">Trigger any of the five pipelines and watch it move through recording, transcription, summarization, and judging. Transcription always runs locally (Whisper); pick a summarization and judge provider per run. Every judged run is added to the run history on the <button class="inline-link" id="pipeline-eval-link" type="button">Evaluation page</button>.</p>
      ${renderPipelineStats(data.pipelines)}
      <div class="pipeline-grid">${data.pipelines.map(renderPipelinePanel).join("")}</div>
    `;
    root.querySelectorAll(".pipeline-panel").forEach((panel) => {
      const id = panel.dataset.id;
      const select = panel.querySelector(".provider-select");
      const judgeSelect = panel.querySelector(".judge-provider-select");
      const checkbox = panel.querySelector(".regenerate-check");
      select.addEventListener("change", () => { pipelineUiState(id).provider = select.value; });
      judgeSelect.addEventListener("change", () => { pipelineUiState(id).judgeProvider = judgeSelect.value; });
      checkbox.addEventListener("change", () => { pipelineUiState(id).regenerate = checkbox.checked; });
      const btn = panel.querySelector(".run-btn");
      if (!btn.disabled) {
        btn.addEventListener("click", () => triggerPipelineRun(id, panel));
      }
    });
    const evalLink = document.getElementById("pipeline-eval-link");
    if (evalLink) {
      evalLink.addEventListener("click", () => {
        document.querySelector('.nav-item[data-page="evaluation"]').click();
      });
    }
  } catch (err) {
    root.innerHTML = `<p>Could not load pipeline status (${escapeHtml(err.message)}). Make sure you're running <code>python webapp/server.py</code>, not a plain static server.</p>`;
  }
}

function startPipelinePagePolling() {
  stopPipelinePagePolling();
  refreshPipelinePage();
  pipelinePollTimer = setInterval(refreshPipelinePage, 3000);
}

function stopPipelinePagePolling() {
  if (pipelinePollTimer) {
    clearInterval(pipelinePollTimer);
    pipelinePollTimer = null;
  }
}

// ---------- Story page ----------
async function loadStoryResults() {
  const res = await fetch("/eval/output/story_results.json");
  if (!res.ok) throw new Error(`Failed to load story results: ${res.status}`);
  return res.json();
}

async function loadStoryProbes() {
  const res = await fetch("/eval/output/story_probes.json");
  if (!res.ok) throw new Error(`Failed to load story probes: ${res.status}`);
  return res.json();
}

function checkRow(pass, label, detailHtml) {
  return `
    <div class="probe-row">
      <span class="status-pill"><span class="status-dot ${pass ? "good" : "critical"}"></span>${pass ? "Pass" : "Fail"}</span>
      <span class="probe-label">${label}</span>
    </div>
    ${detailHtml || ""}
  `;
}

function renderVariantChecks(weekProbeEntry, variantKey) {
  if (!weekProbeEntry) return "";
  let html = `<div class="probe-block"><div class="key-points-label">Targeted checks</div>`;

  const noise = weekProbeEntry.noise[variantKey];
  html += checkRow(
    !noise.leaked,
    "No small-talk leakage into Topic/Key Points/Decisions/Actions",
    noise.leaked ? `<div class="mismatch">Found: ${escapeHtml(noise.keywords_found.join(", "))}</div>` : ""
  );

  const det = weekProbeEntry.deterministic_checks || {};
  if (det.conflation) {
    const c = det.conflation[variantKey];
    html += checkRow(
      !c.conflated,
      "Dark mode kept separate from legal/privacy review (deterministic check)",
      c.conflated ? c.offending_lines.map((l) => `<div class="mismatch">${escapeHtml(l)}</div>`).join("") : ""
    );
  }
  if (det.stale_actions) {
    const s = det.stale_actions[variantKey];
    html += checkRow(
      !s.stale,
      "No stale-action carryover from a prior meeting (deterministic check)",
      s.stale ? s.matches.map((m) => `<div class="mismatch">"${escapeHtml(m.current_bullet)}" closely repeats "${escapeHtml(m.matched_history_phrase)}" (${Math.round(m.overlap_ratio * 100)}% word overlap)</div>`).join("") : ""
    );
  }

  for (const probe of weekProbeEntry.probes) {
    const p = probe[variantKey];
    html += checkRow(
      p.pass,
      probe.question,
      `<div class="probe-rationale">${escapeHtml(p.rationale || "")}</div>`
    );
  }

  html += `</div>`;
  return html;
}

function deltaCell(b, c) {
  if (b === null || b === undefined || c === null || c === undefined) {
    return `<span class="score-num">—</span>`;
  }
  let cls = "neutral", arrow = "=";
  if (c > b) { cls = "good"; arrow = "▲"; }
  else if (c < b) { cls = "critical"; arrow = "▼"; }
  return `<span class="score-num">${b}</span> <span class="delta-arrow ${cls}">${arrow}</span> <span class="score-num">${c}</span>`;
}

function renderStoryScoreTable(results) {
  let html = `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead>
          <tr>
            <th>Week</th>
            <th>Faithfulness (B &rarr; C)</th>
            <th>Completeness (B &rarr; C)</th>
            <th>Conciseness (B &rarr; C)</th>
            <th>Continuity (B &rarr; C)</th>
          </tr>
        </thead>
        <tbody>
  `;
  for (const m of results.meetings) {
    const bl = m.baseline.layer2;
    const cl = m.with_context.layer2;
    const bCont = m.baseline.continuity ? m.baseline.continuity.continuity : null;
    const cCont = m.with_context.continuity ? m.with_context.continuity.continuity : null;
    html += `
      <tr>
        <td>${m.label}</td>
        <td>${deltaCell(bl.faithfulness, cl.faithfulness)}</td>
        <td>${deltaCell(bl.completeness, cl.completeness)}</td>
        <td>${deltaCell(bl.conciseness, cl.conciseness)}</td>
        <td>${deltaCell(bCont, cCont)}</td>
      </tr>
    `;
  }
  html += `</tbody></table></div>`;
  return html;
}

function renderStoryMeeting(meeting, texts, evalEntry, probeEntry) {
  const { transcriptText, baselineText, contextText } = texts;
  const baselineKP = extractKeyPoints(baselineText);
  const contextKP = extractKeyPoints(contextText);
  const transcriptId = `story-transcript-${meeting.week}`;

  const bl = evalEntry ? evalEntry.baseline.layer2 : null;
  const cl = evalEntry ? evalEntry.with_context.layer2 : null;
  const bCont = evalEntry && evalEntry.baseline.continuity ? evalEntry.baseline.continuity.continuity : null;
  const cCont = evalEntry && evalEntry.with_context.continuity ? evalEntry.with_context.continuity.continuity : null;
  const bClaims = (bl && bl.unsupported_claims) || [];
  const cClaims = (cl && cl.unsupported_claims) || [];

  const scoreLine = (l2, cont) => l2
    ? `Faithfulness ${l2.faithfulness}/5 &middot; Completeness ${l2.completeness}/5 &middot; Conciseness ${l2.conciseness}/5${cont !== null ? ` &middot; Continuity ${cont}/5` : ""}`
    : "";

  const claimsBlock = (claims) => claims.length
    ? `<div class="key-points-label">Unsupported claims (judge-flagged)</div>` +
      claims.map((c) => `<div class="mismatch">${escapeHtml(c)}</div>`).join("")
    : "";

  return `
    <div class="story-meeting">
      <div class="story-meeting-head"><h3>${meeting.label}</h3></div>

      <div class="audio-block">
        <div class="block-label">Recording</div>
        <audio controls src="${meeting.audio}"></audio>
        <a class="audio-link" href="${meeting.audio}" download>Download audio</a>
      </div>

      <button class="full-toggle" data-target="${transcriptId}">Show transcript &#9662;</button>
      <div class="transcript-block hidden" id="${transcriptId}">
        <h4>Transcript</h4>
        <div class="transcript-text">${escapeHtml(transcriptText)}</div>
      </div>

      <div class="compare-grid">
        <div class="compare-col">
          <h5>Baseline (isolated)</h5>
          <div class="score-row">${scoreLine(bl, bCont)}</div>
          <div class="key-points">
            <div class="key-points-label">Key Points</div>
            <ul>${baselineKP.map((k) => `<li>${escapeHtml(k)}</li>`).join("") || "<li>(none extracted)</li>"}</ul>
          </div>
          <div class="full-text">${renderMarkdownLite(baselineText)}</div>
          ${claimsBlock(bClaims)}
          ${renderVariantChecks(probeEntry, "baseline")}
        </div>
        <div class="compare-col">
          <h5>With Context + History</h5>
          <div class="score-row">${scoreLine(cl, cCont)}</div>
          <div class="key-points">
            <div class="key-points-label">Key Points</div>
            <ul>${contextKP.map((k) => `<li>${escapeHtml(k)}</li>`).join("") || "<li>(none extracted)</li>"}</ul>
          </div>
          <div class="full-text">${renderMarkdownLite(contextText)}</div>
          ${claimsBlock(cClaims)}
          ${renderVariantChecks(probeEntry, "with_context")}
        </div>
      </div>

      ${STORY_CURATOR_NOTES[meeting.week] ? `<div class="curator-note"><strong>Human review note:</strong> ${escapeHtml(STORY_CURATOR_NOTES[meeting.week])}</div>` : ""}
    </div>
  `;
}

async function renderStoryPage() {
  const root = document.getElementById("story-root");
  root.innerHTML = "<p>Loading…</p>";
  try {
    let results = null;
    try {
      results = await loadStoryResults();
    } catch (_err) {
      results = null;
    }

    let probes = null;
    try {
      probes = await loadStoryProbes();
    } catch (_err) {
      probes = null;
    }

    let html = `
      <p class="custom-intro">Five weekly status syncs about the same Mobile App Redesign project, told as one continuous story instead of a single snapshot (see <a href="/story/README.md">story/README.md</a>). Each meeting is summarized two ways: <strong>Baseline</strong> (transcript only, no memory of prior weeks) and <strong>With Context + History</strong> (project background plus a running history built from every prior week's own generated summary). Each meeting also opens with a few lines of unrelated small talk (weather, a show, a game, coffee, traffic) to test whether it leaks into the summary.</p>
      <div class="story-verdict">
        <strong>Verdict:</strong> the holistic 1-5 judge scores are nearly identical between baseline and context-aware across all 5 meetings — on numbers alone, context looks like it made no difference. Targeted checks tell a clearer story: a <strong>deterministic</strong> check (not an LLM judgment) shows baseline conflates the Week 3 dark-mode and legal/privacy workstreams into one, while context-aware keeps them correctly separate — and the same deterministic check shows context-aware's Week 5 summary repeating Week 4's already-completed actions as if still pending, while baseline (with no history to leak) does not. Two of the original LLM-judge probes were swapped for these deterministic checks after the judge itself got both wrong on manual verification — see the human review notes and per-meeting "Targeted checks" below.
      </div>
    `;

    html += results
      ? renderStoryScoreTable(results)
      : `<p class="eval-note">Could not load eval/output/story_results.json — run <code>python eval/story_judge.py</code> to generate scores. Showing recordings/transcripts/summaries without scores.</p>`;

    if (!probes) {
      html += `<p class="eval-note">Could not load eval/output/story_probes.json — run <code>python eval/story_probes.py</code> to generate targeted checks.</p>`;
    }

    const meetingsHtml = await Promise.all(STORY_MEETINGS.map(async (meeting) => {
      const [transcriptText, baselineText, contextText] = await Promise.all([
        fetchText(meeting.transcript),
        fetchText(meeting.baseline),
        fetchText(meeting.context),
      ]);
      const evalEntry = results ? results.meetings.find((m) => m.week === meeting.week) : null;
      const probeEntry = probes ? probes.weeks.find((w) => w.week === meeting.week) : null;
      return renderStoryMeeting(meeting, { transcriptText, baselineText, contextText }, evalEntry, probeEntry);
    }));

    root.innerHTML = html + meetingsHtml.join("");

    root.querySelectorAll(".full-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = document.getElementById(btn.dataset.target);
        const isHidden = target.classList.toggle("hidden");
        btn.innerHTML = isHidden ? "Show transcript &#9662;" : "Hide transcript &#9652;";
      });
    });
  } catch (err) {
    root.innerHTML = `<p>Could not load story data (${escapeHtml(err.message)}). Run <code>python story/src/main.py</code> from the project root first.</p>`;
  }
}

// ---------- Nav ----------
function setupNav() {
  const navItems = document.querySelectorAll(".nav-item");
  const pages = {
    scenarios: document.getElementById("scenarios-page"),
    story: document.getElementById("story-page"),
    custom: document.getElementById("custom-page"),
    pipeline: document.getElementById("pipeline-page"),
    evaluation: document.getElementById("evaluation-page"),
  };
  navItems.forEach((item) => {
    item.addEventListener("click", () => {
      navItems.forEach((t) => t.setAttribute("aria-pressed", "false"));
      item.setAttribute("aria-pressed", "true");
      Object.entries(pages).forEach(([key, el]) => {
        el.classList.toggle("hidden", key !== item.dataset.page);
      });

      // Always re-render on nav click, not just the first visit — both pages
      // can change from Pipeline-triggered runs (story/v1-v4 re-summarized,
      // new judged runs added to history) after the first time you look.
      if (item.dataset.page === "evaluation") {
        renderEvaluationPage();
      }

      if (item.dataset.page === "story") {
        renderStoryPage();
      }

      if (item.dataset.page === "custom") {
        startCustomPagePolling();
      } else {
        stopCustomPagePolling();
      }

      if (item.dataset.page === "pipeline") {
        startPipelinePagePolling();
      } else {
        stopPipelinePagePolling();
      }
    });
  });
}

function setupDrawer() {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("drawer-toggle");
  toggle.addEventListener("click", () => sidebar.classList.toggle("collapsed"));
}

renderTechSummary();
renderEvalSummaryTable();
renderScenarioGrid();
setupNav();
setupDrawer();
