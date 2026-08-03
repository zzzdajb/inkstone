import argparse
import sys


def extract(path: str, format: str) -> str:
    """
    输入文件路径和格式，执行结构化提取。
    返回输出目录的路径。
    """
    if format == "html":
        from inkstone.html import extract_html

        return extract_html(path)
    elif format == "pdf":
        from inkstone.pdf import extract_pdf

        return extract_pdf(path)
    elif format == "docx":
        from inkstone.docx import extract_docx

        return extract_docx(path)
    else:
        raise ValueError(f"Unsupported format: {format}")


def cli_main():
    parser = argparse.ArgumentParser(prog="inkstone")
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser("extract", help="Extract structured Markdown from a file")
    extract_parser.add_argument("path", help="Input file path")
    extract_parser.add_argument("--format", required=True, choices=["html", "pdf", "docx"])

    args = parser.parse_args()

    if args.command == "extract":
        output_dir = extract(args.path, format=args.format)
        print(output_dir)
    else:
        parser.print_help()
        sys.exit(1)
