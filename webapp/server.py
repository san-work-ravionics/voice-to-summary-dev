import datetime
import hashlib
import hmac
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

sys.path.insert(0, PROJECT_ROOT)
from app_logging import get_logger  # noqa: E402
from pipeline_status import read_status  # noqa: E402
from run_history import read_history  # noqa: E402

logger = get_logger("webapp")

_BOOT_VERSION = hashlib.md5(str(os.getpid()).encode() + str(os.path.getmtime(__file__)).encode()).hexdigest()[:10]

sys.path.insert(0, os.path.join(PROJECT_ROOT, "phase8-voice-query", "src"))
from query_history import read_history as read_voice_query_history  # noqa: E402

# --- Google OAuth (disabled locally, enabled via VTS_AUTH=google) -----------
VTS_AUTH = os.environ.get("VTS_AUTH", "")
VTS_JWT_SECRET = os.environ.get("VTS_JWT_SECRET", "")
VTS_BASE_URL = os.environ.get("VTS_BASE_URL", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
JWT_EXPIRY_HOURS = 24
AUTH_ENABLED = VTS_AUTH.lower() == "google"


def _jwt_encode(payload, secret):
    import base64 as b64
    header = b64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=")
    body = b64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    signing_input = header + b"." + body
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = b64.urlsafe_b64encode(sig).rstrip(b"=")
    return (signing_input + b"." + sig_b64).decode()


def _jwt_decode(token, secret):
    import base64 as b64
    parts = token.split(".")
    if len(parts) != 3:
        return None
    signing_input = (parts[0] + "." + parts[1]).encode()
    expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    def _pad(s):
        return s + "=" * (-len(s) % 4)
    try:
        actual_sig = b64.urlsafe_b64decode(_pad(parts[2]))
    except Exception:
        return None
    if not hmac.compare_digest(expected_sig, actual_sig):
        return None
    try:
        payload = json.loads(b64.urlsafe_b64decode(_pad(parts[1])))
    except Exception:
        return None
    if payload.get("exp", 0) < datetime.datetime.utcnow().timestamp():
        return None
    return payload


def _create_token(email):
    exp = datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRY_HOURS)
    return _jwt_encode({"sub": email, "exp": exp.timestamp()}, VTS_JWT_SECRET)


def _verify_token(token):
    if not token or not VTS_JWT_SECRET:
        return None
    payload = _jwt_decode(token, VTS_JWT_SECRET)
    return payload.get("sub") if payload else None


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
                stderr_text = (stderr or "").strip()
                lines = [l for l in stderr_text.splitlines() if l]
                if proc.returncode == -9 or "MemoryError" in stderr_text:
                    job["error"] = "Out of memory — process was killed (signal 9)"
                else:
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


DEMO_MEETING = "01-kickoff"
DEMO_OUTPUTS = {
    "phase1_summary": os.path.join(PROJECT_ROOT, "phase1-baseline", "output", DEMO_MEETING, "summary.txt"),
    "phase2_summary": os.path.join(PROJECT_ROOT, "phase2-checklist", "output", DEMO_MEETING, "summary.txt"),
    "phase3_baseline": os.path.join(PROJECT_ROOT, "phase3-context", "output", DEMO_MEETING, "summary_baseline.txt"),
    "phase3_context": os.path.join(PROJECT_ROOT, "phase3-context", "output", DEMO_MEETING, "summary_with_context.txt"),
}
DEMO_AUDIO = f"/audio-generation/output/{DEMO_MEETING}/recording.wav"


def _parse_summary_sections(text):
    sections = {}
    current_heading = None
    current_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        heading_match = None
        if stripped.startswith("##"):
            heading_match = stripped.lstrip("#").strip()
        if heading_match:
            if current_heading:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = heading_match.lower()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading:
        sections[current_heading] = "\n".join(current_lines)
    return sections


def _extract_bullets(section_text):
    bullets = []
    for line in section_text.split("\n"):
        stripped = line.strip()
        m = None
        if stripped.startswith("- "):
            m = stripped[2:]
        elif stripped.startswith("* "):
            m = stripped[2:]
        if m:
            m = m.lstrip("*").strip()
            if m.endswith(":"):
                continue
            if m:
                bullets.append(m)
    return bullets


def _build_demo_data():
    result = {"audio": DEMO_AUDIO, "meeting": DEMO_MEETING}

    for key, path in DEMO_OUTPUTS.items():
        try:
            with open(path) as f:
                text = f.read()
        except FileNotFoundError:
            result[key] = None
            continue
        sections = _parse_summary_sections(text)
        result[key] = {
            "topic": sections.get("topic", "").strip(),
            "key_points": _extract_bullets(sections.get("key points", "")),
            "decisions": _extract_bullets(sections.get("decisions", "")),
            "actions": _extract_bullets(sections.get("actions", "")),
        }
        if "checklist coverage" in sections:
            result[key]["checklist_coverage"] = sections["checklist coverage"].strip()

    vq_history_path = os.path.join(PROJECT_ROOT, "phase8-voice-query", "output", "query_history.jsonl")
    qa_pairs = []
    try:
        with open(vq_history_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("answer") and not rec["answer"].startswith("I couldn't find"):
                    qa_pairs.append({"q": rec["question"], "a": rec["answer"]})
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    result["voice_query_history"] = qa_pairs

    return result


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_ROOT, **kwargs)

    def end_headers(self):
        if getattr(self, "_no_cache", False):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self._no_cache = False
        super().end_headers()

    def _serve_index_html(self):
        index_path = os.path.join(PROJECT_ROOT, "webapp", "index.html")
        with open(index_path, "r") as f:
            html = f.read()
        v = _BOOT_VERSION
        html = html.replace("/webapp/style.css", f"/webapp/style.css?v={v}")
        html = html.replace("/webapp/app.js", f"/webapp/app.js?v={v}")
        self._send_html(html)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_bearer_token(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None

    def _check_auth(self):
        if not AUTH_ENABLED:
            return True
        token = self._get_bearer_token()
        return _verify_token(token) is not None

    def _handle_auth_login(self):
        callback = VTS_BASE_URL.rstrip("/") + "/auth/callback"
        url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            "response_type=code&"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={urllib.parse.quote(callback, safe='')}&"
            "scope=openid%20email%20profile&"
            "access_type=offline"
        )
        return self._send_redirect(url)

    def _handle_auth_callback(self, query):
        code = (query.get("code") or [None])[0]
        if not code:
            return self._send_json({"error": "no code"}, status=400)

        callback = VTS_BASE_URL.rstrip("/") + "/auth/callback"
        try:
            import urllib.request
            data = urllib.parse.urlencode({
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": callback,
                "grant_type": "authorization_code",
            }).encode()
            req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req) as resp:
                tokens = json.loads(resp.read())
        except Exception as exc:
            logger.error("OAuth token exchange failed: %s", exc)
            return self._send_json({"error": "token exchange failed"}, status=400)

        id_token = tokens.get("id_token")
        if not id_token:
            return self._send_json({"error": "no id_token"}, status=400)

        import base64 as b64
        try:
            payload_b64 = id_token.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            id_payload = json.loads(b64.urlsafe_b64decode(payload_b64))
        except Exception:
            return self._send_json({"error": "invalid id_token"}, status=400)

        email = id_payload.get("email")
        if not email:
            return self._send_json({"error": "no email in token"}, status=400)

        jwt_token = _create_token(email)
        logger.info("auth: login %s", email)
        self._send_html(f"""<!doctype html><html><head><title>Redirecting…</title></head>
<body><script>
localStorage.setItem("vts_token", {json.dumps(jwt_token)});
window.location.href = "/webapp/index.html";
</script></body></html>""")

    def _handle_auth_check(self):
        token = self._get_bearer_token()
        email = _verify_token(token)
        if email:
            return self._send_json({"authenticated": True, "email": email})
        return self._send_json({"authenticated": False}, status=401)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            return self._send_redirect("/webapp/index.html")
        if parsed.path == "/healthz":
            return self._send_json({"status": "ok"})
        if parsed.path == "/auth/login":
            return self._handle_auth_login()
        if parsed.path == "/auth/callback":
            return self._handle_auth_callback(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/auth/check":
            return self._handle_auth_check()
        if parsed.path == "/api/auth/enabled":
            return self._send_json({"enabled": AUTH_ENABLED})

        if parsed.path.startswith("/api/") and not self._check_auth():
            return self._send_json({"error": "unauthorized"}, status=401)

        if parsed.path == "/api/demo/data":
            return self._handle_demo_data()
        if parsed.path == "/api/pipeline/status":
            return self._handle_pipeline_status()
        if parsed.path == "/api/eval/history":
            return self._handle_eval_history(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/voice-query/status":
            return self._handle_voice_query_status(urllib.parse.parse_qs(parsed.query))
        if parsed.path == "/api/voice-query/history":
            return self._handle_voice_query_history()
        if parsed.path == "/webapp/index.html":
            self._no_cache = True
            return self._serve_index_html()
        if parsed.path.startswith("/webapp/"):
            self._no_cache = True
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path.startswith("/api/") and not self._check_auth():
            return self._send_json({"error": "unauthorized"}, status=401)

        if parsed.path == "/api/pipeline/run":
            return self._handle_pipeline_run()
        if parsed.path == "/api/voice-query":
            return self._handle_voice_query_start(urllib.parse.parse_qs(parsed.query))
        self.send_error(404)

    def _handle_demo_data(self):
        self._send_json(_build_demo_data())

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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8743
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", port), Handler) as httpd:
        logger.info("Serving %s", PROJECT_ROOT)
        logger.info("Open http://localhost:%s/webapp/index.html", port)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
