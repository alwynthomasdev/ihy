"""Thin wrapper that runs homr in a separate process.

homr is run through its own command-line entry point rather than imported,
so a crash inside it cannot take down a whole batch, and its noisy output
can be captured and summarised.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Run homr's CLI with the same interpreter ihy is running under. This finds
# homr in uv/pipx tool environments without relying on PATH.
_HOMR_LAUNCHER = "import sys; from homr.main import main; sys.argv[0] = 'homr'; main()"


class HomrNotFound(Exception):
    """homr is not installed in this Python environment."""


class HomrFailed(Exception):
    """homr ran but did not produce MusicXML."""


def homr_available() -> bool:
    return importlib.util.find_spec("homr") is not None


def models_downloaded() -> bool:
    """Best guess at whether homr's model files are already on disk."""
    spec = importlib.util.find_spec("homr")
    if spec is None or not spec.submodule_search_locations:
        return False
    package_dir = Path(next(iter(spec.submodule_search_locations)))
    # segmentation model + transformer encoder + decoder
    return len(list(package_dir.rglob("*.onnx"))) >= 3


def _run_homr(args: list[str], *, stream: bool = False) -> subprocess.CompletedProcess:
    if not homr_available():
        raise HomrNotFound(
            "homr is not installed in this environment. Reinstall ihy "
            "(see README) or run: pip install homr"
        )
    env = dict(os.environ)
    # homr's dependencies print hundreds of harmless SyntaxWarnings.
    env["PYTHONWARNINGS"] = "ignore"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    cmd = [sys.executable, "-c", _HOMR_LAUNCHER, *args]
    if stream:
        return subprocess.run(cmd, env=env, check=False)
    return subprocess.run(
        cmd, env=env, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def download_models() -> None:
    """Download homr's models now instead of on the first recognition."""
    result = _run_homr(["--init"], stream=True)
    if result.returncode != 0:
        raise HomrFailed(
            f"model download failed (homr exit code {result.returncode}). "
            "Check your internet connection and try again."
        )


def _tail(text: str, lines: int = 15) -> str:
    kept = [ln for ln in (text or "").splitlines() if ln.strip() and not ln.startswith("Downloaded ")]
    return "\n".join(kept[-lines:])


def recognise(image: Path, workdir: Path) -> Path:
    """Run homr on ``image`` and return the path of the MusicXML it produced.

    homr writes its output next to its input, so the image is first copied
    into ``workdir`` under a plain ASCII name. Nothing is written beside the
    user's original file.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    work_image = workdir / f"page{image.suffix.lower()}"
    if image.resolve() != work_image.resolve():
        shutil.copyfile(image, work_image)
    expected = work_image.with_suffix(".musicxml")
    if expected.exists():
        expected.unlink()

    result = _run_homr([str(work_image)])
    if result.returncode != 0 or not expected.exists():
        detail = _tail(result.stderr) or _tail(result.stdout) or "no output"
        raise HomrFailed(
            f"homr could not recognise the image (exit code {result.returncode}).\n{detail}"
        )
    return expected
