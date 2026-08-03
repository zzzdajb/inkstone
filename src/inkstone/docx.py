from pathlib import Path

import pypandoc


def extract_docx(path: str) -> str:
    """DOCX 文件结构化提取。返回输出目录路径。"""
    path = Path(path).resolve()
    output_dir = path.parent / path.stem
    output_dir.mkdir(exist_ok=True)

    markdown = pypandoc.convert_file(
        str(path),
        to="markdown",
        extra_args=["--extract-media", str(output_dir)],
    )

    md_path = output_dir / f"{path.stem}.md"
    md_path.write_text(markdown, encoding="utf-8")

    return str(output_dir)
