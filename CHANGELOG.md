# Changelog

All notable changes to ihy are listed here. Versions follow [Semantic Versioning](https://semver.org).

## v0.1.0 (2026-10-23)

First release.

- `ihy IMAGE` converts a PNG/JPG of printed sheet music to compressed MusicXML (`.mxl`) for MuseScore.
- Folder mode (`ihy FOLDER/`) processes every PNG/JPG and prints a success/failure summary. One bad image doesn't stop the batch.
- OpenCV preprocessing: greyscale, deskew, upscaling of small images, light denoise. Optional `--binarise`, and `--no-preprocess` to skip it.
- Recognition with homr 0.7, run in a separate process. Clear errors when homr is missing or fails.
- Export with music21. If the recognised MusicXML can't be parsed, the raw file is kept and a warning is shown.
- `--keep-temp` keeps intermediate files. `--download-models` fetches homr's models ahead of time.
- Timings for each stage. Non-zero exit code on failure.
- Also installed as `ihy-omr`, because `ihy` is a built-in alias in PowerShell.
- One-line installers for macOS/Linux (`install.sh`) and Windows (`install.ps1`) using uv.
