"""Image cleanup helpers for scanned document OCR."""

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


def preprocess(image: Image.Image) -> Image.Image:
    """Convert to grayscale, suppress speckle, and improve local contrast."""
    grayscale = ImageOps.autocontrast(ImageOps.grayscale(image))
    grayscale = grayscale.filter(ImageFilter.MedianFilter(size=3))
    # Pillow-only adaptive threshold: compare against a broad local background
    # estimate. This keeps preprocessing available without a native CV runtime.
    background = grayscale.filter(ImageFilter.BoxBlur(max(8, min(image.size) // 80)))
    local_delta = ImageChops.subtract(grayscale, background, offset=128)
    thresholded = local_delta.point(lambda pixel: 255 if pixel > 120 else 0)
    contrast = ImageEnhance.Contrast(grayscale).enhance(1.5)
    # Keep grayscale detail when thresholding would erase faint scan strokes.
    return Image.blend(contrast, thresholded, 0.35)
