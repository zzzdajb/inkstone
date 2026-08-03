#!/usr/bin/env python3
"""Inkstone SKILL script entry point."""
import sys

from inkstone.core import extract

if len(sys.argv) != 3:
    print("Usage: python extract.py <file_path> <format>")
    print("Formats: html, pdf, docx")
    sys.exit(1)

output_dir = extract(sys.argv[1], format=sys.argv[2])
print(output_dir)
