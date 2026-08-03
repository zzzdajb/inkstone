#!/usr/bin/env python3
"""Inkstone SKILL script entry point. Auto-installs dependencies on first run."""
import shutil
import subprocess
import sys


def _ensure_installed():
    try:
        import inkstone  # noqa: F401
        return
    except ImportError:
        pass

    fmt = sys.argv[2] if len(sys.argv) > 2 else "html"
    pkg = "inkstone[pdf]" if fmt == "pdf" else "inkstone"

    installer = shutil.which("uv")
    if installer:
        cmd = [installer, "pip", "install", pkg]
    else:
        cmd = [sys.executable, "-m", "pip", "install", pkg]

    print(f"Inkstone not found, installing: {' '.join(cmd)}")
    subprocess.check_call(cmd)


if len(sys.argv) != 3:
    print("Usage: python extract.py <file_path> <format>")
    print("Formats: html, pdf, docx")
    sys.exit(1)

_ensure_installed()

from inkstone.core import extract  # noqa: E402

output_dir = extract(sys.argv[1], format=sys.argv[2])
print(output_dir)
