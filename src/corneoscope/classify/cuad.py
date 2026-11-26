"""CUAD v1: 510 contracts with clause spans labeled by lawyers (CC BY 4.0).

https://www.atticusprojectai.org/cuad
"""

import hashlib
import http.client
import json
import re
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from corneoscope.classify.labels import LABELS
from corneoscope.classify.sentences import sentence_bounds
from corneoscope.clauses.splitter import PARAGRAPH_BREAK

URL = "https://zenodo.org/records/4595826/files/CUAD_v1.zip"
SHA256 = "88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e"
JSON_MEMBER = "CUAD_v1/CUAD_v1.json"
DATA_DIR = Path("data/cuad")
QUESTION_LABEL = re.compile(r'related to "(?P<label>[^"]+)"')

TRAIN_SHARE = 70
VALIDATION_SHARE = 15


@dataclass(frozen=True)
class Example:
    contract: str
    text: str
    labels: frozenset[str]
    # Each sentence carries only the labels whose spans touch it, which is finer
    # than the paragraph's labels.
    sentences: tuple[tuple[str, frozenset[str]], ...] = ()


def labels_between(
    spans: list[tuple[int, int, str]], begin: int, end: int
) -> frozenset:
    return frozenset(label for low, high, label in spans if low < end and high > begin)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, path: Path, attempts: int = 5) -> None:
    """Zenodo often drops the connection part way, so each retry resumes."""
    partial = path.with_name(path.name + ".part")
    error: Exception | None = None
    for _ in range(attempts):
        done = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(url, headers={"Range": f"bytes={done}-"})
        try:
            # A server that ignores Range sends the whole file again (200, not 206).
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                partial.open("ab" if response.status == 206 else "wb") as out,
            ):
                shutil.copyfileobj(response, out)
            partial.replace(path)
            return
        except (OSError, http.client.HTTPException) as exc:
            error = exc
    raise RuntimeError(f"Download of {url} failed after {attempts} attempts") from error


def download(directory: Path = DATA_DIR) -> Path:
    """Return the path of CUAD_v1.json, downloading and checking it when missing."""
    target = directory / "CUAD_v1.json"
    if target.exists():
        return target
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / "CUAD_v1.zip"
    if not archive.exists() or sha256(archive) != SHA256:
        fetch(URL, archive)
    if sha256(archive) != SHA256:
        archive.unlink()
        raise RuntimeError(f"{archive} does not match the published checksum")
    with (
        zipfile.ZipFile(archive) as bundle,
        bundle.open(JSON_MEMBER) as source,
        target.open("wb") as out,
    ):
        shutil.copyfileobj(source, out)
    return target


def contract_examples(title: str, context: str, qas: list[dict]) -> list[Example]:
    """One example per paragraph, labeled with every span that overlaps it."""
    spans = []
    for qa in qas:
        label = QUESTION_LABEL.search(qa["question"])["label"]
        if label in LABELS:
            for answer in qa["answers"]:
                start = answer["answer_start"]
                spans.append((start, start + len(answer["text"]), label))

    edges = [0]
    for match in PARAGRAPH_BREAK.finditer(context):
        edges += [match.start(), match.end()]
    edges.append(len(context))
    examples = []
    for begin, end in zip(edges[::2], edges[1::2], strict=True):
        raw = context[begin:end]
        text = " ".join(raw.split())
        if text:
            sentences = tuple(
                (
                    " ".join(raw[low:high].split()),
                    labels_between(spans, begin + low, begin + high),
                )
                for low, high in sentence_bounds(raw)
            )
            examples.append(
                Example(title, text, labels_between(spans, begin, end), sentences)
            )
    return examples


def load_examples(path: Path) -> list[Example]:
    data = json.loads(path.read_text(encoding="utf-8"))["data"]
    return [
        example
        for contract in data
        for paragraph in contract["paragraphs"]
        for example in contract_examples(
            contract["title"], paragraph["context"], paragraph["qas"]
        )
    ]


def split_of(contract: str) -> str:
    """Split by contract, so no contract has paragraphs on both sides.

    A hash of the title, not a random draw, keeps the split the same on every
    machine and when contracts are added.
    """
    bucket = int(hashlib.sha256(contract.encode()).hexdigest(), 16) % 100
    if bucket < TRAIN_SHARE:
        return "train"
    if bucket < TRAIN_SHARE + VALIDATION_SHARE:
        return "validation"
    return "test"


def split(examples: list[Example]) -> dict[str, list[Example]]:
    parts: dict[str, list[Example]] = {"train": [], "validation": [], "test": []}
    for example in examples:
        parts[split_of(example.contract)].append(example)
    return parts
