import io
import struct
import zipfile

import pytest

from aedrova_site.file_policy import inspect_file


@pytest.mark.parametrize(
    "name,data",
    [
        ("fake.png", b"text"),
        ("bad.txt", b"MZ\0malware"),
        ("app.exe", b"MZprogram"),
        ("bad.jpg", b"\xff\xd8junk\xff\xd9"),
        ("bad.pdf", b"%PDF-1.7 no end"),
        ("page.html", b"<script>bad()</script>"),
        ("bad.docx", b"not zip"),
    ],
)
def test_mismatched_active_and_malformed_files_rejected(name, data):
    with pytest.raises(ValueError):
        inspect_file(name, data)


def test_image_expansion_limit_and_documents_are_bounded():
    png = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 6000, 6000)
    with pytest.raises(ValueError):
        inspect_file("huge.png", png + b"\0" * 8 + b"IEND" + b"\0" * 4)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("word/document.xml", "content")
        archive.writestr("../outside", "bad")
    with pytest.raises(ValueError):
        inspect_file("unsafe.docx", output.getvalue())
    assert inspect_file("brief.md", b"# Approved\nText") == "text/plain"
    assert inspect_file("document.pdf", b"%PDF-1.7\nbody\n%%EOF") == "application/pdf"
