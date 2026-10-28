"""Local Docling conversion; fixed formats/options, offline models and bounded process lifetime."""

from __future__ import annotations

import io
import multiprocessing
import os
import threading

from .settings import DOCLING_ARTIFACTS

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_CHUNKS = 2000
PDF_TIMEOUT = 120
_slot = threading.BoundedSemaphore(1)


class PDFUnavailable(RuntimeError):
    pass


class PDFBusy(PDFUnavailable):
    pass


def normalize_document(document):
    """Keep item/page/bbox provenance, including explicit multi-page item ranges."""
    chunks = []
    for item, _ in document.iterate_items():
        label = getattr(item, "label", None)
        label = getattr(label, "value", str(label))
        if label in {"page_header", "page_footer", "picture"}:
            continue
        if label == "table":
            text = item.export_to_markdown(doc=document)
        else:
            text = getattr(item, "text", "")
        if not text.strip():
            continue
        provenance = getattr(item, "prov", [])
        if not provenance:
            raise ValueError("PDF item has no page provenance")
        pages = sorted({p.page_no for p in provenance})
        for page in pages:
            if not 1 <= page <= MAX_PDF_PAGES or page not in document.pages:
                raise ValueError("PDF exceeds the page limit")
        for page in pages[:1]:
            for offset in range(0, len(text), 1200):
                chunks.append(
                    {
                        "page": page,
                        "kind": label,
                        "text": text[offset : offset + 1200],
                        "item_ref": item.self_ref,
                        "offset": offset,
                        "pages": pages,
                        "bboxes": [
                            {"page": p.page_no, **p.bbox.model_dump(mode="json")}
                            for p in provenance
                        ],
                        "multi_page_item": len(pages) > 1,
                    }
                )
                if len(chunks) > MAX_CHUNKS:
                    raise ValueError("PDF exceeds the text/chunk limit")
    if not chunks:
        raise ValueError("No readable PDF text; OCR is disabled for this milestone")
    return {
        "chunks": chunks,
        "page_count": len(document.pages),
        "table_count": len(document.tables),
        "parser": "docling-standard",
        "ocr": False,
    }


def convert_pdf_bytes(content, artifacts=DOCLING_ARTIFACTS):
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import DocumentStream, InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    if not artifacts.is_dir():
        raise PDFUnavailable(
            "Docling model assets are missing; run the documented model-prefetch command"
        )
    options = PdfPipelineOptions(
        artifacts_path=artifacts,
        do_ocr=False,
        do_table_structure=True,
        enable_remote_services=False,
        allow_external_plugins=False,
        document_timeout=100,
        queue_max_size=1,
        accelerator_options=AcceleratorOptions(device="cpu", num_threads=2),
    )
    options.table_structure_options.mode = TableFormerMode.FAST
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
    )
    result = converter.convert(
        DocumentStream(name="source.pdf", stream=io.BytesIO(content)),
        max_num_pages=MAX_PDF_PAGES,
        max_file_size=MAX_PDF_BYTES,
    )
    if getattr(result.status, "value", result.status) != "success":
        raise ValueError("PDF conversion did not complete successfully")
    from importlib.metadata import version

    return {
        **normalize_document(result.document),
        "parser_version": version("docling"),
        "core_version": version("docling-core"),
        "table_mode": "fast",
        "device": "cpu",
    }


def _pdf_worker(connection, content, artifacts):
    # Conversion never silently downloads models or enables remote inference.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    parent = multiprocessing.parent_process()
    if parent is not None:

        def watch_parent():
            while parent.is_alive():
                import time

                time.sleep(0.1)
            os._exit(75)

        threading.Thread(target=watch_parent, daemon=True).start()
    try:
        from pathlib import Path

        result = convert_pdf_bytes(content, Path(artifacts))
        connection.send({"result": result})
    except ImportError:
        connection.send(
            {"unavailable": "Install PDF support: uv sync --extra dev --extra documents"}
        )
    except (PDFUnavailable, OSError):
        connection.send(
            {
                "unavailable": "Docling model assets are unavailable. Prefetch layout and tableformer models."
            }
        )
    except Exception as exc:
        connection.send({"error": f"PDF conversion rejected the input ({type(exc).__name__})"})
    finally:
        connection.close()


def parse_pdf(content, *, timeout=PDF_TIMEOUT):
    if not content.startswith(b"%PDF-") or len(content) > MAX_PDF_BYTES:
        raise ValueError("Expected a PDF of at most 10 MiB")
    if not _slot.acquire(blocking=False):
        raise PDFBusy("A PDF is already being converted; retry after it finishes")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_pdf_worker, args=(sender, content, str(DOCLING_ARTIFACTS)), daemon=True
    )
    try:
        process.start()
        sender.close()
        if not receiver.poll(timeout):
            raise PDFUnavailable("PDF conversion timed out; reduce the document size")
        try:
            message = receiver.recv()
        except EOFError as exc:
            raise PDFUnavailable(
                "PDF worker stopped; check local resources and Docling installation"
            ) from exc
        if "unavailable" in message:
            raise PDFUnavailable(message["unavailable"])
        if "error" in message:
            raise ValueError(message["error"])
        return message["result"]
    finally:
        sender.close()
        receiver.close()
        if process.pid is not None:
            process.join(timeout=0.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=3)
            process.close()
        _slot.release()
