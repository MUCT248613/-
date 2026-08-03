"""Pre-flight backend dependency check for the API import chain.

Prints the names (space-separated) of any required third-party module that is
not importable, and exits 1 when at least one is missing. Used by start.bat to
auto-install missing packages before launching the backend, so the backend
window never dies with a cryptic ModuleNotFoundError crash loop.
"""
import importlib.util
import sys

REQUIRED = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "numpy",
    "scipy",
    "networkx",
    "duckdb",
    "yaml",
]

def main() -> int:
    missing = [m for m in REQUIRED if importlib.util.find_spec(m) is None]
    if missing:
        print(" ".join(missing))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
