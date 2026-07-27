"""Shared stage-progress reporting between a pipeline's main.py (running as a
subprocess, launched by the webapp) and webapp/server.py (polling the file).

Each vN/src/main.py's `run_pipeline(on_stage=...)` calls write_status() on
every stage transition when run with `--status-file`; the webapp reads it
back with read_status() to answer GET /api/pipeline/status.
"""
import json
import os
import time


def write_status(status_file, stage, detail=None):
    tmp = status_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"stage": stage, "detail": detail, "updated_at": time.time()}, f)
    os.replace(tmp, status_file)  # atomic on POSIX, avoids a torn read


def read_status(status_file):
    try:
        with open(status_file) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
