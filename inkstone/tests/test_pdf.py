import shutil
from pathlib import Path

import pytest

from inkstone.detect import is_scanned_pdf
from inkstone.pdf import extract_pdf


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestDetect:
    def test_text_pdf_detected(self):
        pdf_path = FIXTURE_DIR / "sample_text_report.pdf"
        if not pdf_path.exists():
            pytest.skip("sample_text_report.pdf fixture not found")
        assert is_scanned_pdf(str(pdf_path)) is False

    def test_scanned_pdf_detected(self):
        pdf_path = FIXTURE_DIR / "Apple2026Q3财报电话会议.pdf"
        if not pdf_path.exists():
            pytest.skip("Apple2026Q3财报电话会议.pdf fixture not found")
        assert is_scanned_pdf(str(pdf_path)) is True


class TestExtractPdf:
    def test_text_pdf_end_to_end(self, tmp_path):
        src = FIXTURE_DIR / "sample_text_report.pdf"
        if not src.exists():
            pytest.skip("sample_text_report.pdf fixture not found")

        pdf_path = tmp_path / "sample_text_report.pdf"
        shutil.copy(src, pdf_path)

        output_dir = extract_pdf(str(pdf_path))

        assert Path(output_dir).exists()
        assert Path(output_dir).name == "sample_text_report"
        assert Path(output_dir).parent == tmp_path

        md_path = Path(output_dir) / "sample_text_report.md"
        assert md_path.exists()

        content = md_path.read_text(encoding="utf-8")
        assert len(content) > 0
        assert "Revenue" in content

    def test_output_dir_same_level_as_input(self, tmp_path):
        src = FIXTURE_DIR / "sample_text_report.pdf"
        if not src.exists():
            pytest.skip("sample_text_report.pdf fixture not found")

        pdf_path = tmp_path / "my_report.pdf"
        shutil.copy(src, pdf_path)

        output_dir = extract_pdf(str(pdf_path))

        assert Path(output_dir).parent == tmp_path
        assert Path(output_dir).name == "my_report"

    def test_scanned_pdf_without_token_raises(self, tmp_path, monkeypatch):
        src = FIXTURE_DIR / "Apple2026Q3财报电话会议.pdf"
        if not src.exists():
            pytest.skip("Apple2026Q3财报电话会议.pdf fixture not found")

        pdf_path = tmp_path / "scanned.pdf"
        shutil.copy(src, pdf_path)

        # Point dotenv to a nonexistent .env so token is always missing
        import dotenv
        monkeypatch.setattr(dotenv, "dotenv_values", lambda _: {})

        with pytest.raises(RuntimeError, match="PADDLE_OCR_TOKEN"):
            extract_pdf(str(pdf_path))
