"""ihy: convert images of printed sheet music to compressed MusicXML (.mxl)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ihy-omr")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.0.0"

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
SUPPORTED_EXTENSIONS = (*IMAGE_EXTENSIONS, ".pdf")
