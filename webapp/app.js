const SCENARIOS = [
  {
    id: "phase1-baseline",
    title: "Phase 1 — Basic summary",
    description: "Transcript in, structured summary out. No extra grounding.",
    audio: "/audio-generation/output/01-kickoff/recording.wav",
    transcript: "/phase1-baseline/output/transcript.txt",
    variants: [
      { key: "baseline", label: "Summary", path: "/phase1-baseline/output/summary.txt" },
    ],
  },
  {
    id: "phase2-checklist",
    title: "Phase 2 — Checklist coverage check",
    description: "Same kickoff recording, plus a deterministic checklist coverage section and context-aware prompting.",
    audio: "/audio-generation/output/01-kickoff/recording.wav",
    transcript: "/phase2-checklist/output/transcript.txt",
    variants: [
      { key: "context_checklist", label: "Summary + Checklist", path: "/phase2-checklist/output/summary.txt" },
    ],
  },
  {
    id: "phase3-context",
    title: "Phase 3 — Context-aware summarization",
    description: "Meeting context injected into the prompt before the transcript — baseline and context-aware summaries side by side.",
    audio: "/audio-generation/output/01-kickoff/recording.wav",
    transcript: "/phase3-context/output/transcript.txt",
    variants: [
      { key: "baseline", label: "Baseline (no context)", path: "/phase3-context/output/summary_baseline.txt" },
      { key: "with_context", label: "With context", path: "/phase3-context/output/summary_with_context.txt" },
    ],
  },
  {
    id: "phase4-assistant",
    title: "Phase 4 — AI Assistant as third actor",
    description: "A third voice (AI Assistant) joins the recording itself and takes notes live.",
    audio: "/phase4-assistant/output/recording.wav",
    transcript: "/phase4-assistant/output/transcript.txt",
    variants: [
      { key: "context_checklist_assistant", label: "Summary + Checklist", path: "/phase4-assistant/output/summary.txt" },
    ],
  },
  {
    id: "phase7-reference-rag",
    title: "Phase 7 — Reference-document RAG",
    description: "Same kickoff recording, plus TF-IDF retrieval over the project's own reference documents (PRD, design spec, payments vendor doc) — baseline and reference-grounded summaries side by side.",
    audio: "/audio-generation/output/01-kickoff/recording.wav",
    transcript: "/phase7-reference-rag/output/transcript.txt",
    variants: [
      { key: "baseline", label: "Baseline (transcript only)", path: "/phase7-reference-rag/output/summary_baseline.txt" },
      { key: "with_references", label: "With references", path: "/phase7-reference-rag/output/summary_with_references.txt" },
    ],
  },
];

const STORY_MEETINGS = [
  ["01-kickoff", "Kickoff"], ["02-requirements-review", "Requirements Review"],
  ["03-design-review", "Design Review"], ["04-sprint-status-1", "Sprint 1 Status"],
  ["05-sprint-status-2", "Sprint 2 Status"], ["06-sprint-status-3", "Sprint 3 Status"],
  ["07-sprint-status-4", "Sprint 4 Status"], ["08-sprint-status-5", "Sprint 5 Status"],
  ["09-sprint-status-6", "Sprint 6 Status"], ["10-sprint-status-7", "Sprint 7 Status"],
  ["11-test-plan-review", "Test Plan Review"], ["12-uat-kickoff", "UAT Kickoff"],
  ["13-uat-results", "UAT Results / Bug Triage"], ["14-go-live-readiness", "Go-Live Readiness"],
  ["15-launch-retro", "Launch Retro"],
].map(([slug, label], i) => ({
  slug,
  label: `${i + 1}. ${label}`,
  audio: `/audio-generation/output/${slug}/recording.wav`,
  transcript: `/phase6-history/output/${slug}/transcript.txt`,
  baseline: `/phase6-history/output/${slug}/summary_baseline.txt`,
  context: `/phase6-history/output/${slug}/summary_with_context.txt`,
}));

// Findings from reading the actual generated text, not something the
// automated eval surfaced on its own (see eval/story_judge.py) — kept here
// as explicit, attributed human-review notes rather than folded into the
// scored data, so the UI never implies these came from the judge. Keyed by
// slug — see phase6-history/README.md for the full write-up.
const STORY_CURATOR_NOTES = {
  "04-sprint-status-1": "The context-aware summary's Actions list \"Promote dark mode from stretch to committed P1 scope\" and \"Confirm payments sandbox access is provisioned\" as pending — but both were already decided/done in the prior meeting (03-design-review), and this meeting's own transcript doesn't restate them (dark mode is \"not started yet\", payments sandbox is already \"stood up\"). This is stale history leaking into current-meeting content. Baseline (no history to leak) doesn't show this.",
  "12-uat-kickoff": "The context-aware summary lists \"Start recruiting testers for UAT\" as a pending action — but this meeting's own transcript says recruiting is already done (\"Eight external testers recruited... all confirmed for next week\"). The prior meeting (11-test-plan-review) is where recruiting was assigned; the summarizer carried that forward as still-pending instead of registering that this meeting resolves it. The clearest stale-action carryover found in this run.",
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
  // triple. variantKey folds in the meeting slug for phase6-history/ (each of
  // its 15 meetings has its own "baseline"/"with_context" pair) so aggregating
  // "all of this provider's records for this scenario" below correctly
  // covers all 15 meetings instead of just whichever was judged last.
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
    if (id !== "phase6-history") return werById[id] !== undefined ? labelForWer(werById[id]) : { label: "—", cls: "neutral" };
    const storyWerValues = STORY_MEETINGS.map((m) => werById[`phase6-history-${m.slug}`]).filter((v) => v !== undefined);
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
    const scenario = id === "phase6-history" ? null : (results ? results.scenarios.find((s) => s.id === id) : null);
    const scenarioResults = id === "phase6-history" ? storyResults : null;
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
    ...scenarioRows("phase1-baseline", "Phase 1 — Basic summary", "—"),
    ...scenarioRows("phase2-checklist", "Phase 2 — Checklist coverage", "—"),
    ...scenarioRows("phase3-context", "Phase 3 — Context-aware", "Mixed — sharper wording, but captured fewer real action items than the plain version in this test."),
    ...scenarioRows("phase4-assistant", "Phase 4 — AI Assistant", "—"),
    ...scenarioRows("phase6-history", "Phase 6 (15 meetings)", "Mostly positive — higher faithfulness/completeness and zero small-talk leakage vs. baseline, but carries stale already-done actions forward as pending in 2 of 15 meetings. See the Story page for details."),
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

const SCENARIO_LINKS = [
  {
    title: "Phase 5 — Office Agent",
    description: "Claude tool-use agent writes Word/Excel docs under simulated network conditions.",
    page: "roadmap",
    note: "See Roadmap → Phase 5",
  },
  {
    title: "Phase 6 — Meeting History (15 meetings)",
    description: "A full project lifecycle tracked across 15 meetings with running context carried forward.",
    page: "story",
    note: "See Story page",
  },
  {
    title: "Phase 8 — Voice Query",
    description: "Ask a spoken question and get a text answer drawn from all past meetings and summaries.",
    page: "voicequery",
    note: "See Voice Query page",
  },
];

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
  for (const link of SCENARIO_LINKS) {
    const card = document.createElement("button");
    card.className = "scenario-card scenario-card-link";
    card.innerHTML = `<h3>${link.title}</h3><p>${link.description}</p><span class="scenario-link-note">${link.note} &rarr;</span>`;
    card.addEventListener("click", () => {
      document.querySelector(`.nav-item[data-page="${link.page}"]`).click();
    });
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
  if (!tier || tier.wer == null) return "—";
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

// ---------- Pipeline page ----------
const PIPELINE_META = {
  "phase1-baseline": { desc: "Transcript in, structured summary out. No extra grounding." },
  "phase2-checklist": { desc: "Context-aware summarizer plus a deterministic checklist coverage section." },
  "phase3-context": { desc: "Meeting context injected into the prompt — baseline and context-aware summaries side by side." },
  "phase4-assistant": { desc: "A third voice (AI Assistant) joins the recording and takes notes live." },
  "phase6-history": { desc: "15 lifecycle meetings — a summarizer with no memory of prior meetings vs. one given a running history." },
  "phase7-reference-rag": { desc: "Same kickoff recording, plus TF-IDF retrieval over the project's reference documents (PRD, design spec, vendor doc) to enrich the summary." },
};

// Pipelines whose main.py accepts --retrieval tfidf|faiss (see
// faiss_retrieval.py) — only phase7-reference-rag so far.
const RETRIEVAL_CAPABLE_PIPELINES = new Set(["phase7-reference-rag"]);

const PIPELINE_STAGE_LABELS = {
  recording: "Recording",
  transcribing: "Transcribing",
  retrieving: "Retrieving references",
  summarizing: "Summarizing",
  summarizing_baseline: "Summarizing (baseline)",
  summarizing_context: "Summarizing (context)",
  summarizing_with_references: "Summarizing (with references)",
  judging: "Judging",
  judging_baseline: "Judging (baseline)",
  judging_context: "Judging (context)",
  judging_with_references: "Judging (with references)",
  done: "Done",
};

const PIPELINE_STATUS_LABELS = {
  done: "Done", error: "Error", running: "Running", not_run: "Not run",
};

// Provider/regenerate choices persist across polling refreshes, keyed by
// pipeline id, so a poll tick mid-decision doesn't reset the user's pick.
const PIPELINE_UI_STATE = {};
function pipelineUiState(id) {
  if (!PIPELINE_UI_STATE[id]) PIPELINE_UI_STATE[id] = { provider: "local", judgeProvider: "local", regenerate: false, retrieval: "tfidf" };
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
        ${RETRIEVAL_CAPABLE_PIPELINES.has(pipeline.id) ? `
        <label class="control-label">
          Retrieval
          <select class="retrieval-select" ${running ? "disabled" : ""}>
            <option value="tfidf" ${ui.retrieval === "tfidf" ? "selected" : ""}>TF-IDF</option>
            <option value="faiss" ${ui.retrieval === "faiss" ? "selected" : ""}>FAISS (embeddings)</option>
          </select>
        </label>
        ` : ""}
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
        retrieval: RETRIEVAL_CAPABLE_PIPELINES.has(pipelineId) ? ui.retrieval : undefined,
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
      <p class="pipeline-intro">Trigger any of the six pipelines and watch it move through recording, transcription, summarization, and judging. Transcription always runs locally (Whisper); pick a summarization and judge provider per run. Every judged run is added to the run history on the <button class="inline-link" id="pipeline-eval-link" type="button">Evaluation page</button>.</p>
      ${renderPipelineStats(data.pipelines)}
      <div class="pipeline-grid">${data.pipelines.map(renderPipelinePanel).join("")}</div>
    `;
    root.querySelectorAll(".pipeline-panel").forEach((panel) => {
      const id = panel.dataset.id;
      const select = panel.querySelector(".provider-select");
      const judgeSelect = panel.querySelector(".judge-provider-select");
      const checkbox = panel.querySelector(".regenerate-check");
      const retrievalSelect = panel.querySelector(".retrieval-select");
      select.addEventListener("change", () => { pipelineUiState(id).provider = select.value; });
      judgeSelect.addEventListener("change", () => { pipelineUiState(id).judgeProvider = judgeSelect.value; });
      checkbox.addEventListener("change", () => { pipelineUiState(id).regenerate = checkbox.checked; });
      if (retrievalSelect) {
        retrievalSelect.addEventListener("change", () => { pipelineUiState(id).retrieval = retrievalSelect.value; });
      }
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

function storyMeetingTableRow(meeting, texts, evalEntry) {
  const bl = evalEntry ? evalEntry.baseline.layer2 : null;
  const cl = evalEntry ? evalEntry.with_context.layer2 : null;
  const bCont = evalEntry && evalEntry.baseline.continuity ? evalEntry.baseline.continuity.continuity : null;
  const cCont = evalEntry && evalEntry.with_context.continuity ? evalEntry.with_context.continuity.continuity : null;
  const hasNote = !!STORY_CURATOR_NOTES[meeting.slug];

  return `<tr class="story-row" data-slug="${meeting.slug}">
    <td>${escapeHtml(meeting.label)}${hasNote ? ' <span class="story-note-badge" title="Has human review note">*</span>' : ""}</td>
    <td>${bl ? bl.faithfulness : "—"}</td>
    <td>${bl ? bl.completeness : "—"}</td>
    <td>${bCont !== null ? bCont : "—"}</td>
    <td>${cl ? cl.faithfulness : "—"}</td>
    <td>${cl ? cl.completeness : "—"}</td>
    <td>${cCont !== null ? cCont : "—"}</td>
  </tr>`;
}

function renderStoryMeetingDetail(meeting, texts, evalEntry, probeEntry) {
  const { transcriptText, baselineText, contextText } = texts;
  const baselineKP = extractKeyPoints(baselineText);
  const contextKP = extractKeyPoints(contextText);
  const transcriptId = `story-transcript-${meeting.slug}`;

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

    ${STORY_CURATOR_NOTES[meeting.slug] ? `<div class="curator-note"><strong>Human review note:</strong> ${escapeHtml(STORY_CURATOR_NOTES[meeting.slug])}</div>` : ""}
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
      <p class="custom-intro">Fifteen meetings covering the Mobile App Redesign project's full lifecycle, kickoff through launch retro over roughly five months — a distinct meeting type each time (kickoff, requirements review, design review, seven sprint syncs, test plan review, UAT kickoff, UAT results, go-live readiness, launch retro), not a repeated weekly format (see <a href="/phase6-history/README.md">phase6-history/README.md</a>). Each meeting is summarized two ways: <strong>Baseline</strong> (transcript only, no memory of prior meetings) and <strong>With Context + History</strong> (project background plus a running history built from every prior meeting's own generated summary). Each meeting also opens with a few lines of unrelated small talk to test whether it leaks into the summary.</p>
      <div class="story-verdict">
        <strong>Verdict:</strong> context-aware scores a bit higher on the holistic judge (faithfulness 4.0/5 vs. baseline's 3.9/5, completeness 3.5/5 vs. 3.3/5 — continuity is identical at 4.6/5 for both, which doesn't distinguish them). Targeted <strong>deterministic</strong> checks (not LLM judgments) tell a more decisive story: baseline leaks small talk into the summary in 3 of 15 meetings, context-aware in 0 of 15 — a clean win for context. Context-aware also correctly conveys that the payments vendor issue is fully resolved by 09-sprint-status-6, where baseline's phrasing leaves it ambiguous. But context-aware has a real cost: it carries stale, already-resolved actions forward as still-pending in 2 of 15 meetings (04-sprint-status-1, 12-uat-kickoff) — baseline, having no history to leak, never does this. See the human review notes and per-meeting "Targeted checks" below.
      </div>
    `;

    if (!results) {
      html += `<p class="eval-note">Could not load eval/output/story_results.json — run <code>python eval/story_judge.py</code> to generate scores.</p>`;
    }
    if (!probes) {
      html += `<p class="eval-note">Could not load eval/output/story_probes.json — run <code>python eval/story_probes.py</code> to generate targeted checks.</p>`;
    }

    const meetingData = await Promise.all(STORY_MEETINGS.map(async (meeting) => {
      const [transcriptText, baselineText, contextText] = await Promise.all([
        fetchText(meeting.transcript),
        fetchText(meeting.baseline),
        fetchText(meeting.context),
      ]);
      const evalEntry = results ? results.meetings.find((m) => m.slug === meeting.slug) : null;
      const probeEntry = probes ? probes.meetings.find((w) => w.slug === meeting.slug) : null;
      return { meeting, texts: { transcriptText, baselineText, contextText }, evalEntry, probeEntry };
    }));

    html += `
      <p class="eval-note">Click a row to expand recording, transcript, and full summaries. <span class="story-note-badge">*</span> = has a human review note.</p>
      <div class="eval-table-wrap story-table-wrap">
        <table class="eval-table story-table">
          <thead>
            <tr>
              <th rowspan="2">Meeting</th>
              <th colspan="3" class="story-th-group">Baseline</th>
              <th colspan="3" class="story-th-group">With Context</th>
            </tr>
            <tr>
              <th>Faith.</th><th>Compl.</th><th>Contin.</th>
              <th>Faith.</th><th>Compl.</th><th>Contin.</th>
            </tr>
          </thead>
          <tbody>
    `;
    for (const d of meetingData) {
      html += storyMeetingTableRow(d.meeting, d.texts, d.evalEntry);
    }
    html += `</tbody></table></div>`;
    html += `<div id="story-detail"></div>`;

    root.innerHTML = html;

    root.querySelectorAll(".story-row").forEach((row) => {
      row.addEventListener("click", () => {
        const slug = row.dataset.slug;
        const d = meetingData.find((m) => m.meeting.slug === slug);
        const detail = document.getElementById("story-detail");
        const alreadyOpen = detail.dataset.slug === slug && !detail.classList.contains("hidden");
        if (alreadyOpen) {
          detail.classList.add("hidden");
          detail.dataset.slug = "";
          row.classList.remove("story-row-active");
          return;
        }
        root.querySelectorAll(".story-row-active").forEach((r) => r.classList.remove("story-row-active"));
        row.classList.add("story-row-active");
        detail.dataset.slug = slug;
        detail.classList.remove("hidden");
        detail.innerHTML = `<div class="story-meeting"><div class="story-meeting-head"><h3>${d.meeting.label}</h3></div>${renderStoryMeetingDetail(d.meeting, d.texts, d.evalEntry, d.probeEntry)}</div>`;
        detail.querySelectorAll(".full-toggle").forEach((btn) => {
          btn.addEventListener("click", () => {
            const target = document.getElementById(btn.dataset.target);
            const isHidden = target.classList.toggle("hidden");
            btn.innerHTML = isHidden ? "Show transcript &#9662;" : "Hide transcript &#9652;";
          });
        });
        detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    });
  } catch (err) {
    root.innerHTML = `<p>Could not load story data (${escapeHtml(err.message)}). Run <code>python phase6-history/src/main.py</code> from the project root first.</p>`;
  }
}

// ---------- Roadmap page ----------
function avg(nums) {
  const vals = nums.filter((n) => n !== null && n !== undefined && !Number.isNaN(n));
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
}

function fmtScore(n) {
  return n === null || n === undefined ? "—" : `${n.toFixed(1)}/5`;
}

function findVariant(results, scenarioId, variantName) {
  if (!results) return null;
  const scenario = results.scenarios.find((s) => s.id === scenarioId);
  if (!scenario) return null;
  return scenario.variants.find((v) => v.variant === variantName) || null;
}

function gapPill(label) {
  return `<span class="status-pill"><span class="status-dot critical"></span>${escapeHtml(label)}</span>`;
}

function statTile(value, label) {
  return `<div class="stat-tile"><div class="stat-value">${value}</div><div class="stat-label">${escapeHtml(label)}</div></div>`;
}

function statRow(tiles) {
  return `<div class="stat-row">${tiles.join("")}</div>`;
}

function roadmapVerdict(text) {
  return `<p class="roadmap-verdict">${text}</p>`;
}

function roadmapDetails(summaryText, innerHtml) {
  return `<details class="roadmap-details"><summary>${escapeHtml(summaryText)}</summary>${innerHtml}</details>`;
}

function renderFoundation(transcriptionData) {
  let html = `
    <div class="roadmap-foundation">
      <div class="roadmap-foundation-badge">Foundation — the shared input every phase builds on</div>
      <h3 class="eval-section-header" style="margin-top:0;padding-top:0;border-top:none;">Voice-to-Transcript — how accurately &amp; fast is speech turned into text?</h3>
      <p class="eval-note">The input is one project's <strong>15 meetings</strong> (kickoff → launch retro), recorded as audio. This step only does one thing: turn each recording into a text transcript. Everything measured here is per recording — the numbered Phases are a separate axis (added capabilities) that all read from these same transcripts.</p>
  `;

  if (!transcriptionData) {
    html += `<p class="eval-note">Could not load WER data. Run <code>python eval/transcription_quality.py</code>.</p></div>`;
    return html;
  }

  const scenarios = transcriptionData.scenarios;
  const avgWer = (tier) => avg(scenarios.map((s) => s.tiers[tier]?.wer));
  const avgClean = avgWer("clean");
  const avgHeavy = avgWer("heavy_noise");
  const avgRtf = avg(scenarios.map((s) => s.tiers.clean?.rtf));
  const avgSecs = avg(scenarios.map((s) => s.tiers.clean?.seconds));
  const speedup = avgRtf ? Math.round(1 / avgRtf) : null;

  // Worst heavy-noise recording — the one actually worth investigating.
  const worst = scenarios.reduce((w, s) =>
    (s.tiers.heavy_noise?.wer ?? 0) > (w.tiers.heavy_noise?.wer ?? 0) ? s : w, scenarios[0]);

  // Plain-English verdict, derived from the data so it stays honest if the
  // numbers change. Benchmark target (5–8% for domain audio) comes from the
  // eval's own wer_benchmark_note.
  const cleanVerdict = avgClean <= 0.08
    ? `<strong>${fmtPct(avgClean)} average error on clean audio</strong> — inside the commonly-cited 5–8% target for domain-specific speech`
    : `<strong>${fmtPct(avgClean)} average error on clean audio</strong> — above the 5–8% target for domain-specific speech`;
  html += roadmapVerdict(
    `${cleanVerdict}, and fast: ~${speedup}× quicker than real time on CPU. ` +
    `Accuracy holds up under mild noise but degrades under heavy noise ` +
    `(worst case: <strong>${escapeHtml(worst.id)}</strong> at ${fmtPct(worst.tiers.heavy_noise.wer)}). ` +
    `Since every phase reads these transcripts, this accuracy is the ceiling on all of them.`
  );

  html += statRow([
    statTile(fmtPct(avgClean), "Avg clean WER"),
    statTile(fmtPct(avgWer("light_noise")), "Avg light-noise WER"),
    statTile(fmtPct(avgHeavy), "Avg heavy-noise WER"),
    statTile(speedup ? `${speedup}×` : "—", "Faster than real time"),
  ]);

  // Engine comparison — only when more than one engine was benchmarked
  // (i.e. someone ran `--engines whisper,voxtral`). Each row is one engine's
  // averages over the same 15 recordings, read from s.engines[engine].
  const benchedEngines = transcriptionData.engines || ["whisper"];
  const ENGINE_LABELS = { whisper: `Whisper (${transcriptionData.whisper_model || "base"})`, voxtral: "Voxtral Mini 3B" };
  const multiEngine = benchedEngines.length > 1;
  if (multiEngine) {
    const engineAvg = (engine, tier, field) =>
      avg(scenarios.map((s) => s.engines?.[engine]?.[tier]?.[field]));
    html += `<h4 class="eval-subsection-header">Engine comparison — Whisper vs Voxtral</h4>`;
    html += `
      <div class="eval-table-wrap">
        <table class="eval-table">
          <thead><tr><th>Engine</th><th>Avg clean WER</th><th>Avg light-noise WER</th><th>Avg heavy-noise WER</th><th>Avg time / recording</th></tr></thead>
          <tbody>
    `;
    for (const engine of benchedEngines) {
      const t = engineAvg(engine, "clean", "seconds");
      html += `
        <tr>
          <td>${escapeHtml(ENGINE_LABELS[engine] || engine)}</td>
          <td>${fmtPct(engineAvg(engine, "clean", "wer"))}</td>
          <td>${fmtPct(engineAvg(engine, "light_noise", "wer"))}</td>
          <td>${fmtPct(engineAvg(engine, "heavy_noise", "wer"))}</td>
          <td>${t != null ? `${t.toFixed(1)}s` : "—"}</td>
        </tr>
      `;
    }
    html += `</tbody></table></div>`;
    html += `<p class="eval-legend eval-legend-note">Both engines run fully locally. Voxtral (a 3B model) is far heavier on CPU than Whisper <code>base</code>. The stat tiles above use the primary engine (<code>${escapeHtml(transcriptionData.primary_engine || "whisper")}</code>); the per-recording table below breaks out every engine.</p>`;
  }

  // The three tiers explained inline — the reader shouldn't have to dig for
  // what "light"/"heavy" mean.
  html += `
    <p class="eval-legend">Each recording is transcribed under three audio conditions to stress-test robustness:
    <strong>Clean</strong> = original audio (best case) ·
    <strong>Light noise</strong> = mild background hiss ·
    <strong>Heavy noise</strong> = loud noise + muffled-mic filter (worst case).
    <strong>WER</strong> (word error rate) = % of words transcribed wrong; lower is better.
    <strong>Time</strong> = seconds Whisper took on the clean audio (this machine, CPU).</p>
    <p class="eval-legend eval-legend-note">Only the <strong>Clean</strong> transcript is real input to the rest of the system — each recording is transcribed once, from its original audio. Light/Heavy noise are synthesized here purely to stress-test robustness and then discarded; nothing downstream ever picks "the best of the three."</p>
  `;

  html += `<h4 class="eval-subsection-header">Per-recording detail — all ${scenarios.length} meetings</h4>`;
  // Each engine is its own row so the same tier's WER for Whisper vs Voxtral
  // lines up in one column (easy top-to-bottom comparison). With one engine
  // the "Engine" column is dropped and it's the original flat table.
  const fmtSecs = (t) => (t != null ? `${t.toFixed(1)}s` : "—");
  const engineCol = multiEngine ? "<th>Engine</th>" : "";
  html += `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead><tr><th>Recording</th><th>Length</th>${engineCol}<th>Time to transcribe</th><th>Clean WER</th><th>Light noise WER</th><th>Heavy noise WER</th></tr></thead>
        <tbody>
  `;
  for (const s of scenarios) {
    const len = s.audio_seconds != null ? `${s.audio_seconds.toFixed(0)}s` : "—";
    const tierCells = (t) =>
      `<td>${fmtSecs(t?.clean?.seconds)}</td><td>${werCell(t?.clean)}</td><td>${werCell(t?.light_noise)}</td><td>${werCell(t?.heavy_noise)}</td>`;
    if (multiEngine) {
      // First engine row carries the recording name + length spanning all
      // engine rows; a top border marks the start of each recording group.
      benchedEngines.forEach((eng, i) => {
        const lead = i === 0
          ? `<td rowspan="${benchedEngines.length}">${escapeHtml(s.id)}</td><td rowspan="${benchedEngines.length}">${len}</td>`
          : "";
        html += `<tr class="${i === 0 ? "eval-group-start" : ""}">${lead}<td>${escapeHtml(ENGINE_LABELS[eng] || eng)}</td>${tierCells(s.engines?.[eng])}</tr>`;
      });
    } else {
      html += `<tr><td>${escapeHtml(s.id)}</td><td>${len}</td>${tierCells(s.tiers)}</tr>`;
    }
  }
  html += `</tbody></table></div>`;

  // Full methodology + honesty caveats, available but collapsed so they
  // don't bury the numbers above.
  let caveats = `<p class="eval-note"><strong>Goal:</strong> convert raw spoken audio into a clean transcript, fast. <strong>Built by:</strong> one shared Whisper (<code>${escapeHtml(transcriptionData.whisper_model || "base")}</code>) step (<code>transcription.py</code>) run on each of the 15 recordings in <code>audio-generation/output/</code>. Nothing here is phase-specific — the phases are separate capabilities layered on top of these transcripts.</p>`;
  for (const key of ["wer_benchmark_note", "noise_tiers_note", "timing_note", "diarization_note"]) {
    if (transcriptionData[key]) caveats += `<p class="eval-note">${escapeHtml(transcriptionData[key])}</p>`;
  }
  caveats += `<p class="eval-note">Avg transcription time: ${avgSecs ? avgSecs.toFixed(1) : "—"}s per recording (real-time factor ${avgRtf ? avgRtf.toFixed(3) : "—"}). Speaker diarization: ${gapPill("not implemented — Whisper returns one undifferentiated text stream")}</p>`;
  html += roadmapDetails("Methodology, benchmarks & caveats", caveats);

  html += `</div>`;
  return html;
}

const PHASE1_PROVIDERS = [
  { id: "local", label: "Local (Qwen2.5-1.5B)" },
  { id: "mistral", label: "Mistral 7B" },
  { id: "claude", label: "Claude (Haiku)" },
];

function fmtCost(usd) {
  if (usd == null) return "—";
  if (usd === 0) return "free";
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}

function fmtSeconds(s) {
  if (s == null) return "—";
  return s < 10 ? `${s.toFixed(1)}s` : `${s.toFixed(0)}s`;
}

const schemaOkOf = (r) => !!(r.layer1?.schema?.all_sections_present && r.layer1?.schema?.heading_level_matches_spec);
const actionsOkOf = (r) => r.layer1?.actions?.compliant !== false;
const phase1Label = (id) => (PHASE1_PROVIDERS.find((p) => p.id === id) || { label: id }).label;

// meeting is null on the old kickoff runs (main.py never set it) — treat those
// as the kickoff so every run maps to one of the 15 recordings.
const recKeyOf = (r) => r.meeting || "01-kickoff";

// recording -> provider -> latest run for that (recording, provider) pair.
function phase1LatestGrid(records) {
  const grid = {};
  for (const r of records || []) {
    const rk = recKeyOf(r);
    const p = r.summarizer_provider;
    (grid[rk] = grid[rk] || {});
    if (!grid[rk][p] || (r.timestamp || 0) > (grid[rk][p].timestamp || 0)) grid[rk][p] = r;
  }
  return grid;
}

function renderPhase1(historyRecords) {
  let html = `
    <h3 class="eval-section-header">Phase 1 — Basic Summary: which model summarizes best?</h3>
    <p class="eval-note"><strong>Goal:</strong> a faithful paragraph + bullet summary, no extra grounding (<code>phase1-baseline/</code>, zero-shot). The <em>same</em> transcript is summarized by all three providers and scored by one judge, so the three are directly comparable per recording.</p>
  `;

  const grid = phase1LatestGrid(historyRecords);
  const recordings = Object.keys(grid).sort();
  if (!recordings.length) {
    html += `<p class="eval-note">No runs yet.</p>`;
    return html;
  }

  const judgeOfRec = (rk) => {
    const any = PHASE1_PROVIDERS.map((p) => grid[rk][p.id]).find(Boolean);
    return any ? any.judge_provider : null;
  };

  // Aggregate only over recordings sharing one judge, so averages stay on a
  // single scale. Mistral judged the 14 batch recordings; the kickoff is
  // Claude-judged and is shown in the detail table but kept out of the average.
  const judgeCounts = {};
  for (const rk of recordings) { const j = judgeOfRec(rk); judgeCounts[j] = (judgeCounts[j] || 0) + 1; }
  const aggJudge = Object.entries(judgeCounts).sort((a, b) => b[1] - a[1])[0][0];
  const aggRecs = recordings.filter((rk) => judgeOfRec(rk) === aggJudge);

  const providerAgg = (pid) => {
    const runs = aggRecs.map((rk) => grid[rk][pid]).filter(Boolean);
    if (!runs.length) return null;
    return {
      n: runs.length,
      faithfulness: avg(runs.map((r) => r.layer2?.faithfulness)),
      completeness: avg(runs.map((r) => r.layer2?.completeness)),
      conciseness: avg(runs.map((r) => r.layer2?.conciseness)),
      unsupported: runs.reduce((a, r) => a + (r.layer2?.unsupported_claims || []).length, 0),
      schemaPass: runs.filter(schemaOkOf).length,
      actionsPass: runs.filter(actionsOkOf).length,
      genCost: avg(runs.map((r) => r.summarizer_cost_usd)),
      genTime: avg(runs.map((r) => r.gen_seconds)),
    };
  };

  // Data-derived verdict over the aggregate set (n = aggRecs.length).
  const joinList = (arr) => arr.length <= 1 ? (arr[0] || "")
    : arr.length === 2 ? `${arr[0]} and ${arr[1]}`
    : `${arr.slice(0, -1).join(", ")}, and ${arr[arr.length - 1]}`;
  const aggs = PHASE1_PROVIDERS.map((p) => ({ p, a: providerAgg(p.id) })).filter((x) => x.a);
  if (aggs.length) {
    const maxF = Math.max(...aggs.map((x) => x.a.faithfulness));
    const top = aggs.filter((x) => Math.abs(x.a.faithfulness - maxF) < 0.05);
    const allTie = top.length === aggs.length;
    let v;
    if (allTie) {
      // The LLM judge isn't discriminating (everyone ~tied). Point at the
      // deterministic schema check, which does separate them.
      const bySchema = aggs.slice().sort((a, b) => (b.a.schemaPass / b.a.n) - (a.a.schemaPass / a.a.n));
      const worstSchema = bySchema[bySchema.length - 1];
      v = `Across ${aggRecs.length} recordings the ${escapeHtml(aggJudge)} judge scores every model ~${fmtScore(maxF)} on faithfulness — it doesn't separate them. The deterministic <strong>schema check</strong> does: <strong>${escapeHtml(worstSchema.p.label)}</strong> follows the required format only ${worstSchema.a.schemaPass}/${worstSchema.a.n} times, versus ${bySchema[0].a.schemaPass}/${bySchema[0].a.n} for <strong>${escapeHtml(bySchema[0].p.label)}</strong> — so format compliance, not the judge score, is what actually distinguishes them here.`;
    } else {
      const freeTop = top.find((x) => (x.a.genCost || 0) === 0);
      const paidTop = top.find((x) => (x.a.genCost || 0) > 0);
      v = `Averaged over ${aggRecs.length} recordings (judge: ${escapeHtml(aggJudge)}), <strong>${joinList(top.map((x) => escapeHtml(x.p.label)))}</strong> lead${top.length > 1 ? "" : "s"} on faithfulness (${fmtScore(maxF)})`;
      if (freeTop && paidTop) v += ` — and <strong>${escapeHtml(freeTop.p.label)}</strong> reaches it <strong>free on-device</strong>, matching the paid model.`;
      else v += `.`;
      const worst = aggs.slice().sort((a, b) => a.a.faithfulness - b.a.faithfulness)[0];
      if (worst.a.faithfulness < maxF - 0.05) v += ` <strong>${escapeHtml(worst.p.label)}</strong> trails at ${fmtScore(worst.a.faithfulness)}.`;
    }
    html += roadmapVerdict(v);
  }

  // ---- Aggregate table (per provider) ----
  html += `<h4 class="eval-subsection-header">Average across ${aggRecs.length} recordings — judged by ${escapeHtml(aggJudge)}</h4>`;
  html += `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead><tr><th>Summarizer</th><th>Faithfulness</th><th>Completeness</th><th>Conciseness</th><th>Unsupported</th><th>Schema pass</th><th>Actions pass</th><th>Avg gen time</th><th>Avg gen cost</th></tr></thead>
        <tbody>
  `;
  for (const p of PHASE1_PROVIDERS) {
    const a = providerAgg(p.id);
    if (!a) { html += `<tr><td>${escapeHtml(p.label)}</td><td colspan="8" class="eval-muted">not run yet${p.id === "mistral" ? " (Mistral on CPU is slow — may still be running)" : ""}</td></tr>`; continue; }
    html += `
      <tr>
        <td>${escapeHtml(p.label)}</td>
        <td>${scoreCell(Number(a.faithfulness.toFixed(1)))}</td>
        <td>${scoreCell(Number(a.completeness.toFixed(1)))}</td>
        <td>${scoreCell(Number(a.conciseness.toFixed(1)))}</td>
        <td>${a.unsupported}</td>
        <td>${a.schemaPass}/${a.n}</td>
        <td>${a.actionsPass}/${a.n}</td>
        <td>${fmtSeconds(a.genTime)}</td>
        <td>${fmtCost(a.genCost)}</td>
      </tr>
    `;
  }
  html += `</tbody></table></div>`;

  // ---- Per-recording detail (Foundation-style) ----
  html += `<h4 class="eval-subsection-header">Per-recording detail — ${recordings.length} recordings × 3 models</h4>`;
  html += `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead><tr>
          <th>Recording</th><th>Summarizer</th><th>Faithful</th><th>Complete</th><th>Concise</th>
          <th>Unsupp.</th><th>Schema</th><th>Actions</th><th>Gen time</th><th>Summary $</th><th>Judge $</th><th>Total $</th>
        </tr></thead>
        <tbody>
  `;
  for (const rk of recordings) {
    const judge = judgeOfRec(rk);
    PHASE1_PROVIDERS.forEach((p, idx) => {
      const r = grid[rk][p.id];
      const recCell = idx === 0
        ? `<td rowspan="3">${escapeHtml(rk)}<br><span class="eval-muted" style="font-size:11px;">judge: ${escapeHtml(judge)}</span></td>`
        : "";
      if (!r) {
        html += `<tr>${recCell}<td>${escapeHtml(p.label)}</td><td colspan="10" class="eval-muted">—</td></tr>`;
        return;
      }
      const l2 = r.layer2 || {};
      html += `
        <tr>
          ${recCell}
          <td>${escapeHtml(p.label)}</td>
          <td>${l2.faithfulness != null ? scoreCell(l2.faithfulness) : "—"}</td>
          <td>${l2.completeness != null ? scoreCell(l2.completeness) : "—"}</td>
          <td>${l2.conciseness != null ? scoreCell(l2.conciseness) : "—"}</td>
          <td>${(l2.unsupported_claims || []).length}</td>
          <td>${statusPill(schemaOkOf(r), "OK", "Drift")}</td>
          <td>${statusPill(actionsOkOf(r), "OK", "Viol.")}</td>
          <td>${fmtSeconds(r.gen_seconds)}</td>
          <td>${fmtCost(r.summarizer_cost_usd)}</td>
          <td>${fmtCost(r.judge_cost_usd)}</td>
          <td>${fmtCost(r.total_cost_usd)}</td>
        </tr>
      `;
    });
  }
  html += `</tbody></table></div>`;

  html += `
    <p class="eval-legend"><strong>Faithful</strong> = no invented facts · <strong>Complete</strong> = key points captured (judge proxy, not literal recall) · <strong>Concise</strong> = no padding · <strong>Schema/Actions</strong> = deterministic format checks · <strong>Gen time</strong> = wall-clock to produce the summary (selection criterion — on-device compute; Claude not measured as its time is API latency) · <strong>Summary $</strong> = generation cost (on-device = free) · <strong>Judge $</strong> = scoring cost · <strong>Total $</strong> = both.</p>
  `;

  let caveats = `<p class="eval-note">Judge varies by recording (shown per row): the kickoff keeps its earlier <strong>Claude</strong>-judged run; recordings 2–15 are judged by <strong>Mistral</strong> (free, on-device) to save cost. Because the judge differs, the kickoff is excluded from the average table above (Mistral-judged recordings only) — cross-judge scores aren't on the same scale.</p>`;
  caveats += `<p class="eval-note">LLM-judge scores are non-deterministic; completeness is a proxy, not a ground-truth recall fraction. Generation cost for on-device models (local, Mistral) is $0; only Claude generation and Claude/Mistral judging incur (or, for Mistral, don't) real cost — Mistral judging is local, hence free.</p>`;
  html += roadmapDetails("Judge, cost & caveats", caveats);
  return html;
}

function renderPhase2(historyRecords) {
  let html = `
    <h3 class="eval-section-header">Phase 2 — Summary + Checklist + Action list: which model captures tasks best?</h3>
    <p class="eval-note"><strong>Goal:</strong> beyond a summary, produce a <strong>checklist coverage</strong> (which required topics were discussed) and an <strong>action list</strong> (who committed to what). Both are scored against a known ground truth — deterministic, no judge opinion. Action-list capture/correctness runs across <strong>all 15 meetings</strong>; the checklist stays kickoff-only (its required-topics list is the kickoff's own agenda, not a sprint-status or UAT agenda). Qwen vs Mistral.</p>
  `;

  // Qwen + Mistral only for now (per scope); Claude not part of this comparison.
  const PHASE2_PROVIDERS = PHASE1_PROVIDERS.filter((p) => p.id !== "claude");
  const labelOf = (id) => (PHASE1_PROVIDERS.find((p) => p.id === id) || { label: id }).label;
  const records = (historyRecords || []).filter((r) => r.summarizer_provider !== "claude");

  // Kickoff full scorecard: latest record per provider carrying the checklist
  // (only the kickoff run has one — the checklist is kickoff-specific).
  const kickoffByProv = {};
  for (const r of records) {
    if (!r.checklist) continue;
    const p = r.summarizer_provider;
    if (!kickoffByProv[p] || (r.timestamp || 0) > (kickoffByProv[p].timestamp || 0)) kickoffByProv[p] = r;
  }

  // All-15 action metrics: latest record per (provider, meeting) carrying an
  // action_extraction block and a meeting slug.
  const perMeeting = {};
  for (const r of records) {
    if (!r.meeting || !r.action_extraction) continue;
    const k = `${r.summarizer_provider}::${r.meeting}`;
    if (!perMeeting[k] || (r.timestamp || 0) > (perMeeting[k].timestamp || 0)) perMeeting[k] = r;
  }
  const slugs = [...new Set(Object.values(perMeeting).map((r) => r.meeting))].sort();
  // Pool over LABELED meetings only (gt >= 1). A meeting where the strict
  // "I'll" heuristic finds zero commitments has no ground truth, so its
  // generated bullets can't be judged real-vs-invented — including them would
  // understate precision. Gen time is still summed across every meeting run.
  const pooled = {}; // provider -> pooled action counts across its labeled meetings
  for (const r of Object.values(perMeeting)) {
    const p = r.summarizer_provider, ax = r.action_extraction;
    const agg = pooled[p] || (pooled[p] = { meetings: 0, labeled: 0, gt: 0, matchedGt: 0, gen: 0, extra: 0, genTimes: [] });
    agg.meetings += 1;
    if (r.gen_seconds != null) agg.genTimes.push(r.gen_seconds);
    if (!(ax.ground_truth_count > 0)) continue;
    agg.labeled += 1;
    agg.gt += ax.ground_truth_count || 0;
    agg.matchedGt += (ax.ground_truth_count || 0) - (ax.missed || 0);
    agg.gen += ax.generated_count || 0;
    agg.extra += ax.extra || 0;
  }
  const poolRecall = (a) => (a.gt ? a.matchedGt / a.gt : null);
  const poolPrecision = (a) => (a.gen ? (a.gen - a.extra) / a.gen : null);

  if (!Object.keys(kickoffByProv).length && !slugs.length) {
    html += `<p class="eval-note">No runs yet.</p>`;
    return html;
  }

  // Verdict — lead with action-list correctness pooled across all meetings.
  const withPool = PHASE2_PROVIDERS.filter((p) => pooled[p.id] && poolPrecision(pooled[p.id]) != null);
  if (withPool.length) {
    const totalGt = pooled[withPool[0].id].gt;
    const nLabeled = pooled[withPool[0].id].labeled;
    const nMeetings = pooled[withPool[0].id].meetings;
    // Rank by capture (recall) first — the dominant gap across the timeline —
    // then report precision for each. Data-driven, so it stays correct if a
    // re-run shifts the numbers.
    const byRecall = withPool.slice().sort((a, b) => poolRecall(pooled[b.id]) - poolRecall(pooled[a.id]));
    const best = byRecall[0], worst = byRecall[byRecall.length - 1];
    const ba = pooled[best.id], wa = pooled[worst.id];
    let v = `Across the ${nMeetings}-meeting timeline the strict "I'll / I will" heuristic marks only <strong>${totalGt}</strong> ground-truth commitments, spread over ${nLabeled} meetings (the other ${nMeetings - nLabeled} had none) — a deliberately sparse, high-confidence label set. `;
    if (worst.id !== best.id) {
      const betterOnBoth = poolPrecision(ba) >= poolPrecision(wa);
      v += `Pooled over the labeled meetings, <strong>${escapeHtml(labelOf(best.id))}</strong> captures far more of the real commitments (${fmtPct(poolRecall(ba))}, ${ba.matchedGt}/${ba.gt}) than <strong>${escapeHtml(labelOf(worst.id))}</strong> (${fmtPct(poolRecall(wa))}, ${wa.matchedGt}/${wa.gt})`;
      v += betterOnBoth
        ? `, and is also more precise (${fmtPct(poolPrecision(ba))} vs ${fmtPct(poolPrecision(wa))} real-vs-invented) — so it wins on both axes.`
        : `, though it lists more invented tasks (${fmtPct(poolPrecision(ba))} precision vs ${fmtPct(poolPrecision(wa))}).`;
      v += ` This <em>overturns</em> the kickoff-only read, where the single meeting made ${escapeHtml(labelOf(worst.id))} look competitive — extending the action metric across all ${nMeetings} meetings is what surfaced the real gap. Action-list capture is the discriminator; the checklist (kickoff-only) is saturated at 100%.`;
    } else {
      v += `Pooled capture is ${fmtPct(poolRecall(ba))} (${ba.matchedGt}/${ba.gt}) at ${fmtPct(poolPrecision(ba))} precision.`;
    }
    html += roadmapVerdict(v);
  }

  // --- Table 1: action list pooled across all 15 meetings ---
  html += `<h4 class="eval-subsection-header">Action list — pooled across all 15 meetings</h4>`;
  html += `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead><tr>
          <th>Summarizer</th>
          <th>Meetings (labeled/total)</th><th>Commitments (n)</th>
          <th>Action capture</th><th>Action correctness</th>
          <th>Avg gen time</th><th>Cost</th>
        </tr></thead>
        <tbody>
  `;
  for (const p of PHASE2_PROVIDERS) {
    const a = pooled[p.id];
    if (!a) { html += `<tr><td>${escapeHtml(p.label)}</td><td colspan="6" class="eval-muted">not run yet</td></tr>`; continue; }
    const rec = poolRecall(a), prec = poolPrecision(a);
    const cap = rec != null ? `${fmtPct(rec)} <span class="eval-muted" style="font-size:11px;">(${a.matchedGt}/${a.gt})</span>` : "—";
    const corr = prec != null ? `${fmtPct(prec)} <span class="eval-muted" style="font-size:11px;">(${a.gen - a.extra}/${a.gen})</span>` : "—";
    const avgGen = a.genTimes.length ? a.genTimes.reduce((x, y) => x + y, 0) / a.genTimes.length : null;
    html += `
      <tr>
        <td>${escapeHtml(p.label)}</td>
        <td>${a.labeled}/${a.meetings}</td>
        <td>${a.gt}</td>
        <td>${cap}</td>
        <td>${corr}</td>
        <td>${fmtSeconds(avgGen)}</td>
        <td>free</td>
      </tr>
    `;
  }
  html += `</tbody></table></div>`;

  // --- Table 2: kickoff full scorecard (summary quality + checklist) ---
  html += `<h4 class="eval-subsection-header">Kickoff — summary quality &amp; checklist coverage</h4>`;
  html += `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead><tr>
          <th>Summarizer</th>
          <th>Faithful</th><th>Complete</th><th>Concise</th>
          <th>Checklist acc</th>
          <th>Action capture</th><th>Action correctness</th>
          <th>Gen time</th><th>Cost</th>
        </tr></thead>
        <tbody>
  `;
  for (const p of PHASE2_PROVIDERS) {
    const r = kickoffByProv[p.id];
    if (!r) { html += `<tr><td>${escapeHtml(p.label)}</td><td colspan="8" class="eval-muted">not run yet</td></tr>`; continue; }
    const l2 = r.layer2 || {};
    const cl = r.checklist || {};
    const ax = r.action_extraction || {};
    const corr = ax.precision != null ? `${fmtPct(ax.precision)} <span class="eval-muted" style="font-size:11px;">(${ax.generated_count - (ax.extra || 0)}/${ax.generated_count})</span>` : "—";
    const cap = ax.recall != null ? `${fmtPct(ax.recall)} <span class="eval-muted" style="font-size:11px;">(${ax.ground_truth_count - (ax.missed || 0)}/${ax.ground_truth_count})</span>` : "—";
    html += `
      <tr>
        <td>${escapeHtml(p.label)}</td>
        <td>${l2.faithfulness != null ? scoreCell(l2.faithfulness) : "—"}</td>
        <td>${l2.completeness != null ? scoreCell(l2.completeness) : "—"}</td>
        <td>${l2.conciseness != null ? scoreCell(l2.conciseness) : "—"}</td>
        <td>${cl.accuracy != null ? fmtPct(cl.accuracy) : "—"}</td>
        <td>${cap}</td>
        <td>${corr}</td>
        <td>${fmtSeconds(r.gen_seconds)}</td>
        <td>${fmtCost(r.summarizer_cost_usd)}</td>
      </tr>
    `;
  }
  html += `</tbody></table></div>`;

  html += `
    <p class="eval-legend"><strong>Faithful / Complete / Concise</strong> = summary quality (judged) · <strong>Checklist acc</strong> = of the required topics, how many were correctly marked discussed-or-not (deterministic, kickoff only) · <strong>Action capture</strong> = of the real commitments, how many were caught (recall) · <strong>Action correctness</strong> = of the listed actions, how many are real vs invented (precision) · <strong>Gen time / Cost</strong> = on-device compute (free).</p>
  `;

  // --- Details: per-meeting action breakdown + scoring notes ---
  let details = "";
  if (slugs.length) {
    details += `<div class="eval-table-wrap"><table class="eval-table"><thead><tr><th>Meeting</th><th>Commitments</th>`;
    for (const p of PHASE2_PROVIDERS) details += `<th>${escapeHtml(p.label)} capture</th><th>correctness</th>`;
    details += `</tr></thead><tbody>`;
    for (const slug of slugs) {
      details += `<tr><td>${escapeHtml(slug)}</td>`;
      const anyRec = perMeeting[`${PHASE2_PROVIDERS[0].id}::${slug}`] || Object.values(perMeeting).find((r) => r.meeting === slug);
      details += `<td>${anyRec ? anyRec.action_extraction.ground_truth_count : "—"}</td>`;
      for (const p of PHASE2_PROVIDERS) {
        const r = perMeeting[`${p.id}::${slug}`];
        const ax = r && r.action_extraction;
        // No labels on a meeting with zero heuristic commitments -> "—" for both.
        const labeled = ax && ax.ground_truth_count > 0;
        details += `<td>${labeled ? fmtPct(ax.recall) : "—"}</td><td>${labeled ? fmtPct(ax.precision) : "—"}</td>`;
      }
      details += `</tr>`;
    }
    details += `</tbody></table></div>`;
  }
  details += `<p class="eval-note">Action metrics are <strong>deterministic</strong> — scored against ground-truth commitments auto-derived per meeting via the same "I'll / I will" heuristic every summarizer's system prompt is told to use for Actions bullets (see <code>eval/extraction_efficiency.py</code>), not an LLM opinion. Transcripts are reused from the Foundation/Phase-6 Whisper runs; only summarization re-runs per meeting.</p>`;
  details += `<p class="eval-note">The heuristic is intentionally strict, so most meetings contribute only 0–2 commitments — per-meeting recall is thin, which is why the headline numbers <strong>pool</strong> across all 15 (n above). Meetings with no "I'll" commitment show "—" for capture. Checklist coverage stays kickoff-only and is saturated at 100% there — kept for completeness, not a discriminator. Kickoff summary quality is judge-scored (judge: Mistral, free — lenient, hence the identical 5/4/4).</p>`;
  html += roadmapDetails("Per-meeting breakdown, how these are scored & caveats", details);
  return html;
}

function renderPhase3(results) {
  let html = `
    <h3 class="eval-section-header">Phase 3 — Context-Aware Summarization</h3>
    <p class="eval-note"><strong>Goal:</strong> does giving the summarizer meeting background sharpen the summary? <strong>Built by:</strong> <code>phase3-context/</code> — <code>summarize_baseline</code> (zero-shot) vs <code>summarize_with_context</code> (project background injected into the prompt), same transcript, same run.</p>
  `;
  const rows = [
    { label: "Baseline (no context)", variant: findVariant(results, "phase3-context", "baseline") },
    { label: "With context", variant: findVariant(results, "phase3-context", "with_context") },
  ];
  if (results) {
    html += `
      <div class="eval-table-wrap">
        <table class="eval-table">
          <thead><tr><th>Variant</th><th>Faithfulness</th><th>Completeness (proxy)</th><th>Conciseness</th><th>Unsupported claims</th></tr></thead>
          <tbody>
            ${rows.map((row) => {
              const v = row.variant;
              return `<tr><td>${escapeHtml(row.label)}</td><td>${v ? scoreCell(v.layer2.faithfulness) : "—"}</td><td>${v ? scoreCell(v.layer2.completeness) : "—"}</td><td>${v ? scoreCell(v.layer2.conciseness) : "—"}</td><td>${v ? (v.layer2.unsupported_claims || []).length : "—"}</td></tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
      <p class="eval-note">Judge model: ${escapeHtml(results.model)}.</p>
    `;
  } else {
    html += `<p class="eval-note">Could not load judge results. Run <code>python eval/judge.py</code>.</p>`;
  }
  return html;
}

function renderPhase4(results, extraction) {
  let html = `
    <h3 class="eval-section-header">Phase 4 — AI Assistant as Third Actor</h3>
    <p class="eval-note"><strong>Goal:</strong> a third voice (an AI meeting assistant) joins the recording itself, taking notes live — does the summarizer correctly exclude the assistant's own remarks from the actual meeting content? <strong>Built by:</strong> <code>phase4-assistant/</code> — same checklist + context-aware summarizer as Phases 2-3, plus an instruction that only Person A/Person B's own statements count.</p>
  `;
  const variant = results ? results.scenarios.find((s) => s.id === "phase4-assistant")?.variants[0] : null;
  const cl = variant?.checklist;
  html += cl ? `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead><tr><th>Checklist Precision</th><th>Checklist Recall</th><th>Faithfulness</th><th>Completeness</th></tr></thead>
        <tbody><tr>
          <td>${fmtPct(cl.precision)}</td><td>${fmtPct(cl.recall)}</td>
          <td>${scoreCell(variant.layer2.faithfulness)}</td><td>${scoreCell(variant.layer2.completeness)}</td>
        </tr></tbody>
      </table>
    </div>
  ` : `<p class="eval-note">Could not load results. Run <code>python eval/judge.py</code>.</p>`;

  if (extraction) {
    const s = extraction.scenarios.find((sc) => sc.id === "phase4-assistant");
    const v = s?.variants[0];
    if (v) {
      html += `<p class="eval-note">Action-item extraction: recall ${fmtPct(v.recall)}, precision ${fmtPct(v.precision)} — the assistant's own note-taking/closing-summary lines are never a source of a Key Point, Decision, or Action; only Person A/B's own statements are.</p>`;
    }
  }
  return html;
}

function renderPhase5(historyRecords) {
  let html = `
    <h3 class="eval-section-header">Phase 5 — On-Device / Office Tool Processing</h3>
    <p class="eval-note"><strong>Goal:</strong> agentic Office-document processing, validated under low-network conditions. <strong>Built by:</strong> <code>phase5-office-agent/</code> — a Claude tool-use agent standing in for Microsoft Copilot Enterprise (no license available in this repo); see its README for exactly what that substitution does and doesn't validate.</p>
  `;

  const byVariant = {};
  for (const r of historyRecords || []) {
    (byVariant[r.variant] = byVariant[r.variant] || []).push(r);
  }
  const variants = ["baseline", "agent_good", "agent_degraded", "agent_offline"].filter((v) => byVariant[v]);

  if (variants.length) {
    const rows = variants.map((v) => {
      const records = byVariant[v];
      const faithfulness = avg(records.map((r) => r.layer2?.faithfulness));
      const completeness = avg(records.map((r) => r.layer2?.completeness));
      const conciseness = avg(records.map((r) => r.layer2?.conciseness));
      return `<tr><td>${v}</td><td>${fmtScore(faithfulness)}</td><td>${fmtScore(completeness)}</td><td>${fmtScore(conciseness)}</td></tr>`;
    }).join("");
    html += `
      <div class="eval-table-wrap">
        <table class="eval-table">
          <thead><tr><th>Variant</th><th>Faithfulness</th><th>Completeness</th><th>Conciseness</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p class="eval-note">Was the improvement significant? Compare "baseline" (single-shot) against "agent_good" above — see <code>phase5-office-agent/README.md</code> for the current read.</p>
    `;
  } else {
    html += `<p class="eval-note">No runs yet. Run <code>python phase5-office-agent/src/main.py</code> (needs <code>ANTHROPIC_API_KEY</code>).</p>`;
  }

  html += `<p class="eval-note">Claude-only: local/Mistral have no tool-calling support in this project's <code>llm_provider.py</code>, so the agent arm requires a cloud model — on-device stays comprehension-only. Network conditions above are simulated (no real network-shaping tool in this repo), not a real network test. See <a href="/ROADMAP.md">ROADMAP.md</a> for the full write-up.</p>`;
  return html;
}

function renderPhase6(storyResults, storyProbes) {
  let html = `
    <h3 class="eval-section-header">Phase 6 — RAG over Meeting History</h3>
    <p class="eval-note"><strong>Goal:</strong> meeting-history-aware summaries (RAG over past notes) across a full 15-meeting project lifecycle. <strong>Built by:</strong> <code>phase6-history/</code> — comparing a summarizer with no memory of prior meetings against one given a running history built from each prior meeting's own summary.</p>
  `;

  if (storyResults) {
    const baselineFaithfulness = avg(storyResults.meetings.map((m) => m.baseline.layer2.faithfulness));
    const contextFaithfulness = avg(storyResults.meetings.map((m) => m.with_context.layer2.faithfulness));
    const baselineCompleteness = avg(storyResults.meetings.map((m) => m.baseline.layer2.completeness));
    const contextCompleteness = avg(storyResults.meetings.map((m) => m.with_context.layer2.completeness));
    const baselineContinuity = avg(storyResults.meetings.map((m) => m.baseline.continuity?.continuity));
    const contextContinuity = avg(storyResults.meetings.map((m) => m.with_context.continuity?.continuity));

    html += `
      <div class="eval-table-wrap">
        <table class="eval-table">
          <thead><tr><th>Variant</th><th>Avg faithfulness</th><th>Avg completeness</th><th>Avg continuity (meetings 2-15)</th></tr></thead>
          <tbody>
            <tr><td>Baseline (no history)</td><td>${fmtScore(baselineFaithfulness)}</td><td>${fmtScore(baselineCompleteness)}</td><td>${fmtScore(baselineContinuity)}</td></tr>
            <tr><td>With context + history</td><td>${fmtScore(contextFaithfulness)}</td><td>${fmtScore(contextCompleteness)}</td><td>${fmtScore(contextContinuity)}</td></tr>
          </tbody>
        </table>
      </div>
      <p class="eval-note">Was the improvement significant? <strong>A modest edge to context</strong> on the holistic scores (faithfulness/completeness both a bit higher) — continuity is identical for both and doesn't distinguish them. Deterministic checks below tell a more decisive story.</p>
    `;
  } else {
    html += `<p class="eval-note">Could not load story scores. Run <code>python eval/story_judge.py</code>.</p>`;
  }

  if (storyProbes) {
    const noiseLeakCount = storyProbes.meetings.reduce(
      (acc, m) => acc + (m.noise?.baseline?.leaked ? 1 : 0) + (m.noise?.with_context?.leaked ? 1 : 0), 0,
    );
    let baselineStale = 0, contextStale = 0;
    for (const m of storyProbes.meetings) {
      const s = m.deterministic_checks?.stale_actions;
      if (s?.baseline?.stale) baselineStale++;
      if (s?.with_context?.stale) contextStale++;
    }

    html += `<h4 class="eval-subsection-header">Deterministic checks (more trustworthy than the holistic score for these cases)</h4>`;
    html += `<div class="eval-card">`;
    html += `<div class="row"><span class="label">Small-talk noise leakage (15 meetings, both variants):</span> ${statusPill(
      noiseLeakCount === 0, "0 leaks — small talk never entered the summary", `${noiseLeakCount} leak(s) found`
    )}</div>`;
    html += `<div class="row"><span class="label">Stale-action carryover (meetings 2-15):</span> ${statusPill(
      baselineStale === 0, "baseline: none found", `baseline: ${baselineStale} meeting(s) found`
    )} · ${statusPill(contextStale === 0, "context-aware: none found", `context-aware: ${contextStale} meeting(s) found`)}</div>`;
    html += `</div>`;
  } else {
    html += `<p class="eval-note">Could not load story probes. Run <code>python eval/story_probes.py</code>.</p>`;
  }

  html += `<p class="eval-note">Not yet built: meeting-type-specific templates and domain terminology handling beyond this project's own vocabulary. See <a href="/ROADMAP.md">ROADMAP.md</a> for the full write-up.</p>`;
  return html;
}

function renderPhase7(historyRecords) {
  let html = `
    <h3 class="eval-section-header">Phase 7 — Reference-Document RAG</h3>
    <p class="eval-note"><strong>Goal:</strong> improve summary accuracy by retrieving relevant excerpts from the project's own reference documents (PRD, design spec, payments vendor doc) and grounding the summary in them, in addition to the transcript. <strong>Built by:</strong> <code>phase7-reference-rag/</code> — same TF-IDF, no-vector-DB retrieval approach as Phase 8's voice query, applied to summarization instead of Q&A.</p>
  `;

  // Grouped by (variant, retrieval_method) rather than just variant — a
  // "with_references" row run with FAISS and one run with TF-IDF aren't the
  // same thing to average together, and the point of keeping both backends
  // is to compare them, not blend them.
  const groups = {};
  for (const r of historyRecords || []) {
    const method = r.variant === "with_references" ? (r.retrieval_method || "tfidf") : "—";
    const key = `${r.variant}|${method}`;
    (groups[key] = groups[key] || { variant: r.variant, method, records: [] }).records.push(r);
  }
  const order = ["baseline|—", "with_references|tfidf", "with_references|faiss"];
  const keys = order.filter((k) => groups[k]);

  if (keys.length) {
    const rows = keys.map((key) => {
      const { variant, method, records } = groups[key];
      const faithfulness = avg(records.map((r) => r.layer2?.faithfulness));
      const completeness = avg(records.map((r) => r.layer2?.completeness));
      const conciseness = avg(records.map((r) => r.layer2?.conciseness));
      const groundingScores = records.map((r) => r.reference_grounding?.score).filter((s) => s != null);
      const grounding = variant === "with_references"
        ? (groundingScores.length ? fmtPct(avg(groundingScores)) : "n/a")
        : "—";
      return `<tr><td>${variant}</td><td>${method}</td><td>${fmtScore(faithfulness)}</td><td>${fmtScore(completeness)}</td><td>${fmtScore(conciseness)}</td><td>${grounding}</td></tr>`;
    }).join("");
    html += `
      <div class="eval-table-wrap">
        <table class="eval-table">
          <thead><tr><th>Variant</th><th>Retrieval</th><th>Faithfulness</th><th>Completeness</th><th>Conciseness</th><th>Reference Grounding</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p class="eval-note">Reference Grounding: of the words present in the reference-grounded summary but not the baseline (i.e. what the reference material added), the % that also appear in the retrieved excerpts — a proxy for "did the addition come from the reference docs," not a semantic fact-check. Baseline has nothing to compare against, so it's shown as —. TF-IDF and FAISS (real sentence embeddings, see <code>../faiss_retrieval.py</code>) are kept as separate rows since they can retrieve different excerpts for the same transcript.</p>
    `;
  } else {
    html += `<p class="eval-note">Not run yet — trigger it from the Pipeline page with a judge provider set to populate this table.</p>`;
  }
  return html;
}

function renderPhase8(voiceQueryRecords) {
  let html = `
    <h3 class="eval-section-header">Phase 8 — Voice Interface for Querying the Content</h3>
    <p class="eval-note"><strong>Goal:</strong> ask a spoken question, get a text answer grounded in everything this project has produced. <strong>Built by:</strong> <code>phase8-voice-query/</code> — TF-IDF retrieval over stored transcripts/summaries (no vector DB, no new dependency), answered with the same provider-swappable backend every other phase uses.</p>
  `;

  const records = voiceQueryRecords || [];
  if (!records.length) {
    html += `<p class="eval-note">No queries logged yet — try it on the <strong>Voice Query</strong> page, or see <a href="/phase8-voice-query/README.md">phase8-voice-query/README.md</a> for the retrieval/grounding methodology.</p>`;
    return html;
  }

  const groundingScores = records.map((r) => r.grounding?.score).filter((s) => s != null);
  const avgGrounding = groundingScores.length ? groundingScores.reduce((a, b) => a + b, 0) / groundingScores.length : null;
  const latencies = records.map((r) => r.timing?.total_s).filter((s) => s != null);
  const avgLatency = latencies.length ? latencies.reduce((a, b) => a + b, 0) / latencies.length : null;

  html += statRow([
    statTile(records.length, "Queries"),
    statTile(avgGrounding != null ? `${Math.round(avgGrounding * 100)}%` : "—", "Avg grounding"),
    statTile(avgLatency != null ? `${avgLatency.toFixed(1)}s` : "—", "Avg latency"),
  ]);

  html += `
    <h4 class="eval-subsection-header">Query history</h4>
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Provider</th>
            <th>Retrieval</th>
            <th>Question</th>
            <th>Grounding</th>
            <th>Latency</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
  `;
  for (const r of records) {
    const grounding = r.grounding || {};
    const groundingPct = grounding.score != null ? `${Math.round(grounding.score * 100)}%` : "n/a";
    const groundingLabel = grounding.abstained ? `${groundingPct} (abstained)` : groundingPct;
    const when = r.timestamp ? new Date(r.timestamp * 1000).toLocaleString() : "—";
    const question = r.question && r.question.length > 70 ? `${r.question.slice(0, 67)}...` : (r.question || "");
    const timing = r.timing || {};
    const latency = timing.total_s != null ? `${timing.total_s.toFixed(2)}s` : "—";
    const cost = r.cost_usd ? `$${r.cost_usd.toFixed(4)}` : (r.cost_usd === 0 ? "free" : "—");
    html += `
      <tr>
        <td>${when}</td>
        <td>${escapeHtml(r.provider || "")}</td>
        <td>${escapeHtml(r.retrieval_method || "tfidf")}</td>
        <td>${escapeHtml(question)}</td>
        <td>${groundingLabel}</td>
        <td>${latency}</td>
        <td>${cost}</td>
      </tr>
    `;
  }
  html += `</tbody></table></div>`;
  html += `<p class="eval-note">End-to-end latency and Grounding Score are measured per query. Try it on the <strong>Voice Query</strong> page, or see <a href="/phase8-voice-query/README.md">phase8-voice-query/README.md</a> for the retrieval/grounding methodology.</p>`;
  return html;
}

const ROADMAP_TABS = [
  { id: "foundation", label: "Foundation" },
  { id: "phase1", label: "Phase 1" },
  { id: "phase2", label: "Phase 2" },
  { id: "phase3", label: "Phase 3" },
  { id: "phase4", label: "Phase 4" },
  { id: "phase5", label: "Phase 5" },
  { id: "phase6", label: "Phase 6" },
  { id: "phase7", label: "Phase 7" },
  { id: "phase8", label: "Phase 8" },
];

function wireRoadmapTabs(root) {
  const tabs = root.querySelectorAll(".roadmap-tab");
  const panels = root.querySelectorAll(".roadmap-tab-panel");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.setAttribute("aria-pressed", "false"));
      tab.setAttribute("aria-pressed", "true");
      panels.forEach((p) => p.classList.toggle("hidden", p.dataset.tabPanel !== tab.dataset.tab));
    });
  });
}

async function renderRoadmapPage() {
  const root = document.getElementById("roadmap-root");
  root.innerHTML = "<p>Loading…</p>";

  const [transcriptionData, results, extraction, storyResults, storyProbes, phase1History, phase2History, phase5History, phase7History, voiceQueryHistory] = await Promise.all([
    fetchJsonOrNull("/eval/output/transcription_quality.json"),
    fetchJsonOrNull("/eval/output/results.json"),
    fetchJsonOrNull("/eval/output/extraction_efficiency.json"),
    fetchJsonOrNull("/eval/output/story_results.json"),
    fetchJsonOrNull("/eval/output/story_probes.json"),
    fetchJsonOrNull("/api/eval/history?scenario=phase1-baseline"),
    fetchJsonOrNull("/api/eval/history?scenario=phase2-checklist"),
    fetchJsonOrNull("/api/eval/history?scenario=phase5-office-agent"),
    fetchJsonOrNull("/api/eval/history?scenario=phase7-reference-rag"),
    fetchJsonOrNull("/api/voice-query/history"),
  ]);

  const panelContent = {
    foundation: renderFoundation(transcriptionData),
    phase1: renderPhase1(phase1History?.records),
    phase2: renderPhase2(phase2History?.records),
    phase3: renderPhase3(results),
    phase4: renderPhase4(results, extraction),
    phase5: renderPhase5(phase5History?.records),
    phase6: renderPhase6(storyResults, storyProbes),
    phase7: renderPhase7(phase7History?.records),
    phase8: renderPhase8(voiceQueryHistory?.records),
  };

  let html = `<p class="custom-intro">Each tab below is scored from the same eval outputs shown on the Evaluation and Story pages, regrouped by roadmap phase instead of by scenario — see <a href="/ROADMAP.md">ROADMAP.md</a> for the narrative version.</p>`;
  html += `<div class="roadmap-tabs" role="tablist">`;
  html += ROADMAP_TABS.map((t, i) => `<button class="roadmap-tab" data-tab="${t.id}" aria-pressed="${i === 0}">${t.label}</button>`).join("");
  html += `</div>`;
  html += ROADMAP_TABS.map((t, i) => `<div class="roadmap-tab-panel${i === 0 ? "" : " hidden"}" data-tab-panel="${t.id}">${panelContent[t.id]}</div>`).join("");

  root.innerHTML = html;
  wireRoadmapTabs(root);
}

// ---------- Voice Query page (Phase 8) ----------
const VOICE_QUERY_STAGE_LABELS = {
  transcribing: "Transcribing",
  retrieving: "Retrieving",
  answering: "Answering",
  done: "Done",
};

const VOICE_QUERY_PROVIDER_HINTS = {
  claude: { text: "~15–30 s (transcribe ~10 s + retrieve <1 s + API answer ~5 s)", slow: false },
  local:  { text: "~3–5 min (transcribe ~10 s + model load ~2 min + generate ~1 min)", slow: true },
  mistral:{ text: "~5–10 min (transcribe ~10 s + model load ~3 min + generate ~2 min)", slow: true },
};

let voiceQueryMediaRecorder = null;
let voiceQueryChunks = [];
let voiceQueryPollTimer = null;

function renderVoiceQueryPage() {
  const root = document.getElementById("voicequery-root");
  root.innerHTML = `
    <p class="custom-intro">Ask a spoken question about anything the project has already summarized
      (Phases 1-7) and get a text answer grounded in the stored transcripts/summaries, with end-to-end
      latency and a deterministic Grounding Score. See
      <a href="/phase8-voice-query/README.md">phase8-voice-query/README.md</a>.</p>
    <div class="voicequery-controls">
      <select id="voicequery-provider" class="provider-select">
        <option value="local" class="option-slow">Local (Qwen2.5)</option>
        <option value="mistral" class="option-slow">Local (Mistral 7B)</option>
        <option value="claude">Claude (Haiku 4.5)</option>
      </select>
      <select id="voicequery-retrieval" class="provider-select">
        <option value="tfidf">Retrieval: TF-IDF</option>
        <option value="faiss">Retrieval: FAISS (embeddings)</option>
      </select>
      <button id="voicequery-record-btn" class="run-btn">Start recording</button>
      <span id="voicequery-rec-status" class="voicequery-status"></span>
    </div>
    <div id="voicequery-provider-hint" class="voicequery-provider-hint"></div>
    <div id="voicequery-progress" class="custom-processing-note"></div>
    <div id="voicequery-result"></div>
    <div class="block-label">Progress across providers</div>
    <div id="voicequery-history">Loading…</div>
  `;

  document.getElementById("voicequery-record-btn").addEventListener("click", () => {
    if (voiceQueryMediaRecorder && voiceQueryMediaRecorder.state === "recording") {
      voiceQueryMediaRecorder.stop();
    } else {
      startVoiceQueryRecording();
    }
  });

  const providerSelect = document.getElementById("voicequery-provider");
  providerSelect.addEventListener("change", updateVoiceQueryProviderHint);
  updateVoiceQueryProviderHint();

  renderVoiceQueryHistory();
}

function updateVoiceQueryProviderHint() {
  const el = document.getElementById("voicequery-provider-hint");
  if (!el) return;
  const provider = document.getElementById("voicequery-provider").value;
  const hint = VOICE_QUERY_PROVIDER_HINTS[provider];
  if (hint) {
    el.textContent = `Estimated processing time: ${hint.text}`;
    el.className = `voicequery-provider-hint${hint.slow ? " slow" : ""}`;
  } else {
    el.textContent = "";
    el.className = "voicequery-provider-hint";
  }
}

async function renderVoiceQueryHistory() {
  const root = document.getElementById("voicequery-history");
  if (!root) return;

  let records;
  try {
    const res = await fetch("/api/voice-query/history");
    records = (await res.json()).records || [];
  } catch {
    root.innerHTML = `<p class="tech-intro">Couldn't load run history.</p>`;
    return;
  }

  if (!records.length) {
    root.innerHTML = `<p class="tech-intro">No queries logged yet — ask a question above to start building a comparison across providers.</p>`;
    return;
  }

  let html = `
    <div class="eval-table-wrap">
      <table class="eval-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Provider</th>
            <th>Retrieval</th>
            <th>Question</th>
            <th>Grounding</th>
            <th>Time taken</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
  `;
  for (const r of records) {
    const grounding = r.grounding || {};
    const groundingPct = grounding.score != null ? `${Math.round(grounding.score * 100)}%` : "n/a";
    const groundingLabel = grounding.abstained ? `${groundingPct} (abstained)` : groundingPct;
    const when = r.timestamp ? new Date(r.timestamp * 1000).toLocaleString() : "—";
    const question = r.question && r.question.length > 70 ? `${r.question.slice(0, 67)}...` : (r.question || "");
    const timing = r.timing || {};
    const latency = timing.total_s != null ? `${timing.total_s.toFixed(2)}s` : "—";
    const breakdown = timing.total_s != null
      ? `transcribe ${(timing.transcribe_s || 0).toFixed(2)}s, retrieve ${(timing.retrieve_s || 0).toFixed(2)}s, answer ${(timing.answer_s || 0).toFixed(2)}s`
      : "";
    const cost = r.cost_usd ? `$${r.cost_usd.toFixed(4)}` : (r.cost_usd === 0 ? "free" : "—");
    html += `
      <tr>
        <td>${when}</td>
        <td>${escapeHtml(r.provider || "")}<br><span class="voicequery-status">${escapeHtml(r.model_name || "")}</span></td>
        <td>${escapeHtml(r.retrieval_method || "tfidf")}</td>
        <td>${escapeHtml(question)}</td>
        <td>${groundingLabel}</td>
        <td>${latency}<br><span class="voicequery-status">${breakdown}</span></td>
        <td>${cost}</td>
      </tr>
    `;
  }
  html += `</tbody></table></div>`;
  root.innerHTML = html;
}

async function startVoiceQueryRecording() {
  const btn = document.getElementById("voicequery-record-btn");
  const status = document.getElementById("voicequery-rec-status");
  document.getElementById("voicequery-result").innerHTML = "";
  document.getElementById("voicequery-progress").textContent = "";

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    status.textContent = `Microphone access denied or unavailable (${err.message}).`;
    return;
  }

  voiceQueryChunks = [];
  voiceQueryMediaRecorder = new MediaRecorder(stream);
  voiceQueryMediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) voiceQueryChunks.push(e.data);
  };
  voiceQueryMediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(voiceQueryChunks, { type: voiceQueryMediaRecorder.mimeType || "audio/webm" });
    submitVoiceQuery(blob);
  };
  voiceQueryMediaRecorder.start();
  btn.textContent = "Stop recording";
  status.textContent = "Recording… click again to stop.";
}

async function submitVoiceQuery(blob) {
  const btn = document.getElementById("voicequery-record-btn");
  const status = document.getElementById("voicequery-rec-status");
  const provider = document.getElementById("voicequery-provider").value;
  const retrieval = document.getElementById("voicequery-retrieval").value;
  btn.disabled = true;
  status.textContent = "Uploading…";

  let job;
  try {
    const res = await fetch(`/api/voice-query?provider=${encodeURIComponent(provider)}&retrieval=${encodeURIComponent(retrieval)}`, {
      method: "POST",
      headers: { "Content-Type": blob.type || "audio/webm" },
      body: blob,
    });
    if (!res.ok) throw new Error(`upload failed: ${res.status}`);
    job = (await res.json()).job;
  } catch (err) {
    status.textContent = `Upload failed (${err.message}).`;
    btn.disabled = false;
    btn.textContent = "Start recording";
    return;
  }

  status.textContent = "Processing…";
  pollVoiceQuery(job);
}

function pollVoiceQuery(job) {
  const btn = document.getElementById("voicequery-record-btn");
  const status = document.getElementById("voicequery-rec-status");
  const progress = document.getElementById("voicequery-progress");

  clearInterval(voiceQueryPollTimer);
  voiceQueryPollTimer = setInterval(async () => {
    let data;
    try {
      const res = await fetch(`/api/voice-query/status?job=${encodeURIComponent(job)}`);
      data = await res.json();
    } catch {
      return;
    }

    if (data.stage) {
      progress.textContent = `Stage: ${VOICE_QUERY_STAGE_LABELS[data.stage] || data.stage}`;
    }

    if (data.status === "done") {
      clearInterval(voiceQueryPollTimer);
      status.textContent = "";
      progress.textContent = "";
      btn.disabled = false;
      btn.textContent = "Start recording";
      renderVoiceQueryResult(data.result);
      renderVoiceQueryHistory();
    } else if (data.status === "error") {
      clearInterval(voiceQueryPollTimer);
      const err = data.error || "unknown";
      const isOOM = /killed|memoryerror|out of memory|signal 9/i.test(err);
      if (isOOM) {
        status.textContent = "";
        const resultEl = document.getElementById("voicequery-result");
        resultEl.innerHTML = `<div class="voicequery-oom-hint">Voice query ran out of memory on this server. This feature requires at least 2 GB RAM (currently 914 MB).</div>`;
      } else {
        status.textContent = `Error: ${err}`;
      }
      btn.disabled = false;
      btn.textContent = "Start recording";
    }
  }, 1500);
}

function renderVoiceQueryResult(result) {
  const root = document.getElementById("voicequery-result");
  if (!result) {
    root.innerHTML = `<p>No result returned — check <code>docker compose logs</code> / server output.</p>`;
    return;
  }
  const grounding = result.grounding || {};
  const groundingPct = grounding.score != null ? `${Math.round(grounding.score * 100)}%` : "n/a";
  const timing = result.timing || {};
  const sources = (result.retrieved || []).map((c) => {
    const snippet = c.text.length > 160 ? `${c.text.slice(0, 160)}…` : c.text;
    return `<li><strong>${escapeHtml(c.source)}</strong> (score ${c.score.toFixed(2)}) — ${escapeHtml(snippet)}</li>`;
  }).join("");

  root.innerHTML = `
    <div class="voicequery-qa">
      <div class="voicequery-question"><strong>You asked:</strong> ${escapeHtml(result.question)}</div>
      <div class="voicequery-answer"><strong>Answer:</strong> ${escapeHtml(result.answer)}</div>
    </div>
    <div class="voicequery-metrics">
      <div><strong>End-to-end latency:</strong> ${(timing.total_s || 0).toFixed(2)}s
        (transcribe ${(timing.transcribe_s || 0).toFixed(2)}s, retrieve ${(timing.retrieve_s || 0).toFixed(2)}s,
        answer ${(timing.answer_s || 0).toFixed(2)}s)</div>
      <div><strong>Grounding Score:</strong> ${groundingPct}${grounding.abstained ? " (model abstained — low score expected)" : ""}</div>
    </div>
    <div class="voicequery-sources">
      <h4>Retrieved sources</h4>
      <ul>${sources || "<li>(none matched)</li>"}</ul>
    </div>
  `;
}

function stopVoiceQueryPolling() {
  if (voiceQueryPollTimer) {
    clearInterval(voiceQueryPollTimer);
    voiceQueryPollTimer = null;
  }
}

// ---------- Concepts page ----------
function renderConceptsPage() {
  const root = document.getElementById("concepts-root");
  root.innerHTML = `
    <div class="concepts-overview">
      <h2>Voice to Summary</h2>
      <p>Meetings produce decisions, action items, and context that teams rely on — but writing those up is slow, inconsistent, and often skipped. This project turns a meeting recording into a structured written summary automatically: Topic, Key Points, Decisions, and Actions with owners — ready to share, file, or feed into project tracking.</p>
      <p>Everything runs on your own machine. No recording or transcript is sent to the cloud, no subscription is needed, and there are no per-meeting costs. The system is built in eight progressive phases, each adding one capability so you can see exactly what each layer contributes.</p>
    </div>

    <details class="concepts-section" open>
      <summary>Phases</summary>
      <div class="concepts-grid">
        <div class="concepts-phase"><strong>1. Baseline</strong> — Turn a recording into a structured summary: Topic, Key Points, Decisions, Actions</div>
        <div class="concepts-phase"><strong>2. Checklist</strong> — Verify that all required agenda topics were actually discussed</div>
        <div class="concepts-phase"><strong>3. Context</strong> — Feed project background into the summary for sharper, more relevant output</div>
        <div class="concepts-phase"><strong>4. Assistant</strong> — An AI note-taker joins the call; the summary correctly separates its remarks from the real discussion</div>
        <div class="concepts-phase"><strong>5. Office Agent</strong> — Auto-generate Word and Excel deliverables from the summary, even on spotty network</div>
        <div class="concepts-phase"><strong>6. History</strong> — Track a 15-meeting project lifecycle with running context carried across meetings</div>
        <div class="concepts-phase"><strong>7. Reference RAG</strong> — Pull in facts from project documents (PRD, design specs) to enrich the summary</div>
        <div class="concepts-phase"><strong>8. Voice Query</strong> — Ask a spoken question and get a text answer drawn from all past meetings</div>
      </div>
    </details>

    <details class="concepts-section">
      <summary>Core Concepts</summary>
      <div class="concepts-dl">
        <div class="concepts-term">Speech Recognition</div>
        <div class="concepts-def">Converts the audio recording into a text transcript using Whisper, running entirely on-device. No audio leaves the machine.</div>

        <div class="concepts-term">Summarization</div>
        <div class="concepts-def">A small language model reads the transcript and produces the structured summary. Runs locally by default; optionally swappable to a cloud model for comparison.</div>

        <div class="concepts-term">Checklist Coverage</div>
        <div class="concepts-def">Automatically checks whether each expected agenda topic was actually discussed, using keyword matching rather than AI guesswork.</div>

        <div class="concepts-term">Context Injection</div>
        <div class="concepts-def">Gives the summarizer background about the project (participants, goals, prior decisions) so the output reflects what matters, not just what was said.</div>

        <div class="concepts-term">RAG (Retrieval)</div>
        <div class="concepts-def">Pulls in relevant excerpts from past meetings or project documents before summarizing, so the output connects to the broader project story.</div>

        <div class="concepts-term">Privacy</div>
        <div class="concepts-def">All speaker names are replaced with Person A / Person B. No personally identifiable information appears in any output.</div>
      </div>
    </details>

    <details class="concepts-section">
      <summary>Technical Stack</summary>
      <div class="concepts-dl">
        <div class="concepts-term">Language</div>
        <div class="concepts-def">Python 3</div>

        <div class="concepts-term">Speech-to-text</div>
        <div class="concepts-def">OpenAI Whisper (local, <code>base</code> model) · Voxtral Mini 3B (optional)</div>

        <div class="concepts-term">Summarization LLM</div>
        <div class="concepts-def"><code>Qwen/Qwen2.5-1.5B-Instruct</code> (default, on-device) · Mistral 7B (local) · Claude Haiku 4.5 (API)</div>

        <div class="concepts-term">Audio</div>
        <div class="concepts-def"><code>pydub</code> + <code>ffmpeg</code> for processing · <code>pyttsx3</code> for TTS demo recordings</div>

        <div class="concepts-term">Web UI</div>
        <div class="concepts-def">Framework-free HTML/CSS/JS · Python stdlib <code>http.server</code> — zero frontend dependencies</div>

        <div class="concepts-term">Dependencies</div>
        <div class="concepts-def"><code>torch</code>, <code>accelerate</code>, <code>transformers</code>, <code>openai-whisper</code>, <code>pydub</code>, <code>pyttsx3</code></div>

        <div class="concepts-term">Infrastructure</div>
        <div class="concepts-def">Runs entirely offline after one-time model downloads (~3GB). No API keys required for the default local configuration.</div>
      </div>
    </details>

    <details class="concepts-section">
      <summary>Evaluation Methodology</summary>
      <div class="concepts-dl">
        <div class="concepts-term">Two-layer design</div>
        <div class="concepts-def">Layer 1 is deterministic (no AI opinion): schema compliance, heading format, action-bullet prefixes, transcription accuracy, extraction recall/precision. Layer 2 is AI-judged: faithfulness, completeness, conciseness on a 1-5 scale.</div>

        <div class="concepts-term">Transcription accuracy</div>
        <div class="concepts-def">Word Error Rate (WER) measured across clean, light-noise, and heavy-noise audio. Target: 5-8% for domain speech.</div>

        <div class="concepts-term">Action Extraction</div>
        <div class="concepts-def">How many real commitments the summary captured (recall) and how many listed actions are real vs invented (precision) — scored deterministically, not by AI opinion.</div>

        <div class="concepts-term">Grounding Score</div>
        <div class="concepts-def">For summaries enriched with reference documents, measures what fraction of the new content traces back to the source material.</div>

        <div class="concepts-term">Known limitation</div>
        <div class="concepts-def">The same small model that writes the summary also judges it in the default config — it tends to rate itself generously. Deterministic checks (Layer 1) are more trustworthy.</div>
      </div>
    </details>
  `;
}

// ---------- Demo Journey page ----------
function renderDemoPage() {
  const root = document.getElementById("demo-root");

  const DEMO_TABS = [
    { key: "record",    label: "Record" },
    { key: "summary",   label: "Summary" },
    { key: "checklist", label: "Checklist" },
    { key: "enriched",  label: "Enriched" },
    { key: "qa",        label: "Q&A" },
    { key: "done",      label: "Done" },
  ];

  const DEMO_CHECKLIST = [
    "Get payment provider access provisioned this week",
    "Engage legal early to avoid bottlenecks",
    "Loop analytics team and scope tracking events",
    "Bring localization decision to requirements review",
  ];

  const DEMO_QA = [
    { q: "What was decided about payments?",
      a: "No final vendor decision was made. A new payments provider will be integrated as part of the onboarding rebuild. Person A will push to get sandbox access provisioned this week." },
    { q: "Who owns the legal review?",
      a: "Person A is responsible. They committed to engaging legal early to avoid bottlenecks later in the project timeline." },
    { q: "What is the project timeline?",
      a: "Five-month launch target. Requirements review next week, then two-week sprint syncs. Dark mode is a stretch goal that may extend the timeline." },
  ];

  let demoCurrent = 0;
  let demoClState = DEMO_CHECKLIST.map(() => false);
  let demoQaAsked = 1;

  function waveformHtml() {
    return Array.from({ length: 24 }, () => {
      const h = 8 + Math.round(Math.random() * 24);
      const d = (Math.random() * 0.4).toFixed(2);
      return `<div class="demo-wave-bar" style="height:${h}px;animation-delay:${d}s"></div>`;
    }).join("");
  }

  function renderDemoTabs() {
    const strip = root.querySelector(".demo-tab-strip");
    strip.innerHTML = DEMO_TABS.map((t, i) =>
      `<button class="demo-tab-btn${i === demoCurrent ? " active" : ""}" data-idx="${i}"><div class="demo-tab-num">${i + 1} / ${DEMO_TABS.length}</div><div class="demo-tab-lbl">${escapeHtml(t.label)}</div></button>`
    ).join("");
    strip.querySelectorAll(".demo-tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => demoGoTo(Number(btn.dataset.idx)));
    });

    const dots = root.querySelector(".demo-dots");
    dots.innerHTML = DEMO_TABS.map((_, i) =>
      `<div class="demo-dot${i <= demoCurrent ? " filled" : ""}"></div>`
    ).join("");

    root.querySelector(".demo-step-num").textContent = demoCurrent + 1;
    root.querySelector(".demo-nav-back").disabled = demoCurrent === 0;
    root.querySelector(".demo-nav-next").disabled = demoCurrent === DEMO_TABS.length - 1;
  }

  function renderDemoChecklist() {
    const el = root.querySelector(".demo-cl-list");
    if (!el) return;
    el.innerHTML = DEMO_CHECKLIST.map((label, i) => {
      const checked = demoClState[i];
      const tick = checked ? `<svg width="11" height="11" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>` : "";
      return `<div class="demo-cl-row${checked ? " checked" : ""}" data-idx="${i}"><div class="demo-cl-box">${tick}</div><div class="demo-cl-row-text">${escapeHtml(label)}</div></div>`;
    }).join("");
    el.querySelectorAll(".demo-cl-row").forEach((row) => {
      row.addEventListener("click", () => {
        demoClState[Number(row.dataset.idx)] = !demoClState[Number(row.dataset.idx)];
        renderDemoChecklist();
      });
    });
  }

  function renderDemoQA() {
    const thread = root.querySelector(".demo-qa-thread-inner");
    if (!thread) return;
    thread.innerHTML = DEMO_QA.slice(0, demoQaAsked).map((qa) =>
      `<div class="demo-qa-pair"><div class="demo-q">${escapeHtml(qa.q)}</div><div class="demo-a">${escapeHtml(qa.a)}</div></div>`
    ).join("");
    const askBtn = root.querySelector(".demo-ask-btn");
    if (demoQaAsked < DEMO_QA.length) {
      askBtn.style.display = "";
      askBtn.textContent = `Ask: "${DEMO_QA[demoQaAsked].q}"`;
    } else {
      askBtn.style.display = "none";
    }
  }

  function demoGoTo(idx) {
    if (idx < 0 || idx >= DEMO_TABS.length) return;
    demoCurrent = idx;
    root.querySelectorAll(".demo-device").forEach((d, i) => {
      d.classList.toggle("active", i === idx);
    });
    renderDemoTabs();
    if (idx === 2) renderDemoChecklist();
    if (idx === 4) renderDemoQA();
    const active = root.querySelectorAll(".demo-device")[idx];
    if (active) active.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }

  function demoReset() {
    demoClState = DEMO_CHECKLIST.map(() => false);
    demoQaAsked = 1;
    demoGoTo(0);
  }

  function deviceWrap(idx, label, innerHtml) {
    return `
      <div class="demo-device${idx === 0 ? " active" : ""}" data-idx="${idx}">
        <div class="demo-device-label">${escapeHtml(label)}</div>
        <div class="demo-device-frame">
          <div class="demo-device-notch"></div>
          <div class="demo-device-screen">${innerHtml}</div>
          <div class="demo-device-home"></div>
        </div>
      </div>`;
  }

  const screen0 = `
    <div style="padding:40px 16px 0">
      <div class="demo-screen-eyebrow">Meeting recording</div>
      <div class="demo-screen-title">Project Kickoff</div>
      <div class="demo-screen-meta">Onboarding refresh &middot; sprint planning</div>
    </div>
    <div class="demo-rec-center">
      <div class="demo-mic-circle">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 15a3 3 0 003-3V6a3 3 0 10-6 0v6a3 3 0 003 3z" fill="var(--good)"/><path d="M19 11a7 7 0 01-14 0M12 18v3" stroke="var(--good)" stroke-width="1.6" stroke-linecap="round"/></svg>
      </div>
      <div class="demo-rec-status">
        <div class="demo-rec-dot"></div>
        <span class="demo-rec-label">Recording</span>
        <span class="demo-rec-timer">03:47</span>
      </div>
      <div class="demo-waveform">${waveformHtml()}</div>
    </div>
    <div class="demo-rec-controls">
      <div class="demo-ctrl-circle demo-ctrl-pause">
        <svg width="12" height="12" viewBox="0 0 24 24"><rect x="6" y="5" width="4" height="14" fill="var(--text-secondary)"/><rect x="14" y="5" width="4" height="14" fill="var(--text-secondary)"/></svg>
      </div>
      <div class="demo-ctrl-circle demo-ctrl-stop demo-goto" data-goto="1">
        <div style="width:12px;height:12px;border-radius:2px;background:#fff"></div>
      </div>
    </div>`;

  const screen1 = `
    <div class="demo-screen-hdr">
      <div class="demo-screen-eyebrow">Call summary</div>
      <div class="demo-screen-title">Project Kickoff</div>
      <div class="demo-screen-meta">4 min &middot; recorded today</div>
    </div>
    <div class="demo-screen-body">
      <div class="demo-bullet-list">
        <div class="demo-bullet-item"><div class="demo-bullet-dot"></div><div>High-level goal is to improve onboarding conversion and provide a visual refresh, targeting launch in five months.</div></div>
        <div class="demo-bullet-item"><div class="demo-bullet-dot"></div><div>Engineering scope includes rebuilding the onboarding flow, integrating a new payments provider, and dark mode as a stretch goal.</div></div>
        <div class="demo-bullet-item"><div class="demo-bullet-dot"></div><div>New payments vendor means no sandbox access until integration begins &mdash; access must be provisioned early.</div></div>
        <div class="demo-bullet-item"><div class="demo-bullet-dot"></div><div>Localization scope still open &mdash; decision deferred to requirements review next week.</div></div>
      </div>
    </div>
    <div class="demo-screen-footer">
      <button class="demo-btn-primary demo-goto" data-goto="2">Add checklist</button>
    </div>`;

  const screen2 = `
    <div class="demo-screen-hdr">
      <div class="demo-screen-eyebrow">Summary + checklist</div>
      <div class="demo-screen-title">Project Kickoff</div>
    </div>
    <div class="demo-screen-body" style="gap:0">
      <div class="demo-summary-card">Onboarding conversion improvement with visual refresh, targeting five-month launch. Rebuilding onboarding flow, integrating new payments provider, dark mode stretch goal. Legal review and analytics instrumentation running alongside.</div>
      <div class="demo-section-label">Action items</div>
      <div class="demo-cl-list"></div>
    </div>
    <div class="demo-screen-footer">
      <button class="demo-btn-primary demo-goto" data-goto="3">Enrich with context</button>
    </div>`;

  const screen3 = `
    <div class="demo-screen-hdr">
      <div class="demo-screen-eyebrow">Context-enriched summary</div>
      <div class="demo-screen-title">Project Kickoff</div>
      <span class="demo-context-tag">+ Project docs &amp; PRD</span>
    </div>
    <div class="demo-screen-body" style="gap:10px">
      <div class="demo-summary-card">Onboarding conversion improvement with visual refresh, targeting five-month launch. Rebuilding onboarding flow, integrating new payments provider, dark mode stretch goal.</div>
      <div class="demo-enrich">Person B should also attend the requirements review to discuss localization &mdash; this was missed in the baseline summary but confirmed in the transcript.</div>
      <div class="demo-enrich">"Stakeholder access" resolved to the specific payments provider sandbox &mdash; access must be provisioned before integration work can begin (day one dependency).</div>
      <div class="demo-enrich">Budget or cost impact was not discussed in this meeting &mdash; flagged as a gap for the next review session.</div>
    </div>
    <div class="demo-screen-footer">
      <button class="demo-btn-primary demo-goto" data-goto="4">Ask a question</button>
    </div>`;

  const screen4 = `
    <div class="demo-screen-hdr" style="padding-bottom:10px">
      <div class="demo-screen-eyebrow">Ask about this meeting</div>
    </div>
    <div class="demo-screen-body" style="gap:0">
      <div class="demo-qa-thread">
        <div class="demo-qa-thread-inner"></div>
      </div>
    </div>
    <div class="demo-screen-footer" style="display:flex;flex-direction:column;gap:10px;">
      <button class="demo-btn-secondary demo-ask-btn"></button>
      <button class="demo-btn-primary demo-goto" data-goto="5">Finish review</button>
    </div>`;

  const screen5 = `
    <div style="padding:40px 16px 16px;flex:1;display:flex;flex-direction:column">
      <div class="demo-done-center">
        <div class="demo-done-icon">
          <svg width="16" height="16" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        <div class="demo-done-title">Meeting processed</div>
        <div class="demo-done-sub">Project Kickoff &middot; onboarding refresh summary saved and action items extracted.</div>
      </div>
      <div class="demo-status-rows">
        <div class="demo-status-row"><span>Summary &amp; checklist</span><span class="demo-status-val green">Saved</span></div>
        <div class="demo-status-row"><span>4 action items</span><span class="demo-status-val green">Extracted</span></div>
        <div class="demo-status-row"><span>Context enrichment</span><span class="demo-status-val green">3 insights</span></div>
        <div class="demo-status-row"><span>Q&amp;A grounding</span><span class="demo-status-val orange">Indexed</span></div>
      </div>
      <button class="demo-btn-ghost demo-reset">Start new recording</button>
    </div>`;

  root.innerHTML = `
    <div class="demo-banner">
      <div>
        <div class="demo-banner-title">Voice to summary <u>demo flow</u></div>
        <div class="demo-banner-sub">Project kickoff meeting &middot; onboarding refresh</div>
      </div>
      <div class="demo-step-counter">Step <strong class="demo-step-num">1</strong> / 6</div>
    </div>

    <div class="demo-controls-area">
      <div class="demo-tab-strip"></div>
      <div class="demo-dots"></div>
    </div>

    <div class="demo-filmstrip">
      ${deviceWrap(0, "1. Record",    screen0)}
      ${deviceWrap(1, "2. Summary",   screen1)}
      ${deviceWrap(2, "3. Checklist", screen2)}
      ${deviceWrap(3, "4. Enriched",  screen3)}
      ${deviceWrap(4, "5. Q&A",       screen4)}
      ${deviceWrap(5, "6. Done",      screen5)}
    </div>

    <div class="demo-nav-btns">
      <button class="demo-nav-btn demo-nav-back" disabled>Back</button>
      <button class="demo-nav-btn demo-nav-next">Next</button>
    </div>
  `;

  root.querySelectorAll(".demo-goto").forEach((btn) => {
    btn.addEventListener("click", () => demoGoTo(Number(btn.dataset.goto)));
  });
  root.querySelectorAll(".demo-device").forEach((d) => {
    d.addEventListener("click", () => demoGoTo(Number(d.dataset.idx)));
  });
  root.querySelector(".demo-nav-back").addEventListener("click", () => demoGoTo(demoCurrent - 1));
  root.querySelector(".demo-nav-next").addEventListener("click", () => demoGoTo(demoCurrent + 1));
  root.querySelector(".demo-reset").addEventListener("click", demoReset);
  root.querySelector(".demo-ask-btn").addEventListener("click", () => {
    if (demoQaAsked < DEMO_QA.length) { demoQaAsked++; renderDemoQA(); }
  });

  renderDemoTabs();
  renderDemoChecklist();
  renderDemoQA();
}

// ---------- Nav ----------
function setupNav() {
  const navItems = document.querySelectorAll(".nav-item");
  const pages = {
    demo: document.getElementById("demo-page"),
    concepts: document.getElementById("concepts-page"),
    scenarios: document.getElementById("scenarios-page"),
    story: document.getElementById("story-page"),
    pipeline: document.getElementById("pipeline-page"),
    voicequery: document.getElementById("voicequery-page"),
    evaluation: document.getElementById("evaluation-page"),
    roadmap: document.getElementById("roadmap-page"),
  };
  navItems.forEach((item) => {
    item.addEventListener("click", () => {
      navItems.forEach((t) => t.setAttribute("aria-pressed", "false"));
      item.setAttribute("aria-pressed", "true");
      Object.entries(pages).forEach(([key, el]) => {
        el.classList.toggle("hidden", key !== item.dataset.page);
      });

      // Always re-render on nav click, not just the first visit — both pages
      // can change from Pipeline-triggered runs (phase6-history/phase1-4 scenarios re-summarized,
      // new judged runs added to history) after the first time you look.
      if (item.dataset.page === "demo") {
        renderDemoPage();
      }

      if (item.dataset.page === "concepts") {
        renderConceptsPage();
      }

      if (item.dataset.page === "evaluation") {
        renderEvaluationPage();
      }

      if (item.dataset.page === "story") {
        renderStoryPage();
      }

      if (item.dataset.page === "roadmap") {
        renderRoadmapPage();
      }

      if (item.dataset.page === "pipeline") {
        startPipelinePagePolling();
      } else {
        stopPipelinePagePolling();
      }

      if (item.dataset.page === "voicequery") {
        renderVoiceQueryPage();
      } else {
        stopVoiceQueryPolling();
      }
    });
  });
}

function setupDrawer() {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("drawer-toggle");
  toggle.addEventListener("click", () => sidebar.classList.toggle("collapsed"));
}

// --- Auth ---
// Adds Bearer token to API fetches when auth is enabled (VTS_AUTH=google on
// the server). On localhost, auth is disabled and this is a no-op.
const _origFetch = window.fetch;
window.fetch = function(url, opts = {}) {
  const token = localStorage.getItem("vts_token");
  if (token && typeof url === "string" && url.startsWith("/api/")) {
    opts.headers = { ...(opts.headers || {}), "Authorization": `Bearer ${token}` };
  }
  return _origFetch.call(this, url, opts);
};

async function checkAuth() {
  try {
    const res = await _origFetch("/api/auth/enabled");
    const data = await res.json();
    if (!data.enabled) return;
  } catch { return; }

  const token = localStorage.getItem("vts_token");
  if (token) {
    try {
      const res = await _origFetch("/auth/check", {
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (res.ok) return;
    } catch { /* fall through to login */ }
    localStorage.removeItem("vts_token");
  }
  window.location.href = "/auth/login";
}

checkAuth().then(() => {
  renderConceptsPage();
  renderTechSummary();
  renderEvalSummaryTable();
  renderScenarioGrid();
  setupNav();
  setupDrawer();
});
