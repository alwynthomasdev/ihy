# Changelog

All notable changes to ihy are listed here. Versions follow [Semantic Versioning](https://semver.org).

## v0.2.0 (2026-10-23)

### Fixed
- **Bars were corrupted when the time signature was wrong.** music21's export re-split any bar that didn't fit the time signature, moving notes into neighbouring bars. Bars are now kept exactly as homr recognised them.
- **Wrong time signatures.** homr guesses the top number from the median bar length of the whole piece, so pieces that change metre (such as 6/8 → 2/4) came out wrong. ihy now works out each section's time signature separately and tidies odd forms (12/16 → 3/4).

### Added
- `--instrument {cello,violin,viola,bass,piano,voice}` sets the instrument MuseScore opens the part as, including its playback sound. Previously single-staff parts were always "Voice".
- `--time SIG[,SIG...]` sets the time signature(s) yourself, one per change in the piece.
- The chosen time signatures and instrument are printed after each conversion.

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
