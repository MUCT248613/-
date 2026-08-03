"""
Backend supervisor.

Runs uvicorn as a blocking child and restarts it if it ever exits. The
supervisor itself is a simple blocking script (like `python -m http.server`),
which survives in a background terminal; it keeps the API alive by relaunching
uvicorn whenever the child terminates (e.g. on console-detach signals).
"""
import subprocess
import sys
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    cmd = [
        sys.executable, "-m", "uvicorn", "src.api.main:app",
        "--host", "0.0.0.0", "--port", "6668",
    ]
    while True:
        proc = subprocess.Popen(cmd, cwd=ROOT)
        proc.wait()
        sys.stdout.write(f"[supervisor] uvicorn exited code={proc.returncode}, restarting in 1s\n")
        sys.stdout.flush()
        time.sleep(1)

if __name__ == "__main__":
    main()
