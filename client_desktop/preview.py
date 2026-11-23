"""Preview kind mapping (variant types 5): .js -> text, .png -> image, anything else -> unavailable."""
from __future__ import annotations

import posixpath
from enum import Enum


class PreviewKind(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    UNAVAILABLE = "unavailable"


UNAVAILABLE_TEXT = "Preview unavailable"


def preview_kind(filename: str) -> PreviewKind:
    ext = posixpath.splitext(filename)[1].lower()
    if ext == ".js":
        return PreviewKind.TEXT
    if ext == ".png":
        return PreviewKind.IMAGE
    return PreviewKind.UNAVAILABLE
