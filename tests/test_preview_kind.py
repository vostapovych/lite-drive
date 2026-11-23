"""Test 5: preview kind mapping."""
import pytest

from client_desktop.preview import PreviewKind, preview_kind


@pytest.mark.parametrize("name,kind", [
    ("hello.js", PreviewKind.TEXT),
    ("HELLO.JS", PreviewKind.TEXT),
    ("logo.png", PreviewKind.IMAGE),
    ("Banner.PNG", PreviewKind.IMAGE),
    ("main.cpp", PreviewKind.UNAVAILABLE),
    ("notes.txt", PreviewKind.UNAVAILABLE),
    ("photo.jpg", PreviewKind.UNAVAILABLE),
    ("noext", PreviewKind.UNAVAILABLE),
    ("archive.js.zip", PreviewKind.UNAVAILABLE),
])
def test_preview_kind(name, kind):
    assert preview_kind(name) is kind
