#!/usr/bin/env python3
"""One command to run TraceLink locally:  python dev.py

It prepares everything the first time (virtual environment, packages, secrets,
website packages), then starts the backend and the website and waits until both
answer. Press Ctrl+C to stop both.

Options:
  --lan   let other devices on your network reach it (binds 0.0.0.0)
  --adb   also link a USB-connected Android phone: its localhost -> this laptop
"""

import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
WINDOWS = os.name == "nt"
VENV_PY = BACKEND / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")


def say(msg: str) -> None:
    print(f"[tracelink] {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"\n[tracelink] PROBLEM: {msg}\n", flush=True)
    sys.exit(1)


def run(cmd, cwd=None, quiet=False):
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.DEVNULL if quiet else None)
    if r.returncode != 0:
        fail(f"command failed: {' '.join(map(str, cmd))}")


def prepare_backend() -> None:
    if sys.version_info < (3, 10):
        fail("Python 3.10 or newer is needed. Install it from python.org and tick 'Add to PATH'.")
    if not VENV_PY.exists():
        say("creating the Python environment (first time only)...")
        run([sys.executable, "-m", "venv", str(BACKEND / ".venv")])
    say("installing backend packages (quick if already installed)...")
    run([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(BACKEND / "requirements.txt")])

    env_file = BACKEND / ".env"
    if not env_file.exists():
        say("creating backend/.env with fresh random secrets...")
        fernet = subprocess.check_output(
            [str(VENV_PY), "-c", "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"],
            text=True,
        ).strip()
        env_file.write_text(
            f"JWT_SECRET={secrets.token_urlsafe(48)}\n"
            f"IMEI_HMAC_KEY={secrets.token_urlsafe(48)}\n"
            f"IMEI_ENCRYPTION_KEY={fernet}\n"
            "DATABASE_URL=sqlite:///./tracelink.db\n"
            "DEMO_MODE=true\n"
            "MODEL_API_KEY=\n"
            "MODEL_NAME=muse-spark-1.3\n"
        )
        say("backend/.env created. Put your Meta key after MODEL_API_KEY= to turn the AI on.")


def prepare_frontend() -> str:
    npm = shutil.which("npm")
    if not npm:
        fail("Node.js is not installed. Get the LTS version from nodejs.org, then reopen this terminal.")
    if not (FRONTEND / "node_modules").exists():
        say("installing website packages (first time only, about a minute)...")
        run([npm, "install", "--no-audit", "--no-fund"], cwd=FRONTEND)
    return npm


def wait_for(url: str, name: str, seconds: int = 60) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(1)
    fail(f"{name} did not start. Look at the messages above for the error.")


def link_phone() -> None:
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or (
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk") if WINDOWS
        else str(Path.home() / "Android" / "Sdk"))
    adb = shutil.which("adb") or str(Path(sdk) / "platform-tools" / ("adb.exe" if WINDOWS else "adb"))
    if not Path(adb).exists() and not shutil.which("adb"):
        say("adb not found; skipping the phone link. Install Android Studio or set ANDROID_HOME.")
        return
    for port in (8000, 5173):
        r = subprocess.run([adb, "reverse", f"tcp:{port}", f"tcp:{port}"], capture_output=True, text=True)
        say(f"phone link port {port}: " + ("ok" if r.returncode == 0 else (r.stderr.strip() or "failed: is the phone plugged in with USB debugging on?")))


def main() -> None:
    lan = "--lan" in sys.argv
    prepare_backend()
    npm = prepare_frontend()
    host = "0.0.0.0" if lan else "127.0.0.1"

    say("starting the backend...")
    api = subprocess.Popen([str(VENV_PY), "-m", "uvicorn", "app.main:app", "--host", host, "--port", "8000"], cwd=BACKEND)
    web = None
    try:
        wait_for("http://127.0.0.1:8000/health", "The backend")
        say("starting the website...")
        web_cmd = [npm, "run", "dev", "--"] + (["--host"] if lan else [])
        web = subprocess.Popen(web_cmd, cwd=FRONTEND)
        wait_for("http://127.0.0.1:5173/api/health", "The website")
        if "--adb" in sys.argv:
            link_phone()
        print("\n" + "=" * 60)
        say("READY")
        say("website : http://localhost:5173")
        say("backend : http://localhost:8000/health")
        if "--adb" in sys.argv:
            say("on the USB phone use the same addresses (localhost)")
        say("press Ctrl+C here to stop everything")
        print("=" * 60 + "\n", flush=True)
        while api.poll() is None and web.poll() is None:
            time.sleep(1)
        fail("one of the servers stopped. Read the messages above.")
    except KeyboardInterrupt:
        say("stopping...")
    finally:
        for proc in (web, api):
            if proc and proc.poll() is None:
                proc.terminate()


if __name__ == "__main__":
    main()
