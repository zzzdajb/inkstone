import shutil
from pathlib import Path

import pytest

from inkstone.docx import extract_docx


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_docx(tmp_path):
    """Copy the fixture DOCX to a temp dir so tests don't pollute fixtures/."""
    src = FIXTURE_DIR / "sample.docx"
    dst = tmp_path / "sample.docx"
    shutil.copy2(src, dst)
    return dst


class TestExtractDocx:
    def test_end_to_end(self, sample_docx):
        output_dir = extract_docx(str(sample_docx))

        output = Path(output_dir)
        assert output.exists()
        assert output.name == "sample"

        md_path = output / "sample.md"
        assert md_path.exists()

        md = md_path.read_text(encoding="utf-8")
        assert "Test Report" in md
        assert "Section Two" in md
        assert "GDP" in md
        assert "18.5" in md

    def test_output_dir_same_level_as_input(self, sample_docx):
        output_dir = extract_docx(str(sample_docx))

        assert Path(output_dir).parent == sample_docx.parent
        assert Path(output_dir).name == "sample"

    def test_preserves_heading_levels(self, sample_docx):
        output_dir = extract_docx(str(sample_docx))
        md = (Path(output_dir) / "sample.md").read_text(encoding="utf-8")

        assert "# Test Report" in md
        assert "## Section Two" in md

    def test_overwrite_existing_dir(self, sample_docx):
        output_dir = Path(extract_docx(str(sample_docx)))
        old_content = (output_dir / "sample.md").read_text(encoding="utf-8")

        output_dir2 = Path(extract_docx(str(sample_docx)))
        new_content = (output_dir2 / "sample.md").read_text(encoding="utf-8")

        assert output_dir == output_dir2
        assert old_content == new_content
