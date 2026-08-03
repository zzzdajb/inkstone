#!/usr/bin/env python3
"""Inkstone SKILL script entry point."""
import sys

from inkstone.core import extract

if len(sys.argv) < 2 or len(sys.argv) > 3:
    print("Usage: python extract.py <file_path> [format]")
    print("Format is inferred from extension if omitted. Supported: html, pdf, docx")
    sys.exit(1)

fmt = sys.argv[2] if len(sys.argv) == 3 else None
output_dir = extract(sys.argv[1], format=fmt)
print(output_dir)
