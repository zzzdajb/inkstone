from pathlib import Path


def extract_pdf(path: str) -> str:
    """PDF extraction. Auto-detects scanned vs text PDF internally. Returns output directory path."""
    path = Path(path).resolve()
    stem = path.stem
    output_dir = path.parent / stem
    output_dir.mkdir(exist_ok=True)

    from inkstone.detect import is_scanned_pdf

    if is_scanned_pdf(str(path)):
        from inkstone.pdf_ocr import extract_pdf_ocr

        extract_pdf_ocr(str(path), output_dir, stem)
        return str(output_dir)

    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling_core.types.doc import ImageRefMode

    opts = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=True,
        generate_picture_images=True,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=opts,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )

    result = converter.convert(str(path))

    md_path = output_dir / f"{stem}.md"
    result.document.save_as_markdown(
        md_path,
        artifacts_dir=Path("images"),
        image_mode=ImageRefMode.REFERENCED,
    )

    return str(output_dir)
