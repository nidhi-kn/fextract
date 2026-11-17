"""Optional lazy-loaded PaddleOCR adapter."""

from .base import OCRWord


class PaddleEngine:
    """Load PaddleOCR only on first use to keep digital-only runs light."""

    def __init__(self) -> None:
        self._engine = None

    def run(self, image) -> list[OCRWord]:
        """Recognize words using PaddleOCR, or report the missing optional package."""
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed; use Tesseract fallback"
                ) from exc
            self._engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        try:
            import numpy as np

            image = np.asarray(image)
        except ImportError:
            pass
        result = self._engine.ocr(image, cls=True) or []
        output = []
        for line in result[0] or []:
            points, (text, confidence) = line
            xs, ys = [point[0] for point in points], [point[1] for point in points]
            output.append(
                OCRWord(text, [min(xs), min(ys), max(xs), max(ys)], float(confidence))
            )
        return output
