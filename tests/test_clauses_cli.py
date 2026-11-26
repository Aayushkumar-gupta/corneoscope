from samples import make_pdf

from corneoscope.clauses.__main__ import main


def test_prints_each_clause_with_its_page(tmp_path, capsys):
    pdf = tmp_path / "contract.pdf"
    pdf.write_bytes(make_pdf(["1. Term. Two years.\n2. Fees. Pay", "on time.", ""]))

    assert main([str(pdf)]) == 0

    out = capsys.readouterr().out
    assert "[c1] 1 Term (page 1)" in out
    assert "[c2] 2 Fees (pages 1-2)" in out
    assert "2. Fees. Pay on time." in out
    assert "review: Page 3 has no text layer" in out
    assert out.strip().endswith("2 clauses from 3 pages")


def test_reports_a_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "missing.pdf")]) == 1

    assert "cannot read" in capsys.readouterr().err


def test_reports_an_unreadable_pdf(tmp_path, capsys):
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"%PDF-1.7\nnot a real pdf")

    assert main([str(pdf)]) == 1

    assert "could not be read" in capsys.readouterr().err
