"""
Detached backend launcher.

Spawns uvicorn in a fully detached subprocess (new process group, no console
inheritance) so it survives the parent shell / sandbox detaching. Plain
`python -m uvicorn` exits cleanly on console CTRL_CLOSE events; detaching with
CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS prevents that.
"""
import subprocess
import sys
import os

CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008

def main():
    cmd = [
        sys.executable, "-m", "uvicorn", "src.api.main:app",
        "--host", "0.0.0.0", "--port", "6668",
    ]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
        kwargs["stdin"] = subprocess.DEVNULL
        kwargs["stdout"] = open(os.path.join(root, "logs", "backend.out.log"), "ab")
        kwargs["stderr"] = open(os.path.join(root, "logs", "backend.err.log"), "ab")
        kwargs["close_fds"] = True
    proc = subprocess.Popen(cmd, cwd=root, **kwargs)
    print(f"launched uvicorn pid={proc.pid}")

if __name__ == "__main__":
    main()
