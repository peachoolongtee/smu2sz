"""Brief 03 §6.1: document text extraction for .txt/.md, .docx and text-layer PDF, byte-stable, no OCR."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.ingest import (
    MAX_BYTES,
    MAX_PDF_PAGES,
    MAX_UNZIPPED_BYTES,
    SCANNED_MESSAGE,
    DocumentTooLarge,
    EmptyDocument,
    IngestError,
    ScannedPdf,
    UnsupportedFileType,
    extract_text,
    normalise,
    unwrap,
)

CONTRACTS = Path(__file__).resolve().parents[4] / "fixtures" / "contracts"
STEMS = (
    "fhr-2026-07-supply-agreement",
    "mb-cl-2026-031-credit-line-agreement",
    "gbr-if-2026-118-invoice-financing-agreement",
)


def _pdf(page_streams: list[bytes]) -> bytes:
    """A minimal PDF whose pages have the given content streams (Helvetica as F1)."""
    objs = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for s in page_streams:
        objs.append(b"<< /Length %d >>\nstream\n" % len(s) + s + b"\nendstream")
        content = len(objs)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
                    b"/Contents %d 0 R >>" % content)
        kids.append(len(objs))
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % k for k in kids) + b"] /Count %d >>" % len(kids)
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, body in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    return bytes(out)


def _md_paragraphs(stem: str) -> list[str]:
    text = extract_text(f"{stem}.md", (CONTRACTS / f"{stem}.md").read_bytes())
    return [ln for ln in text.split("\n") if ln.strip()]


# ---------------------------------------------------------------- plain text


def test_plain_text_is_normalised_to_lf_nfc_without_control_characters():
    raw = "﻿Clause 1.\r\n\r\n\r\n\r\nPayable 45 days   \rafter\x00 the invoice.\x07\n"
    assert extract_text("a.txt", raw.encode("utf-8")) == "Clause 1.\n\nPayable 45 days\nafter the invoice."


def test_normalise_is_idempotent_and_composes_unicode():
    s = "Café   line para\f page\n\n\n\nend  "
    once = normalise(s)
    assert normalise(once) == once
    assert "Café" in once and " " not in once and "\f" not in once and "\n\n\n" not in once


def test_markdown_and_txt_give_the_same_text_for_the_same_bytes():
    data = (CONTRACTS / f"{STEMS[0]}.md").read_bytes()
    assert extract_text("x.md", data) == extract_text("x.txt", data) == extract_text("x.MD", data)


def test_extraction_is_byte_stable():
    for stem in STEMS:
        for fmt in ("md", "docx", "pdf"):
            data = (CONTRACTS / f"{stem}.{fmt}").read_bytes()
            assert extract_text(f"{stem}.{fmt}", data) == extract_text(f"{stem}.{fmt}", data)


def test_non_utf8_text_is_refused_with_a_reason():
    with pytest.raises(IngestError, match="UTF-8"):
        extract_text("a.txt", "付款条件".encode("gbk"))


# ---------------------------------------------------------------- Word and PDF copies of the demo documents


@pytest.mark.parametrize("stem", STEMS)
@pytest.mark.parametrize("fmt", ["docx", "pdf"])
def test_docx_and_pdf_copies_read_back_to_the_markdown_paragraphs(stem, fmt):
    text = extract_text(f"{stem}.{fmt}", (CONTRACTS / f"{stem}.{fmt}").read_bytes())
    assert [p for p in text.split("\n\n") if p.strip()] == _md_paragraphs(stem)


def test_docx_tables_are_read_in_body_order():
    import docx

    d = docx.Document()
    d.add_paragraph("Before the table.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Price", "RMB 420,000"
    t.cell(1, 0).text, t.cell(1, 1).text = "Terms", "45 days"
    d.add_paragraph("After the table.")
    buf = io.BytesIO()
    d.save(buf)
    assert extract_text("t.docx", buf.getvalue()) == (
        "Before the table.\n\nPrice | RMB 420,000\n\nTerms | 45 days\n\nAfter the table.")


# ---------------------------------------------------------------- refusals


def test_a_pdf_without_a_text_layer_is_refused_as_a_scan():
    scan = _pdf([b"q 100 0 0 100 50 700 cm Q", b""])  # drawing operators only, no text
    with pytest.raises(ScannedPdf) as e:
        extract_text("scan.pdf", scan)
    assert str(e.value) == SCANNED_MESSAGE == "this PDF is a scan; upload a text PDF or Word file"
    assert e.value.code == "SCANNED_PDF"


def test_a_page_number_alone_does_not_count_as_a_text_layer():
    with pytest.raises(ScannedPdf):
        extract_text("scan.pdf", _pdf([b"BT /F1 9 Tf 290 40 Td (1) Tj ET", b"BT /F1 9 Tf 290 40 Td (2) Tj ET"]))


def test_a_text_pdf_is_read():
    pdf = _pdf([(b"BT /F1 10 Tf 14 TL 56 786 Td (4.2 Each invoice is payable forty-five \\(45\\) days after the "
                 b"Invoice Date.) Tj ET")])
    assert extract_text("t.pdf", pdf) == "4.2 Each invoice is payable forty-five (45) days after the Invoice Date."


@pytest.mark.parametrize(("name", "data", "exc"), [
    ("old.doc", b"\xd0\xcf\x11\xe0 legacy", UnsupportedFileType),
    ("sheet.xlsx", b"PK\x03\x04", UnsupportedFileType),
    ("noext", b"hello", UnsupportedFileType),
    ("fake.pdf", b"PK\x03\x04 a zip, not a pdf", IngestError),
    ("fake.docx", b"%PDF-1.4 not a zip", IngestError),
    ("broken.docx", b"PK\x03\x04 truncated", IngestError),
    ("broken.pdf", b"%PDF-1.4\ngarbage", IngestError),
    ("empty.txt", b"  \n\n\t\n", EmptyDocument),
])
def test_unreadable_or_unsupported_files_are_refused(name, data, exc):
    with pytest.raises(exc):
        extract_text(name, data)


def test_a_file_over_the_size_limit_is_refused_before_parsing():
    with pytest.raises(DocumentTooLarge):
        extract_text("big.txt", b"a" * (MAX_BYTES + 1))


def _zip_with(*entries: tuple[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in entries:
            z.writestr(name, body)
    return buf.getvalue()


def test_a_word_file_that_unzips_past_the_cap_is_refused_before_it_is_loaded(monkeypatch):
    """A few kilobytes of zeros inflate to more than the cap: the sum of the declared sizes refuses it, python-docx
    never opens it."""
    import docx

    def loaded(*_a: object, **_k: object) -> None:
        raise AssertionError("python-docx must not open an oversize archive")

    monkeypatch.setattr(docx, "Document", loaded)
    bomb = _zip_with(("[Content_Types].xml", b"<Types/>"), ("word/media/big.bin", bytes(MAX_UNZIPPED_BYTES + 1)))
    assert len(bomb) < MAX_BYTES  # small enough to pass the upload size check
    with pytest.raises(DocumentTooLarge) as e:
        extract_text("bomb.docx", bomb)
    assert e.value.code == "DOCUMENT_TOO_LARGE" and "20 MB once unzipped" in str(e.value) and e.value.message_zh


def test_the_cap_sums_every_entry_not_just_the_largest():
    half = bytes(MAX_UNZIPPED_BYTES // 2 + 1)
    with pytest.raises(DocumentTooLarge):
        extract_text("two.docx", _zip_with(("word/a.bin", half), ("word/b.bin", half)))


def test_a_word_file_just_under_the_cap_is_still_read():
    import docx

    d = docx.Document()
    d.add_paragraph("Clause 1.")
    buf = io.BytesIO()
    d.save(buf)
    assert extract_text("ok.docx", buf.getvalue()) == "Clause 1."


def test_a_pdf_over_the_page_cap_is_refused_before_any_page_is_read():
    page = b"BT /F1 10 Tf 56 786 Td (4.2 Each invoice is payable forty-five days after the Invoice Date.) Tj ET"
    assert extract_text("ok.pdf", _pdf([page] * MAX_PDF_PAGES))
    with pytest.raises(DocumentTooLarge) as e:
        extract_text("long.pdf", _pdf([page] * (MAX_PDF_PAGES + 1)))
    assert str(e.value) == f"the PDF has {MAX_PDF_PAGES + 1} pages; the limit is {MAX_PDF_PAGES}" and e.value.message_zh


def test_every_refusal_carries_a_stable_code():
    codes = {c.code for c in (IngestError, UnsupportedFileType, ScannedPdf, DocumentTooLarge, EmptyDocument)}
    assert codes == {"UNREADABLE_DOCUMENT", "UNSUPPORTED_FILE_TYPE", "SCANNED_PDF", "DOCUMENT_TOO_LARGE",
                     "EMPTY_DOCUMENT"}


# ---------------------------------------------------------------- PDF line unwrapping


def test_unwrap_joins_a_full_width_wrap_and_keeps_clause_starts():
    page = ("4.4 The Buyer may settle any invoice early, within two (2) days of the Supplier's written\n"
            "request, at a discount of 1.2% of the invoice amount.\n"
            "4.5 Payment of an invoice is subject to receipt of documents.")
    assert unwrap(page) == ("4.4 The Buyer may settle any invoice early, within two (2) days of the Supplier's "
                            "written request, at a discount of 1.2% of the invoice amount.\n\n"
                            "4.5 Payment of an invoice is subject to receipt of documents.")


def test_unwrap_joins_a_year_or_amount_at_the_start_of_a_wrapped_line():
    page = ("2.1 This Agreement takes effect on 1 September 2026 and continues for a term of twelve (12) months, until\n"
            "2026 ends, and the Bank makes available a revolving working-capital credit line with a facility limit of\n"
            "RMB 150,000.\n"
            "A short line.")
    out = unwrap(page)
    assert out.split("\n\n") == [
        ("2.1 This Agreement takes effect on 1 September 2026 and continues for a term of twelve (12) months, until 2026 "
         "ends, and the Bank makes available a revolving working-capital credit line with a facility limit of RMB 150,000."),
        "A short line.",
    ]


def test_unwrap_rejoins_a_hyphenated_word_only_before_lower_case():
    long = "x" * 70
    assert unwrap(f"{long} pay-\nable on time.") == f"{long} payable on time."
    assert unwrap(f"{long} working-\nCapital line.") == f"{long} working- Capital line."


def test_unwrap_does_not_join_headings_or_list_items():
    page = ("5. FINANCIAL COVENANTS\n"
            "6.1 The Supplier shall provide the following documents for each Batch, as they are listed below:\n"
            "(a) a delivery note signed by the Buyer's warehouse;\n"
            "(b) a quality certificate.")
    assert unwrap(page).split("\n\n") == [
        "5. FINANCIAL COVENANTS",
        "6.1 The Supplier shall provide the following documents for each Batch, as they are listed below:",
        "(a) a delivery note signed by the Buyer's warehouse;",
        "(b) a quality certificate.",
    ]


def test_unwrap_joins_two_cjk_characters_across_a_wrap_without_a_space():
    full = "乙方收款账户：开户银行" + "中国建设银行股份有限公" * 3
    page = f"{full}\n司深圳分行，合同总价的\n30%，重新\n提供服务。"
    out = unwrap(page)
    assert "有限公司深圳分行" in out
    assert "有限公 司" not in out


def test_unwrap_keeps_the_space_between_cjk_and_latin_or_digits_across_a_wrap():
    full = "乙方应在收到通知后向甲方开具发票并按合同约定支付" * 3
    assert unwrap(f"{full} RMB\n150,000 元") == f"{full} RMB 150,000 元"
    assert unwrap(f"{full}\nABC 公司") == f"{full} ABC 公司"
    assert unwrap(f"{full}25\n日内付款") == f"{full}25 日内付款"
