import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import urllib.parse
import uuid

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_AUDIO_DIR = os.path.join(PROJECT_ROOT, "custom", "audio")
CUSTOM_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "custom", "output")
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}

sys.path.insert(0, PROJECT_ROOT)
from app_logging import get_logger  # noqa: E402
from pipeline_status import read_status  # noqa: E402
from run_history import read_history  # noqa: E402

logger = get_logger("webapp")

# New audio dropped in custom/audio/ is arbitrary, real content — it doesn't
# belong to the scripted "Mobile App Redesign" kickoff meeting, so
# phase3-context's MEETING_CONTEXT and phase2-checklist/phase4-assistant's
# CHECKLIST (both hardcoded to that scenario) would not apply. Run
# phase1-baseline's plain baseline pipeline instead.
sys.path.insert(0, os.path.join(PROJECT_ROOT, "phase1-baseline", "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "phase8-voice-query", "src"))
from query_history import read_history as read_voice_query_history  # noqa: E402

# filename -> "processing" | "done" | "error:<message>"
JOBS = {}
# filename -> "transcribing" | "summarizing", present only while processing
JOB_STAGE = {}
JOBS_LOCK = threading.Lock()

# --- Scenario pipelines (phase1-baseline, phase2-checklist, phase3-context,
# phase4-assistant, phase6-history): triggered + monitored from the Pipeline
# page. Each is run as a subprocess of its own main.py — the same script the
# README tells you to run by hand — rather than imported in process, since
# all of them define sibling modules with the same names (summarize,
# transcribe, ...) and Python's module cache is keyed by name, not by
# directory; importing more than one into the same process would silently
# alias them. Phase 5 (office-agent) and Phase 8 (voice-query) have their
# own dedicated flows below, not the shared Pipeline panel.
SCENARIOS = {
    "phase1-baseline": {
        "label": "Phase 1 — Basic summary",
        "main_path": os.path.join(PROJECT_ROOT, "phase1-baseline", "src", "main.py"),
        "stages": ["transcribing", "summarizing", "judging", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "phase1-baseline", "output", "15-launch-retro", "summary.txt"),
    },
    "phase2-checklist": {
        "label": "Phase 2 — Checklist coverage",
        "main_path": os.path.join(PROJECT_ROOT, "phase2-checklist", "src", "main.py"),
        "stages": ["transcribing", "summarizing", "judging", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "phase2-checklist", "output", "15-launch-retro", "summary.txt"),
    },
    "phase3-context": {
        "label": "Phase 3 — Context-aware summary",
        "main_path": os.path.join(PROJECT_ROOT, "phase3-context", "src", "main.py"),
        "stages": ["transcribing", "summarizing_baseline", "judging_baseline",
                   "summarizing_context", "judging_context", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "phase3-context", "output", "15-launch-retro", "summary_with_context.txt"),
    },
    "phase4-assistant": {
        "label": "Phase 4 — AI assistant in the room",
        "main_path": os.path.join(PROJECT_ROOT, "phase4-assistant", "src", "main.py"),
        "stages": ["transcribing", "summarizing", "judging", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "phase4-assistant", "output", "15-launch-retro", "summary.txt"),
    },
    "phase6-history": {
        "label": "Phase 6 — 15-meeting RAG history",
        "main_path": os.path.join(PROJECT_ROOT, "phase6-history", "src", "main.py"),
        "stages": ["transcribing", "summarizing_baseline", "judging_baseline",
                   "summarizing_context", "judging_context", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "phase6-history", "output", "15-launch-retro", "summary_with_context.txt"),
    },
    "phase7-reference-rag": {
        "label": "Phase 7 — Reference-document RAG",
        "main_path": os.path.join(PROJECT_ROOT, "phase7-reference-rag", "src", "main.py"),
        "stages": ["transcribing", "retrieving", "summarizing_baseline", "judging_baseline",
                   "summarizing_with_references", "judging_with_references", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "phase7-reference-rag", "output", "15-launch-retro", "summary_with_references.txt"),
    },
}
SCENARIO_ORDER = [
    "phase1-baseline", "phase2-checklist", "phase3-context", "phase4-assistant",
    "phase6-history", "phase7-reference-rag",
]
RUN_STATUS_DIR = os.path.join(PROJECT_ROOT, "webapp", ".run_status")

# /api/eval/history's ?scenario= filter accepts more than just the
# Pipeline-page-triggerable SCENARIOS above — phase5-office-agent writes to
# the same run_history.jsonl (see phase5-office-agent/src/main.py) but has
# no subprocess-triggered Pipeline panel, so it isn't in SCENARIOS itself.
KNOWN_EVAL_SCENARIOS = set(SCENARIOS) | {"phase5-office-agent"}

# Scenarios whose main.py accepts --retrieval tfidf|faiss (see
# faiss_retrieval.py) — only phase7-reference-rag so far.
RETRIEVAL_CAPABLE_SCENARIOS = {"phase7-reference-rag"}

# scenario id -> {"status": "running"|"done"|"error", "error": str|None,
#                 "provider": str|None, "status_file": path, "proc": Popen}
PIPELINE_JOBS = {}
PIPELINE_LOCK = threading.Lock()

# --- Voice Query (Phase 8): records a question with the browser mic, runs
# phase8-voice-query/src/main.py as a subprocess (same reasoning as
# SCENARIOS above) and polls it the same way the Pipeline page does.
VOICE_QUERY_MAIN = os.path.join(PROJECT_ROOT, "phase8-voice-query", "src", "main.py")
VOICE_QUERY_UPLOAD_DIR = os.path.join(PROJECT_ROOT, "phase8-voice-query", "output", "_uploads")
VOICE_QUERY_AUDIO_EXT_BY_CONTENT_TYPE = {
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/wav": ".wav",
}

# job_id -> {"status": "running"|"done"|"error", "error": str|None,
#            "status_file": path, "result_file": path, "proc": Popen}
VOICE_QUERY_JOBS = {}
VOICE_QUERY_LOCK = threading.Lock()


def _start_voice_query(audio_path, provider=None, retrieval=None):
    job_id = uuid.uuid4().hex[:12]
    os.makedirs(RUN_STATUS_DIR, exist_ok=True)
    status_file = os.path.join(RUN_STATUS_DIR, f"voicequery-{job_id}.json")
    result_file = os.path.join(RUN_STATUS_DIR, f"voicequery-{job_id}.result.json")

    cmd = [sys.executable, VOICE_QUERY_MAIN, audio_path, "--status-file", status_file, "--result-file", result_file]
    if provider:
        cmd += ["--provider", provider]
    if retrieval:
        cmd += ["--retrieval", retrieval]

    proc = subprocess.Popen(
        cmd, cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    with VOICE_QUERY_LOCK:
        VOICE_QUERY_JOBS[job_id] = {
            "status": "running", "error": None,
            "status_file": status_file, "result_file": result_file, "proc": proc,
        }
    logger.info("voice-query %s: started (provider=%s retrieval=%s)", job_id, provider, retrieval)

    def waiter():
        stdout, stderr = proc.communicate()
        with VOICE_QUERY_LOCK:
            job = VOICE_QUERY_JOBS.get(job_id)
            if job is None or job["proc"] is not proc:
                return
            if proc.returncode == 0:
                job["status"] = "done"
                logger.info("voice-query %s: done\n--- stdout ---\n%s", job_id, stdout)
            else:
                job["status"] = "error"
                lines = [l for l in (stderr or "").strip().splitlines() if l]
                job["error"] = lines[-1] if lines else f"exited with code {proc.returncode}"
                logger.error(
                    "voice-query %s: failed (exit %s)\n--- stdout ---\n%s\n--- stderr ---\n%s",
                    job_id, proc.returncode, stdout, stderr,
                )

    threading.Thread(target=waiter, daemon=True).start()
    return job_id


def _voice_query_status(job_id):
    with VOICE_QUERY_LOCK:
        job = VOICE_QUERY_JOBS.get(job_id)
        job = dict(job) if job else None
    if job is None:
        return None

    file_status = read_status(job["status_file"])
    stage = file_status.get("stage") if file_status else None

    payload = {"status": job["status"], "stage": stage, "error": job["error"], "result": None}
    if job["status"] == "done":
        try:
            with open(job["result_file"]) as f:
                payload["result"] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            payload["result"] = None
    return payload


def _start_pipeline(scenario_id, provider=None, judge_provider=None, regenerate=False, retrieval=None):
    scenario = SCENARIOS[scenario_id]
    with PIPELINE_LOCK:
        job = PIPELINE_JOBS.get(scenario_id)
        if job and job["status"] == "running":
            return False

        os.makedirs(RUN_STATUS_DIR, exist_ok=True)
        status_file = os.path.join(RUN_STATUS_DIR, f"{scenario_id}.json")
        if os.path.exists(status_file):
            os.remove(status_file)

        cmd = [sys.executable, scenario["main_path"], "--status-file", status_file]
        if provider:
            cmd += ["--provider", provider]
        if judge_provider:
            cmd += ["--judge-provider", judge_provider]
        if regenerate:
            cmd.append("--regenerate")
        # Only phase7-reference-rag's main.py declares --retrieval; passing
        # it to any other scenario's argparse would error out.
        if retrieval and scenario_id in RETRIEVAL_CAPABLE_SCENARIOS:
            cmd += ["--retrieval", retrieval]

        proc = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        PIPELINE_JOBS[scenario_id] = {
            "status": "running",
            "error": None,
            "provider": provider,
            "judge_provider": judge_provider,
            "status_file": status_file,
            "proc": proc,
        }
        logger.info(
            "pipeline %s: started (provider=%s judge_provider=%s regenerate=%s)",
            scenario_id, provider, judge_provider, regenerate,
        )

    def waiter():
        stdout, stderr = proc.communicate()
        with PIPELINE_LOCK:
            job = PIPELINE_JOBS.get(scenario_id)
            if job is None or job["proc"] is not proc:
                return  # superseded by a newer run of the same scenario
            if proc.returncode == 0:
                job["status"] = "done"
                logger.info("pipeline %s: done\n--- stdout ---\n%s", scenario_id, stdout)
            else:
                job["status"] = "error"
                lines = [l for l in (stderr or "").strip().splitlines() if l]
                job["error"] = lines[-1] if lines else f"exited with code {proc.returncode}"
                logger.error(
                    "pipeline %s: failed (exit %s)\n--- stdout ---\n%s\n--- stderr ---\n%s",
                    scenario_id, proc.returncode, stdout, stderr,
                )

    threading.Thread(target=waiter, daemon=True).start()
    return True


def _latest_summarizer_provider(scenario_id):
    """Falls back to the persisted run history for the provider that
    generated the current output — the in-memory PIPELINE_JOBS entry only
    covers runs triggered since this server process started, but the
    written-to-disk summary may be from an earlier session or a plain CLI
    run with --judge-provider set."""
    records = read_history(scenario_id)
    if not records:
        return None
    latest = max(records, key=lambda r: r.get("timestamp", 0))
    provider = latest.get("summarizer_provider")
    return provider if provider in ("local", "mistral", "claude") else None


def _pipeline_status(scenario_id):
    scenario = SCENARIOS[scenario_id]
    with PIPELINE_LOCK:
        job = PIPELINE_JOBS.get(scenario_id)
        job = dict(job) if job else None

    file_status = read_status(os.path.join(RUN_STATUS_DIR, f"{scenario_id}.json"))
    stage = file_status.get("stage") if file_status else None
    detail = file_status.get("detail") if file_status else None

    last_run_at = None
    if os.path.exists(scenario["final_output"]):
        last_run_at = os.path.getmtime(scenario["final_output"])

    if job is None:
        if file_status and stage and stage != "done":
            status = "running"
        elif last_run_at is not None:
            status = "done"
        else:
            status = "not_run"
        error = None
        provider = _latest_summarizer_provider(scenario_id)
        judge_provider = None
        if status == "done":
            stage = "done"
    else:
        status = job["status"]
        error = job["error"]
        provider = job["provider"]
        judge_provider = job["judge_provider"]
        if status == "done":
            stage = "done"

    return {
        "id": scenario_id,
        "label": scenario["label"],
        "stages": scenario["stages"],
        "status": status,
        "stage": stage,
        "detail": detail,
        "provider": provider,
        "judge_provider": judge_provider,
        "error": error,
        "last_run_at": last_run_at,
    }


def _safe_filename(filename):
    if not filename or not isinstance(filename, str):
        return None
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        return None
    return filename


def _stem(filename):
    return os.path.splitext(filename)[0]


def _output_dir(filename):
    return os.path.join(CUSTOM_OUTPUT_DIR, _stem(filename))


def _status_for(filename):
    with JOBS_LOCK:
        job_status = JOBS.get(filename)
    if job_status:
        return job_status
    summary_path = os.path.join(_output_dir(filename), "summary.txt")
    return "done" if os.path.exists(summary_path) else "not_run"


def _stage_for(filename):
    with JOBS_LOCK:
        return JOB_STAGE.get(filename)


def _run_pipeline_async(filename, provider=None, engine=None):
    with JOBS_LOCK:
        if JOBS.get(filename) == "processing":
            return False
        JOBS[filename] = "processing"
        JOB_STAGE[filename] = "transcribing"

    def work():
        try:
            from summarize import summarize
            from transcribe import transcribe

            audio_path = os.path.join(CUSTOM_AUDIO_DIR, filename)
            out_dir = _output_dir(filename)
            os.makedirs(out_dir, exist_ok=True)

            text = transcribe(audio_path, engine=engine)
            with open(os.path.join(out_dir, "transcript.txt"), "w") as f:
                f.write(text)

            with JOBS_LOCK:
                JOB_STAGE[filename] = "summarizing"

            summary = summarize(text, provider=provider)
            with open(os.path.join(out_dir, "summary.txt"), "w") as f:
                f.write(summary)

            with JOBS_LOCK:
                JOBS[filename] = "done"
                JOB_STAGE.pop(filename, None)
            logger.info("custom-audio %s: done", filename)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            logger.exception("custom-audio %s: failed", filename)
            with JOBS_LOCK:
                JOBS[filename] = f"error:{exc}"
                JOB_STAGE.pop(filename, None)

    threading.Thread(target=work, daemon=True).start()
    return True


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_ROOT, **kwargs)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            return self._send_json({"status": "ok"})
        if parsed.path == "/api/custom-audio":
            return self._handle_list_audio()
        if parsed.path == "/api/run-status":
            return self._handle_run_status(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/pipeline/status":
            return self._handle_pipeline_status()
        if parsed.path == "/api/eval/history":
            return self._handle_eval_history(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/voice-query/status":
            return self._handle_voice_query_status(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/voice-query/history":
            return self._handle_voice_query_history()
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/run-pipeline":
            return self._handle_run_pipeline()
        if parsed.path == "/api/pipeline/run":
            return self._handle_pipeline_run()
        if parsed.path == "/api/voice-query":
            return self._handle_voice_query_start(urllib.parse.parse_qs(parsed.query))
        self.send_error(404)

    def _handle_list_audio(self):
        os.makedirs(CUSTOM_AUDIO_DIR, exist_ok=True)
        files = []
        for name in sorted(os.listdir(CUSTOM_AUDIO_DIR)):
            if os.path.splitext(name)[1].lower() not in AUDIO_EXTENSIONS:
                continue
            status = _status_for(name)
            entry = {
                "filename": name,
                "audio_url": f"/custom/audio/{urllib.parse.quote(name)}",
                "status": "error" if status.startswith("error") else status,
            }
            if status == "processing":
                entry["stage"] = _stage_for(name)
            if status == "done":
                stem_q = urllib.parse.quote(_stem(name))
                entry["transcript_url"] = f"/custom/output/{stem_q}/transcript.txt"
                entry["summary_url"] = f"/custom/output/{stem_q}/summary.txt"
            if status.startswith("error"):
                entry["error"] = status.split(":", 1)[1]
            files.append(entry)
        self._send_json({"files": files})

    def _handle_run_status(self, query):
        filename = _safe_filename((query.get("filename") or [""])[0])
        if not filename:
            return self._send_json({"error": "invalid filename"}, status=400)
        status = _status_for(filename)
        payload = {"status": "error" if status.startswith("error") else status}
        if status == "processing":
            payload["stage"] = _stage_for(filename)
        if status.startswith("error"):
            payload["error"] = status.split(":", 1)[1]
        self._send_json(payload)

    def _handle_pipeline_status(self):
        self._send_json({"pipelines": [_pipeline_status(sid) for sid in SCENARIO_ORDER]})

    def _handle_pipeline_run(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid JSON"}, status=400)

        scenario_id = data.get("pipeline")
        if scenario_id not in SCENARIOS:
            return self._send_json({"error": "unknown pipeline"}, status=404)

        provider = data.get("provider")
        if provider not in (None, "local", "mistral", "claude"):
            return self._send_json({"error": "invalid provider"}, status=400)

        judge_provider = data.get("judge_provider")
        if judge_provider not in (None, "local", "mistral", "claude"):
            return self._send_json({"error": "invalid judge_provider"}, status=400)

        regenerate = bool(data.get("regenerate"))

        retrieval = data.get("retrieval")
        if retrieval not in (None, "tfidf", "faiss"):
            return self._send_json({"error": "invalid retrieval"}, status=400)

        started = _start_pipeline(
            scenario_id, provider=provider, judge_provider=judge_provider,
            regenerate=regenerate, retrieval=retrieval,
        )
        self._send_json({"status": "started" if started else "already_running"})

    def _handle_eval_history(self, query):
        scenario_id = (query.get("scenario") or [None])[0]
        if scenario_id is not None and scenario_id not in KNOWN_EVAL_SCENARIOS:
            return self._send_json({"error": "unknown pipeline"}, status=404)
        records = read_history(scenario_id)
        records.sort(key=lambda r: r.get("timestamp", 0))
        self._send_json({"records": records})

    def _handle_run_pipeline(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid JSON"}, status=400)

        filename = _safe_filename(data.get("filename"))
        if not filename or not os.path.exists(os.path.join(CUSTOM_AUDIO_DIR, filename)):
            return self._send_json({"error": "file not found"}, status=404)

        provider = data.get("provider")
        if provider not in (None, "local", "mistral", "claude"):
            return self._send_json({"error": "invalid provider"}, status=400)

        engine = data.get("engine")
        if engine not in (None, "whisper", "voxtral"):
            return self._send_json({"error": "invalid engine"}, status=400)

        started = _run_pipeline_async(filename, provider=provider, engine=engine)
        self._send_json({"status": "started" if started else "already_processing"})

    def _handle_voice_query_start(self, query):
        content_type = (self.headers.get("Content-Type") or "audio/webm").split(";")[0].strip()
        ext = VOICE_QUERY_AUDIO_EXT_BY_CONTENT_TYPE.get(content_type, ".webm")

        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return self._send_json({"error": "empty request body"}, status=400)
        audio_bytes = self.rfile.read(length)

        provider = (query.get("provider") or [None])[0]
        if provider not in (None, "local", "mistral", "claude"):
            return self._send_json({"error": "invalid provider"}, status=400)

        retrieval = (query.get("retrieval") or [None])[0]
        if retrieval not in (None, "tfidf", "faiss"):
            return self._send_json({"error": "invalid retrieval"}, status=400)

        os.makedirs(VOICE_QUERY_UPLOAD_DIR, exist_ok=True)
        audio_path = os.path.join(VOICE_QUERY_UPLOAD_DIR, f"{uuid.uuid4().hex[:12]}{ext}")
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        job_id = _start_voice_query(audio_path, provider=provider, retrieval=retrieval)
        self._send_json({"job": job_id})

    def _handle_voice_query_status(self, query):
        job_id = (query.get("job") or [None])[0]
        status = _voice_query_status(job_id) if job_id else None
        if status is None:
            return self._send_json({"error": "unknown job"}, status=404)
        self._send_json(status)

    def _handle_voice_query_history(self):
        records = read_voice_query_history()
        records.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        self._send_json({"records": records})

    def log_message(self, fmt, *args):
        # /healthz is polled every 30s by docker-compose's healthcheck —
        # excluded so it doesn't drown out real request logs.
        if getattr(self, "path", "").startswith("/healthz"):
            return
        logger.info("%s - %s", self.address_string(), fmt % args)


def main():
    os.makedirs(CUSTOM_AUDIO_DIR, exist_ok=True)
    os.makedirs(CUSTOM_OUTPUT_DIR, exist_ok=True)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8743
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", port), Handler) as httpd:
        logger.info("Serving %s", PROJECT_ROOT)
        logger.info("Open http://localhost:%s/webapp/index.html", port)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
