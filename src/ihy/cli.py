"""Command-line interface: argument parsing and batch handling."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import SUPPORTED_EXTENSIONS, __version__
from .export import InvalidMusicXML, finish_score, load_score
from .pdf import RENDER_DPI, PdfError, page_count, parse_pages, render_pages
from .postprocess import INSTRUMENTS, merge_scores, parse_time_list
from .preprocess import ImageReadError, preprocess
from .recognise import HomrFailed, HomrNotFound, download_models, models_downloaded, recognise

EXAMPLES = """\
examples:
  ihy input.png                   writes input.mxl next to the image
  ihy input.png -o out/score.mxl  explicit output path
  ihy piece.pdf                   all pages of a PDF, joined into piece.mxl
  ihy piece.pdf --pages 2-3       only some pages of a PDF (e.g. 2-3 or 1,3)
  ihy scans/                      processes every PNG/JPG/PDF in the folder
  ihy input.png --no-preprocess   skip the OpenCV clean-up step
  ihy input.png --binarise        convert to pure black and white before recognition
  ihy input.png --keep-temp       keep intermediate files for debugging
  ihy input.png --instrument cello
                                  label the part as cello (also violin, viola, bass, piano, voice)
  ihy input.png --time 3/4        set the time signature instead of guessing it
  ihy input.png --time 6/8,2/4    one value per time signature in the piece, in order
  ihy --download-models           download homr's models now (one-off, ~150 MB)

Open the resulting .mxl in MuseScore and correct any mistakes.
"""


class UsageError(Exception):
    """Bad input from the user, such as a missing file or unsupported format."""


@dataclass
class Outcome:
    source: Path
    output: Path | None = None
    error: str | None = None
    timings: dict[str, float] = field(default_factory=dict)
    # Things that went wrong without failing the file, e.g. skipped PDF pages.
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None


def _time_arg(text: str) -> list[str]:
    try:
        values = parse_time_list(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not values:
        raise argparse.ArgumentTypeError("give at least one time signature, e.g. 3/4")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ihy",
        description=(
            "Convert printed sheet music (a PNG/JPG image or a PDF) into a compressed "
            "MusicXML file (.mxl) that opens in MuseScore."
        ),
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="an image (.png, .jpg, .jpeg), a PDF, or a folder of them",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="PATH",
        help="output .mxl file (single input) or output folder (folder input); "
        "default: next to each input",
    )
    parser.add_argument(
        "--pages",
        metavar="RANGE",
        help="PDF pages to convert, e.g. 2-4 or 1,3 (default: all); single PDF only",
    )
    parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="skip the OpenCV clean-up (greyscale, deskew, upscale, denoise)",
    )
    parser.add_argument(
        "--binarise",
        action="store_true",
        help="convert to pure black and white after clean-up (try it on uneven lighting)",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="keep intermediate files (preprocessed image, raw MusicXML) and print where they are",
    )
    parser.add_argument(
        "--instrument",
        choices=sorted(INSTRUMENTS),
        help="instrument for the part(s) in MuseScore; default: homr's guess "
        "(Voice for one staff, Piano for two)",
    )
    parser.add_argument(
        "--time",
        type=_time_arg,
        metavar="SIG[,SIG...]",
        help="time signature(s), e.g. 3/4, or 6/8,2/4 for a piece that changes; "
        "default: worked out from the recognised bars",
    )
    parser.add_argument(
        "--download-models",
        action="store_true",
        help="download homr's recognition models and exit",
    )
    parser.add_argument("--version", action="version", version=f"ihy {__version__}")
    return parser


def collect_images(path: Path) -> list[Path]:
    """Return the image(s) to process, or raise UsageError."""
    if not path.exists():
        raise UsageError(f"'{path}' does not exist")
    if path.is_dir():
        images = sorted(
            p for p in path.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        if not images:
            raise UsageError(f"no .png, .jpg, .jpeg or .pdf files found in folder '{path}'")
        return images
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UsageError(
            f"unsupported file type '{path.suffix or '(none)'}' for '{path}'; "
            "use a .png, .jpg or .jpeg image or a .pdf"
        )
    return [path]


def output_path_for(image: Path, output: Path | None, folder_mode: bool) -> Path:
    if output is None:
        return image.with_suffix(".mxl")
    if folder_mode or output.is_dir() or str(output).endswith(("/", "\\")):
        return output / f"{image.stem}.mxl"
    return output if output.suffix.lower() == ".mxl" else output.with_suffix(".mxl")


def _add_time(outcome: Outcome, stage: str, start: float) -> float:
    elapsed = time.perf_counter() - start
    outcome.timings[stage] = outcome.timings.get(stage, 0.0) + elapsed
    return elapsed


def recognise_page(image: Path, out: Path, workdir: Path, args: argparse.Namespace, outcome: Outcome):
    """Preprocess and recognise one image; return the parsed music21 score."""
    start = time.perf_counter()
    if args.no_preprocess:
        to_recognise = image
    else:
        pre = preprocess(image, workdir / "preprocessed.png", binarise_output=args.binarise)
        to_recognise = pre.path
        took = _add_time(outcome, "preprocess", start)
        print(f"  preprocess  {took:6.1f}s  ({', '.join(pre.steps)})")

    start = time.perf_counter()
    musicxml = recognise(to_recognise, workdir)
    took = _add_time(outcome, "recognise", start)
    print(f"  recognise   {took:6.1f}s")
    return load_score(musicxml, out)


def recognise_pdf(pdf: Path, out: Path, workdir: Path, args: argparse.Namespace, outcome: Outcome):
    """Render, recognise and merge the selected pages of a PDF."""
    start = time.perf_counter()
    pages = parse_pages(args.pages, page_count(pdf))
    images = render_pages(pdf, pages, workdir / "pages")
    took = _add_time(outcome, "render", start)
    print(f"  render      {took:6.1f}s  ({len(pages)} page(s) at {RENDER_DPI} dpi)")

    scores = []
    for number, image in zip(pages, images):
        print(f"  page {number}")
        try:
            scores.append(recognise_page(image, out, workdir / f"page-{number:03d}", args, outcome))
        except HomrNotFound:
            raise
        except (ImageReadError, HomrFailed, InvalidMusicXML) as exc:
            reason = str(exc).splitlines()[0]
            outcome.notes.append(f"page {number} skipped: {reason}")
            print(f"  warning: page {number} skipped ({reason})", file=sys.stderr)
    if not scores:
        raise HomrFailed(f"no music was recognised on any of the {len(pages)} page(s)")

    merged, warnings = merge_scores(scores)
    for warning in warnings:
        outcome.notes.append(warning)
        print(f"  warning: {warning}", file=sys.stderr)
    return merged


def process_one(image: Path, out: Path, workdir: Path, args: argparse.Namespace) -> Outcome:
    outcome = Outcome(source=image)
    try:
        if image.suffix.lower() == ".pdf":
            score = recognise_pdf(image, out, workdir, args, outcome)
        else:
            score = recognise_page(image, out, workdir, args, outcome)

        start = time.perf_counter()
        result = finish_score(score, out, instrument=args.instrument, time=args.time)
        _add_time(outcome, "export", start)
        print(
            f"  export      {outcome.timings['export']:6.1f}s  "
            f"({result.parts} part(s), {result.measures} measure(s), {result.notes} note(s))"
        )
        if result.time_signatures:
            how = "as given" if args.time else "worked out; use --time to change"
            print(f"  time        {' -> '.join(result.time_signatures)}  ({how})")
        if result.instrument:
            print(f"  instrument  {result.instrument}")
        outcome.output = result.path
        if result.notes == 0:
            print("  warning: no notes were recognised; check the image quality", file=sys.stderr)
    except (ImageReadError, PdfError) as exc:
        outcome.error = str(exc)
    except HomrNotFound as exc:
        outcome.error = str(exc)
    except HomrFailed as exc:
        outcome.error = str(exc)
    except InvalidMusicXML as exc:
        outcome.error = f"invalid MusicXML: {exc}"
        print(f"  warning: {exc}", file=sys.stderr)
    except Exception as exc:  # keep the batch going whatever happens
        outcome.error = f"unexpected error: {type(exc).__name__}: {exc}"
    return outcome


def print_summary(outcomes: list[Outcome]) -> None:
    ok = [o for o in outcomes if o.ok]
    failed = [o for o in outcomes if not o.ok]
    print()
    print(f"Summary: {len(ok)} succeeded, {len(failed)} failed")
    for o in ok:
        extra = f"  ({'; '.join(o.notes)})" if o.notes else ""
        print(f"  ok      {o.source.name} -> {o.output}{extra}")
    for o in failed:
        first_line = (o.error or "").splitlines()[0]
        print(f"  failed  {o.source.name}: {first_line}")


def main(argv: list[str] | None = None) -> int:
    # Don't crash printing non-ASCII file names on consoles like Windows cp1252,
    # and keep progress and error lines in order when output is piped.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace", line_buffering=True)
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.download_models:
        try:
            download_models()
        except (HomrNotFound, HomrFailed) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print("Models are ready.")
        return 0

    if args.input is None:
        parser.print_usage(sys.stderr)
        print("error: give an image, a PDF or a folder (see ihy --help)", file=sys.stderr)
        return 2
    if args.no_preprocess and args.binarise:
        print("error: --binarise cannot be combined with --no-preprocess", file=sys.stderr)
        return 2

    try:
        images = collect_images(args.input)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    folder_mode = args.input.is_dir()
    if folder_mode and args.output is not None and args.output.suffix.lower() == ".mxl":
        print("error: with a folder input, -o must be a folder, not a .mxl file", file=sys.stderr)
        return 2

    if args.pages is not None:
        if folder_mode or args.input.suffix.lower() != ".pdf":
            print("error: --pages only works with a single PDF file", file=sys.stderr)
            return 2
        try:
            parse_pages(args.pages, page_count(args.input))
        except (ValueError, PdfError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if not models_downloaded():
        print(
            "Note: homr will download its recognition models first (~150 MB, one-off). "
            "This needs internet and can take a few minutes."
        )

    temp_root = Path(tempfile.mkdtemp(prefix="ihy-"))
    outcomes: list[Outcome] = []
    try:
        for index, image in enumerate(images, start=1):
            out = output_path_for(image, args.output, folder_mode)
            prefix = f"[{index}/{len(images)}] " if folder_mode else ""
            print(f"{prefix}{image}")
            workdir = temp_root / f"{index:03d}-{image.stem}"
            outcome = process_one(image, out, workdir, args)
            outcomes.append(outcome)
            if outcome.ok:
                print(f"  wrote {outcome.output}  (total {sum(outcome.timings.values()):.1f}s)")
            else:
                print(f"  error: {outcome.error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    finally:
        if args.keep_temp:
            print(f"Intermediate files kept in {temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)

    if folder_mode:
        print_summary(outcomes)
    return 0 if all(o.ok for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
