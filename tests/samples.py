def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    """Build a small synthetic PDF; each string is one page, lines split on \\n."""
    page_count = len(pages)
    page_ids = [4 + 2 * index for index in range(page_count)]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{pid} 0 R".encode() for pid in page_ids)
        + f"] /Count {page_count} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for page_id, text in zip(page_ids, pages, strict=True):
        lines = [f"({escape(line)}) Tj T*" for line in text.splitlines()]
        stream = (
            "BT /F1 12 Tf 16 TL 72 720 Td " + " ".join(lines) + " ET" if lines else ""
        ).encode()
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>".encode()
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.7\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_start = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        output += f"{offset:010d} 00000 n \n".encode()
    output += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode()
    return bytes(output)


SCHEMA = (
    '{"fields": {"invoice_number": {"type": "string", "required": true},'
    ' "total_amount": {"type": "decimal"}}}'
)


def make_cuad(contracts: dict[str, list[tuple[str, list[str]]]]) -> dict:
    """Build CUAD-format data; each contract is a list of (paragraph, labels)."""
    data = []
    for title, paragraphs in contracts.items():
        context = "\n\n".join(text for text, _ in paragraphs)
        answers: dict[str, list[dict]] = {}
        offset = 0
        for text, labels in paragraphs:
            for label in labels:
                answers.setdefault(label, []).append(
                    {"text": text, "answer_start": offset}
                )
            offset += len(text) + 2
        qas = [
            {
                "id": f"{title}__{label}",
                "question": f"Highlight the parts (if any) of this contract related "
                f'to "{label}" that should be reviewed by a lawyer.',
                "answers": found,
                "is_impossible": not found,
            }
            for label, found in answers.items()
        ]
        data.append({"title": title, "paragraphs": [{"context": context, "qas": qas}]})
    return {"version": "test", "data": data}
