"""Tests for the .docx loader in fenn/agents/rag/loader.py

Place at: tests/unit/agents/test_docx_loader.py
(or merge these cases into tests/unit/agents/test_rag_components.py).
"""

from unittest.mock import patch

import pytest

from fenn.agents.rag.loader import (
    _read_docx,
    _read_file,
    load_documents,
)


def _make_docx(path, paragraphs=("Hello from docx", "second line"), table=None):
    docx = pytest.importorskip("docx")
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    if table:
        t = d.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, val in enumerate(row):
                t.rows[r].cells[c].text = val
    d.save(str(path))
    return path


class TestReadDocx:
    def test_reads_paragraphs(self, tmp_path):
        f = _make_docx(tmp_path / "doc.docx")
        assert _read_docx(f) == "Hello from docx\nsecond line"

    def test_reads_table_cells(self, tmp_path):
        f = _make_docx(
            tmp_path / "t.docx",
            paragraphs=("Prices:",),
            table=[["Item", "Price"], ["Coffee", "3.00"]],
        )
        text = _read_docx(f)
        assert "Item\tPrice" in text
        assert "Coffee\t3.00" in text

    def test_empty_docx_returns_none(self, tmp_path):
        docx = pytest.importorskip("docx")
        d = docx.Document()
        d.save(str(tmp_path / "empty.docx"))
        assert _read_docx(tmp_path / "empty.docx") is None

    def test_read_file_delegates_docx(self, tmp_path):
        f = _make_docx(tmp_path / "d.docx")
        assert _read_file(f) == "Hello from docx\nsecond line"

    def test_load_documents_reads_docx(self, tmp_path):
        f = _make_docx(tmp_path / "d.docx")
        assert load_documents(str(f)) == ["Hello from docx\nsecond line"]

    def test_missing_python_docx_raises_importerror(self, tmp_path):
        f = _make_docx(tmp_path / "d.docx")
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("no docx")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with pytest.raises(ImportError, match="python-docx"):
                _read_docx(f)
