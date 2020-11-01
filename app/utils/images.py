from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from sanic.log import logger

from .. import settings
from ..types import Dimensions, Offset, Point
from .text import encode

if TYPE_CHECKING:
    from ..models import Template


def preview(
    template: Template, lines: List[str], style: str = settings.DEFAULT_STYLE
) -> Tuple[bytes, str]:
    image = render_image(template, style, lines, settings.PREVIEW_SIZE, pad=False)
    stream = io.BytesIO()
    image.save(stream, format="JPEG", quality=50)
    return stream.getvalue(), "image/jpeg"


def save(
    template: Template,
    lines: List[str],
    ext: str = settings.DEFAULT_EXT,
    style: str = settings.DEFAULT_STYLE,
    size: Dimensions = (0, 0),
    *,
    directory: Path = settings.IMAGES_DIRECTORY,
) -> Path:
    size = fit_image(*size)

    slug = encode(lines)
    variant = str(style) + str(size)
    fingerprint = hashlib.sha1(variant.encode()).hexdigest()

    path = directory / template.key / f"{slug}.{fingerprint}.{ext}"
    if path.exists():
        logger.info(f"Found meme at {path}")
        if settings.DEPLOYED:
            return path
    else:
        logger.info(f"Saving meme to {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    image = render_image(template, style, lines, size)
    image.save(path, quality=95)

    return path


def load(path: Path) -> Image:
    image = Image.open(path).convert("RGB")
    image = ImageOps.exif_transpose(image)
    return image


def render_image(
    template: Template,
    style: str,
    lines: List[str],
    size: Dimensions,
    *,
    pad: Optional[bool] = None,
) -> Image:
    background = load(template.get_image(style))

    pad = all(size) if pad is None else pad
    image = resize_image(background, *size, pad)

    for (
        point,
        offset,
        text,
        max_text_size,
        text_fill,
        font_size,
        stroke_width,
        stroke_fill,
        angle,
    ) in get_image_elements(template, lines, image.size):

        box = Image.new("RGBA", max_text_size)
        draw = ImageDraw.Draw(box)

        if settings.DEBUG:
            xy = (0, 0, max_text_size[0] - 1, max_text_size[1] - 1)
            draw.rectangle(xy, outline="lime")

        if angle:
            font = ImageFont.truetype(str(settings.FONT_THIN), size=font_size)
        else:
            font = ImageFont.truetype(str(settings.FONT_THICK), size=font_size)

        draw.text(
            (-offset[0], -offset[1]),
            text,
            text_fill,
            font,
            spacing=-offset[1] / 2,
            align="center",
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

        box = box.rotate(angle, resample=Image.BICUBIC, expand=True)
        image.paste(box, point, box)

    if pad:
        image = add_blurred_background(image, background, *size)

    return image


def resize_image(image: Image, width: int, height: int, pad: bool) -> Image:
    ratio = image.width / image.height
    default_width, default_height = settings.DEFAULT_SIZE

    if pad:
        if width < height * ratio:
            size = width, int(width / ratio)
        else:
            size = int(height * ratio), height
    elif width:
        size = width, int(width / ratio)
    elif height:
        size = int(height * ratio), height
    elif ratio < 1.0:
        size = default_width, int(default_height / ratio)
    else:
        size = int(default_width * ratio), default_height

    image = image.resize(size, Image.LANCZOS)
    return image


def fit_image(width: float, height: float) -> Tuple[int, int]:
    while width * height > settings.MAXIMUM_PIXELS:
        width *= 0.75
        height *= 0.75
    return int(width), int(height)


def add_blurred_background(
    foreground: Image, background: Image, width: int, height: int
) -> Image:
    base_width, base_height = foreground.size

    border_width = min(width, base_width + 2)
    border_height = min(height, base_height + 2)
    border_dimensions = border_width, border_height
    border = Image.new("RGB", border_dimensions)
    border.paste(
        foreground,
        ((border_width - base_width) // 2, (border_height - base_height) // 2),
    )

    padded = background.resize((width, height), Image.LANCZOS)
    darkened = padded.point(lambda p: int(p * 0.4))
    blurred = darkened.filter(ImageFilter.GaussianBlur(5))

    blurred_width, blurred_height = blurred.size
    offset = (
        (blurred_width - border_width) // 2,
        (blurred_height - border_height) // 2,
    )
    blurred.paste(border, offset)

    return blurred


def get_image_elements(
    template: Template, lines: List[str], image_size: Dimensions
) -> Iterator[Tuple[Point, Offset, str, Dimensions, str, int, int, str, float]]:
    for index, text in enumerate(template.text):
        point = text.get_anchor(image_size)

        max_text_size = text.get_size(image_size)
        max_font_size = int(image_size[1] / 9)

        try:
            line = lines[index]
        except IndexError:
            line = ""
        else:
            line = text.stylize(wrap(line, max_text_size, max_font_size))

        font = get_font(line, text.angle, max_text_size, max_font_size)
        offset = get_text_offset(line, font, max_text_size)

        stroke_fill = "black"
        if text.color == "black":
            stroke_width = 0
        else:
            stroke_width = get_stroke_width(font)

        yield point, offset, line, max_text_size, text.color, font.size, stroke_width, stroke_fill, text.angle


def wrap(line: str, max_text_size: Dimensions, max_font_size: int) -> str:
    lines = split(line)

    single = get_font(line, 0, max_text_size, max_font_size)
    double = get_font(lines, 0, max_text_size, max_font_size)

    if single.size >= double.size:
        return line

    if get_text_size(lines, double)[0] >= max_text_size[0] * 0.65:
        return lines

    return line


def split(line: str) -> str:
    midpoint = len(line) // 2 - 1

    for offset in range(0, len(line) // 4):
        for index in [midpoint - offset, midpoint + offset]:
            if line[index] == " ":
                return line[:index] + "\n" + line[index:]

    return line


def get_font(
    text: str, angle: float, max_text_size: Dimensions, max_font_size: int
) -> ImageFont:
    max_text_width = max_text_size[0] - max_text_size[0] / 35
    max_text_height = max_text_size[1] - max_text_size[1] / 10

    for size in range(max(7, max_font_size), 6, -1):

        if angle:
            font = ImageFont.truetype(str(settings.FONT_THIN), size=size)
        else:
            font = ImageFont.truetype(str(settings.FONT_THICK), size=size)

        text_width, text_height = get_text_size_minus_font_offset(text, font)
        if text_width <= max_text_width and text_height <= max_text_height:
            break

    return font


def get_text_size_minus_font_offset(text: str, font: ImageFont) -> Dimensions:
    text_width, text_height = get_text_size(text, font)
    offset = font.getoffset(text)
    return text_width - offset[0], text_height - offset[1]


def get_text_offset(text: str, font: ImageFont, max_text_size: Dimensions) -> Offset:
    text_size = get_text_size(text, font)
    stroke_width = get_stroke_width(font)

    x_offset, y_offset = font.getoffset(text)

    x_offset -= stroke_width
    y_offset -= stroke_width

    x_offset -= (max_text_size[0] - text_size[0]) / 2
    y_offset -= (max_text_size[1] - text_size[1] / (1.25 if "\n" in text else 1.5)) // 2

    return x_offset, y_offset


def get_text_size(text: str, font: ImageFont) -> Dimensions:
    image = Image.new("RGB", (100, 100))
    draw = ImageDraw.Draw(image)
    text_size = draw.textsize(text, font)
    stroke_width = get_stroke_width(font)
    return text_size[0] + stroke_width, text_size[1] + stroke_width


def get_stroke_width(font: ImageFont) -> int:
    return min(3, max(1, font.size // 12))
