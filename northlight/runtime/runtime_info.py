import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_runtime_info():
    def run(cmd):
        return subprocess.check_output(cmd, shell=True).decode().strip()

    # Resolve repo root based on THIS file's location
    repo_path = Path(__file__).resolve().parent

    try:
        tag = run(f"git -C {repo_path} describe --tags --abbrev=0")
    except Exception:
        tag = "dev"

    try:
        commit = run(f"git -C {repo_path} rev-parse --short HEAD")
    except Exception:
        commit = "unknown"

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    return {
        "version": tag,
        "commit": commit,
        "run_id": run_id,
    }
