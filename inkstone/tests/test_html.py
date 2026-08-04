import shutil
import tempfile
from pathlib import Path

import pytest

from inkstone.html import extract_html, _preprocess


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _make_html(images: list[tuple[str, str]]) -> str:
    """Build a minimal HTML with embedded base64 images."""
    img_tags = ""
    for mime, b64 in images:
        img_tags += f'<img src="data:image/{mime};base64,{b64}">\n'
    return f"<html><body><p>Test article content.</p>{img_tags}</body></html>"


class TestPreprocess:
    def test_extracts_base64_images(self, tmp_path):
        # 1x1 red PNG pixel
        red_pixel = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "2mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
        )
        html = _make_html([("png", red_pixel)])
        result = _preprocess(html, tmp_path)

        assert (tmp_path / "img_001.png").exists()
        assert (tmp_path / "img_001.png").stat().st_size > 0
        assert "img_001.png" in result
        assert "data:image/" not in result

    def test_handles_multiple_mime_types(self, tmp_path):
        red_pixel = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "2mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
        )
        html = _make_html([("png", red_pixel), ("jpeg", red_pixel)])
        _preprocess(html, tmp_path)

        assert (tmp_path / "img_001.png").exists()
        assert (tmp_path / "img_002.jpg").exists()

    def test_skips_non_base64_images(self, tmp_path):
        html = '<html><body><img src="https://example.com/photo.jpg"></body></html>'
        result = _preprocess(html, tmp_path)

        assert not list(tmp_path.glob("img_*"))
        assert "https://example.com/photo.jpg" in result

    def test_numbering_is_sequential(self, tmp_path):
        red_pixel = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "2mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
        )
        html = _make_html([("png", red_pixel)] * 3)
        _preprocess(html, tmp_path)

        assert (tmp_path / "img_001.png").exists()
        assert (tmp_path / "img_002.png").exists()
        assert (tmp_path / "img_003.png").exists()


class TestExtractHtml:
    def test_end_to_end(self, tmp_path):
        red_pixel = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "2mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
        )
        html = (
            "<html><head><title>Test</title></head>"
            "<body>"
            "<article>"
            "<h1>Article Title</h1>"
            "<p>This is the main content of the article.</p>"
            f'<img src="data:image/png;base64,{red_pixel}">'
            "</article>"
            "</body></html>"
        )
        html_path = tmp_path / "report.html"
        html_path.write_text(html, encoding="utf-8")

        output_dir = extract_html(str(html_path))

        assert Path(output_dir).exists()
        assert Path(output_dir).name == "report"
        assert (Path(output_dir) / "report.md").exists()
        assert (Path(output_dir) / "img_001.png").exists()

    def test_output_dir_same_level_as_input(self, tmp_path):
        html_path = tmp_path / "my_doc.html"
        html_path.write_text("<html><body><p>Content.</p></body></html>", encoding="utf-8")

        output_dir = extract_html(str(html_path))

        assert Path(output_dir).parent == tmp_path
        assert Path(output_dir).name == "my_doc"
