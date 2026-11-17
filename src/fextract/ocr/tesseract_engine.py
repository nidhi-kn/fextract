"""Tesseract OCR adapter; requires the local Tesseract executable."""

import os
from pathlib import Path
import shutil
from .base import OCRWord


class TesseractEngine:
    """Run pytesseract and return positioned word records."""

    def run(self, image) -> list[OCRWord]:
        """Recognize words; fail with an actionable message if Tesseract is absent."""
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError(
                "OCR unavailable: install the 'ocr' extra and Tesseract"
            ) from exc
        command = os.getenv("FEXTRACT_TESSERACT_CMD") or shutil.which("tesseract")
        if not command:
            candidates = [
                Path(os.getenv("ProgramFiles", "C:/Program Files"))
                / "Tesseract-OCR/tesseract.exe",
                Path(os.getenv("ProgramFiles(x86)", "C:/Program Files (x86)"))
                / "Tesseract-OCR/tesseract.exe",
            ]
            command = next((str(path) for path in candidates if path.is_file()), None)
        if not command:
            raise RuntimeError(
                "Tesseract executable not found; install Tesseract or set FEXTRACT_TESSERACT_CMD"
            )
        pytesseract.pytesseract.tesseract_cmd = command
        try:
            orientation = pytesseract.image_to_osd(image, output_type=Output.DICT)
            rotate = int(orientation.get("rotate", 0)) % 360
            if rotate:
                image = image.rotate(-rotate, expand=True, fillcolor="white")
        except Exception:
            # OSD can fail on sparse statement pages; OCR still proceeds.
            pass
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        words = []
        for index, text in enumerate(data["text"]):
            if not text.strip():
                continue
            conf = max(0.0, float(data["conf"][index])) / 100
            x, y, w, h = (
                data[key][index] for key in ("left", "top", "width", "height")
            )
            words.append(
                OCRWord(
                    text.strip(), [float(x), float(y), float(x + w), float(y + h)], conf
                )
            )
        return words
