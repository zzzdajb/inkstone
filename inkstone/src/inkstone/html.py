import base64
import re
from pathlib import Path

from bs4 import BeautifulSoup
import trafilatura


def extract_html(path: str) -> str:
    """HTML 文件结构化提取。返回输出目录路径。"""
    path = Path(path).resolve()
    output_dir = path.parent / path.stem
    output_dir.mkdir(exist_ok=True)

    html_content = path.read_text(encoding="utf-8")

    slim_html = _preprocess(html_content, output_dir)

    markdown = trafilatura.extract(
        slim_html,
        include_images=True,
        include_tables=True,
        include_links=True,
        favor_recall=True,
        output_format="markdown",
    )

    if markdown is None:
        markdown = ""

    md_path = output_dir / f"{path.stem}.md"
    md_path.write_text(markdown, encoding="utf-8")

    return str(output_dir)


def _preprocess(html: str, output_dir: Path) -> str:
    """提取 base64 图片并替换为本地路径，返回瘦身后的 HTML。"""
    soup = BeautifulSoup(html, "html.parser")
    count = 0

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src.startswith("data:image/"):
            continue

        match = re.match(r"data:image/([^;]+);base64,(.*)", src, re.DOTALL)
        if not match:
            continue

        count += 1
        mime_subtype = match.group(1)
        b64_data = match.group(2).strip()

        ext_map = {
            "png": "png",
            "jpeg": "jpg",
            "jpg": "jpg",
            "gif": "gif",
            "webp": "webp",
            "svg+xml": "svg",
            "bmp": "bmp",
        }
        ext = ext_map.get(mime_subtype, "png")

        filename = f"img_{count:03d}.{ext}"
        image_path = output_dir / filename
        image_data = base64.b64decode(b64_data)
        image_path.write_bytes(image_data)

        img["src"] = filename

    return str(soup)
