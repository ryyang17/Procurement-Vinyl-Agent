from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader


@dataclass
class ExtractedImage:
    page_index: int
    image_index: int
    name: str
    path: str


@dataclass
class ExtractedPage:
    page_index: int
    text: str
    images: list[ExtractedImage] = field(default_factory=list)


@dataclass
class Exercise:
    id: str
    source_page: int
    prompt: str
    image_paths: list[str] = field(default_factory=list)
    detected_type: str = "unknown"
    interactive_model: dict[str, Any] = field(default_factory=dict)


class PDFExtractor:
    """Stap 1: PDF -> ruwe tekst en afbeeldingen per pagina."""

    def extract(self, pdf_path: Path, image_output_dir: Path) -> list[ExtractedPage]:
        reader = PdfReader(str(pdf_path))
        image_output_dir.mkdir(parents=True, exist_ok=True)

        pages: list[ExtractedPage] = []
        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            extracted_images: list[ExtractedImage] = []

            for img_idx, image_file in enumerate(getattr(page, "images", []), start=1):
                file_name = getattr(image_file, "name", f"page_{page_idx}_img_{img_idx}.bin")
                image_path = image_output_dir / file_name
                image_path.write_bytes(image_file.data)
                extracted_images.append(
                    ExtractedImage(
                        page_index=page_idx,
                        image_index=img_idx,
                        name=file_name,
                        path=str(image_path),
                    )
                )

            pages.append(
                ExtractedPage(page_index=page_idx, text=text, images=extracted_images)
            )
        return pages


class ExerciseSplitter:
    """Stap 2: Tekst -> losse oefeningen."""

    _split_pattern = re.compile(
        r"(?=(?:^|\n)\s*(?:Oefening\s*\d+|Vraag\s*\d+|\d+[\.)]|[A-Z][\.)])\s+)",
        flags=re.IGNORECASE,
    )

    def split(self, extracted_pages: list[ExtractedPage]) -> list[Exercise]:
        exercises: list[Exercise] = []

        for page in extracted_pages:
            chunks = [chunk.strip() for chunk in self._split_pattern.split(page.text) if chunk.strip()]
            if not chunks:
                continue

            if len(chunks) == 1:
                exercises.append(
                    Exercise(
                        id=f"p{page.page_index}-e1",
                        source_page=page.page_index,
                        prompt=chunks[0],
                        image_paths=[img.path for img in page.images],
                    )
                )
                continue

            for i, chunk in enumerate(chunks, start=1):
                exercises.append(
                    Exercise(
                        id=f"p{page.page_index}-e{i}",
                        source_page=page.page_index,
                        prompt=chunk,
                        image_paths=[img.path for img in page.images],
                    )
                )

        return exercises


class ExerciseClassifier:
    """Stap 3: Oefening -> type detectie (regelgebaseerde minimale PoT)."""

    def classify(self, exercises: list[Exercise]) -> list[Exercise]:
        for ex in exercises:
            text = ex.prompt.lower()
            if self._is_multiple_choice(text):
                ex.detected_type = "multiple_choice"
            elif self._is_math(text):
                ex.detected_type = "math"
            elif self._is_language(text):
                ex.detected_type = "language"
            else:
                ex.detected_type = "open_question"
        return exercises

    @staticmethod
    def _is_multiple_choice(text: str) -> bool:
        return bool(re.search(r"\b(a|b|c|d)[\.)]\b", text)) or "meerkeuze" in text

    @staticmethod
    def _is_math(text: str) -> bool:
        return bool(re.search(r"\d+\s*[+\-x*/]\s*\d+", text)) or any(
            kw in text for kw in ["bereken", "som", "plus", "min", "tafels"]
        )

    @staticmethod
    def _is_language(text: str) -> bool:
        return any(
            kw in text
            for kw in ["lees", "schrijf", "woord", "zin", "spelling", "taal"]
        )


class InteractiveTransformer:
    """Stap 4: Oefening -> interactief model voor UI."""

    def transform(self, exercises: list[Exercise]) -> list[Exercise]:
        for ex in exercises:
            base = {
                "exerciseId": ex.id,
                "prompt": ex.prompt,
                "assets": ex.image_paths,
                "sourcePage": ex.source_page,
            }

            if ex.detected_type == "multiple_choice":
                ex.interactive_model = {
                    **base,
                    "component": "MultipleChoiceCard",
                    "fields": ["choiceA", "choiceB", "choiceC", "choiceD"],
                }
            elif ex.detected_type == "math":
                ex.interactive_model = {
                    **base,
                    "component": "MathInputCard",
                    "fields": ["answer"],
                    "validation": {"type": "numeric"},
                }
            elif ex.detected_type == "language":
                ex.interactive_model = {
                    **base,
                    "component": "TextInputCard",
                    "fields": ["answer"],
                    "validation": {"minLength": 1},
                }
            else:
                ex.interactive_model = {
                    **base,
                    "component": "OpenQuestionCard",
                    "fields": ["answer"],
                }
        return exercises


class ExercisePipeline:
    def __init__(self) -> None:
        self.extractor = PDFExtractor()
        self.splitter = ExerciseSplitter()
        self.classifier = ExerciseClassifier()
        self.transformer = InteractiveTransformer()

    def run(self, pdf_path: Path, output_json_path: Path, image_output_dir: Path) -> dict[str, Any]:
        pages = self.extractor.extract(pdf_path=pdf_path, image_output_dir=image_output_dir)
        exercises = self.splitter.split(pages)
        exercises = self.classifier.classify(exercises)
        exercises = self.transformer.transform(exercises)

        result = {
            "source_pdf": str(pdf_path),
            "page_count": len(pages),
            "exercise_count": len(exercises),
            "exercises": [asdict(ex) for ex in exercises],
        }

        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal proof-of-technology: PDF -> oefeningen -> interactieve JSON"
    )
    parser.add_argument("--pdf", required=True, help="Pad naar input PDF")
    parser.add_argument(
        "--out",
        default="outputs/exercises.json",
        help="Pad naar output JSON bestand",
    )
    parser.add_argument(
        "--images",
        default="outputs/images",
        help="Map waar geëxtraheerde afbeeldingen worden opgeslagen",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    pdf_path = Path(args.pdf)
    out_path = Path(args.out)
    image_dir = Path(args.images)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF niet gevonden: {pdf_path}")

    pipeline = ExercisePipeline()
    result = pipeline.run(pdf_path=pdf_path, output_json_path=out_path, image_output_dir=image_dir)

    print(
        f"Klaar. Pagina's: {result['page_count']}, Oefeningen: {result['exercise_count']}, Output: {out_path}"
    )


if __name__ == "__main__":
    main()
