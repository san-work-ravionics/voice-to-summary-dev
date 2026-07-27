import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import urllib.parse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_AUDIO_DIR = os.path.join(PROJECT_ROOT, "custom", "audio")
CUSTOM_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "custom", "output")
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}

sys.path.insert(0, PROJECT_ROOT)
from pipeline_status import read_status  # noqa: E402
from run_history import read_history  # noqa: E402

# New audio dropped in custom/audio/ is arbitrary, real content — it doesn't
# belong to the scripted "Mobile App Redesign" dummy meeting, so v2's
# MEETING_CONTEXT and v3/v4's CHECKLIST (both hardcoded to that scenario)
# would not apply. Run v1's plain baseline pipeline instead.
sys.path.insert(0, os.path.join(PROJECT_ROOT, "v1", "src"))

# filename -> "processing" | "done" | "error:<message>"
JOBS = {}
# filename -> "transcribing" | "summarizing", present only while processing
JOB_STAGE = {}
JOBS_LOCK = threading.Lock()

# --- Scenario pipelines (v1-v4, story): triggered + monitored from the
# Pipeline page. Each is run as a subprocess of its own main.py — the same
# script the README tells you to run by hand — rather than imported in
# process, since v1-v4/story all define sibling modules with the same names
# (summarize, transcribe, ...) and Python's module cache is keyed by name,
# not by directory; importing more than one version into the same process
# would silently alias them.
SCENARIOS = {
    "v1": {
        "label": "v1 — Baseline pipeline",
        "main_path": os.path.join(PROJECT_ROOT, "v1", "src", "main.py"),
        "stages": ["recording", "transcribing", "summarizing", "judging", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "v1", "output", "summary.txt"),
    },
    "v2": {
        "label": "v2 — Context-aware pipeline",
        "main_path": os.path.join(PROJECT_ROOT, "v2", "src", "main.py"),
        "stages": ["recording", "transcribing", "summarizing_baseline", "judging_baseline",
                   "summarizing_context", "judging_context", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "v2", "output", "summary_with_context.txt"),
    },
    "v3": {
        "label": "v3 — Checklist coverage pipeline",
        "main_path": os.path.join(PROJECT_ROOT, "v3", "src", "main.py"),
        "stages": ["recording", "transcribing", "summarizing", "judging", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "v3", "output", "summary.txt"),
    },
    "v4": {
        "label": "v4 — AI assistant in the room",
        "main_path": os.path.join(PROJECT_ROOT, "v4", "src", "main.py"),
        "stages": ["recording", "transcribing", "summarizing", "judging", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "v4", "output", "summary.txt"),
    },
    "story": {
        "label": "story — 5-meeting arc",
        "main_path": os.path.join(PROJECT_ROOT, "story", "src", "main.py"),
        "stages": ["recording", "transcribing", "summarizing_baseline", "judging_baseline",
                   "summarizing_context", "judging_context", "done"],
        "final_output": os.path.join(PROJECT_ROOT, "story", "output", "meeting-5", "summary_with_context.txt"),
    },
}
SCENARIO_ORDER = ["v1", "v2", "v3", "v4", "story"]
RUN_STATUS_DIR = os.path.join(PROJECT_ROOT, "webapp", ".run_status")

# scenario id -> {"status": "running"|"done"|"error", "error": str|None,
#                 "provider": str|None, "status_file": path, "proc": Popen}
PIPELINE_JOBS = {}
PIPELINE_LOCK = threading.Lock()


def _start_pipeline(scenario_id, provider=None, judge_provider=None, regenerate=False):
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

    def waiter():
        _stdout, stderr = proc.communicate()
        with PIPELINE_LOCK:
            job = PIPELINE_JOBS.get(scenario_id)
            if job is None or job["proc"] is not proc:
                return  # superseded by a newer run of the same scenario
            if proc.returncode == 0:
                job["status"] = "done"
            else:
                job["status"] = "error"
                lines = [l for l in (stderr or "").strip().splitlines() if l]
                job["error"] = lines[-1] if lines else f"exited with code {proc.returncode}"

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
        status = "done" if last_run_at is not None else "not_run"
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


def _run_pipeline_async(filename, provider=None):
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

            text = transcribe(audio_path)
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
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
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
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/run-pipeline":
            return self._handle_run_pipeline()
        if parsed.path == "/api/pipeline/run":
            return self._handle_pipeline_run()
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

        started = _start_pipeline(
            scenario_id, provider=provider, judge_provider=judge_provider, regenerate=regenerate,
        )
        self._send_json({"status": "started" if started else "already_running"})

    def _handle_eval_history(self, query):
        scenario_id = (query.get("scenario") or [None])[0]
        if scenario_id is not None and scenario_id not in SCENARIOS:
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

        started = _run_pipeline_async(filename, provider=provider)
        self._send_json({"status": "started" if started else "already_processing"})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    os.makedirs(CUSTOM_AUDIO_DIR, exist_ok=True)
    os.makedirs(CUSTOM_OUTPUT_DIR, exist_ok=True)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8743
    with socketserver.ThreadingTCPServer(("", port), Handler) as httpd:
        print(f"Serving {PROJECT_ROOT}")
        print(f"Open http://localhost:{port}/webapp/index.html")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
