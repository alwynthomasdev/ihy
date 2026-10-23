# ihy

**ihy** (named after the Egyptian god of music) turns a photo or scan of **printed** sheet music (PNG or JPG) into a compressed MusicXML file (`.mxl`) that you can open in [MuseScore](https://musescore.org) and other notation programs. It cleans up the image with OpenCV, reads the music with the [homr](https://github.com/liebharc/homr) optical music recognition engine, and writes the result with [music21](https://web.mit.edu/music21/). Recognition is not perfect: ihy gives you a good first draft, which you then **check and correct in MuseScore**. It works on engraved (printed) music only, not handwritten scores.

## Install

You don't need Python installed beforehand. The installer sets up [uv](https://docs.astral.sh/uv/), which downloads a suitable Python version and installs ihy in its own isolated environment.

**macOS / Linux**

```bash
curl -LsSf https://raw.githubusercontent.com/alwynthomasdev/ihy/main/install.sh | sh
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/alwynthomasdev/ihy/main/install.ps1 | iex
```

When it finishes, open a new terminal and run `ihy --help`.

> **Windows PowerShell users:** in PowerShell, `ihy` is a built-in alias for `Invoke-History`, so typing `ihy` won't start this tool. Use **`ihy-omr`** instead. It is the same program under a second name, and every example below works with it (for example `ihy-omr input.png`). `ihy.exe` also works. In Command Prompt (cmd), plain `ihy` works as normal.

**Manual install.** If you already use uv or pipx:

```bash
uv tool install --python 3.12 git+https://github.com/alwynthomasdev/ihy.git
# or
pipx install --python python3.12 git+https://github.com/alwynthomasdev/ihy.git
```

**A specific version** (pinned to a release tag):

```bash
uv tool install --python 3.12 git+https://github.com/alwynthomasdev/ihy.git@v0.1.0
# with the install scripts:
curl -LsSf https://raw.githubusercontent.com/alwynthomasdev/ihy/main/install.sh | sh -s -- https://github.com/alwynthomasdev/ihy.git v0.1.0
```

```powershell
$env:IHY_REF = "v0.1.0"; irm https://raw.githubusercontent.com/alwynthomasdev/ihy/main/install.ps1 | iex
```

ihy needs Python 3.11 or 3.12 (the versions homr supports). The commands above request 3.12.

## First run

The first time you convert an image, homr downloads its recognition models (about 150 MB). This needs an internet connection and can take a few minutes. Later runs work offline. To download the models up front instead:

```bash
ihy --download-models
```

The models are stored inside ihy's install folder, so they are downloaded again after an upgrade or reinstall.

ihy runs on the CPU by default. homr can use a GPU if an ONNX Runtime GPU build is available, but the standard install is CPU-only and that is fast enough for single pages (roughly 5–20 seconds per page).

## Usage

| Command | What it does |
| --- | --- |
| `ihy input.png` | writes input.mxl next to the image |
| `ihy input.png -o out/score.mxl` | explicit output path |
| `ihy scans/` | processes every PNG/JPG in the folder |
| `ihy input.png --no-preprocess` | skip the OpenCV clean-up step |
| `ihy input.png --binarise` | convert to pure black and white before recognition |
| `ihy input.png --keep-temp` | keep intermediate files for debugging |
| `ihy --download-models` | download homr's models now (one-off, ~150 MB) |

Full option list (this is the output of `ihy --help`):

```text
usage: ihy [-h] [-o PATH] [--no-preprocess] [--binarise] [--keep-temp] [--download-models]
           [--version]
           [input]

Convert an image of printed sheet music (PNG/JPG) into a compressed MusicXML file (.mxl) that opens in MuseScore.

positional arguments:
  input                 an image file (.png, .jpg, .jpeg) or a folder of images

options:
  -h, --help            show this help message and exit
  -o PATH, --output PATH
                        output .mxl file (single image) or output folder (folder input); default:
                        next to each image
  --no-preprocess       skip the OpenCV clean-up (greyscale, deskew, upscale, denoise)
  --binarise            convert to pure black and white after clean-up (try it on uneven lighting)
  --keep-temp           keep intermediate files (preprocessed image, raw MusicXML) and print where
                        they are
  --download-models     download homr's recognition models and exit
  --version             show program's version number and exit

examples:
  ihy input.png                   writes input.mxl next to the image
  ihy input.png -o out/score.mxl  explicit output path
  ihy scans/                      processes every PNG/JPG in the folder
  ihy input.png --no-preprocess   skip the OpenCV clean-up step
  ihy input.png --binarise        convert to pure black and white before recognition
  ihy input.png --keep-temp       keep intermediate files for debugging
  ihy --download-models           download homr's models now (one-off, ~150 MB)

Open the resulting .mxl in MuseScore and correct any mistakes.
```

In folder mode, a failed image doesn't stop the batch. ihy prints a summary at the end and exits with a non-zero code if any image failed. Nothing other than the `.mxl` is written next to your images; intermediate files go to a temporary folder that is deleted afterwards (unless you pass `--keep-temp`).

### Worked example

```console
$ ihy star-spangled-banner.png
star-spangled-banner.png
  preprocess     2.3s  (greyscale, upscale x2.91, denoise)
  recognise     15.8s
  export         0.3s  (2 part(s), 25 measure(s), 106 note(s))
  wrote star-spangled-banner.mxl  (total 18.4s)
```

Then open `star-spangled-banner.mxl` in MuseScore 4 (**File → Open**) and fix whatever the recogniser got wrong.

What the steps do:

1. **preprocess**: converts to greyscale, straightens a tilted page, enlarges small images so the staff lines are far enough apart, and removes light noise. Your original image is never changed.
2. **recognise**: homr finds the staves and reads the symbols, producing MusicXML.
3. **export**: music21 checks the MusicXML and saves it as `.mxl`. If music21 can't read homr's output, the raw `.musicxml` is saved next to where the `.mxl` would have gone, so you can still try opening it in MuseScore.

## Upgrading and uninstalling

The tool is registered under its package name, **`ihy-omr`**:

```bash
uv tool upgrade ihy-omr        # upgrade
uv tool uninstall ihy-omr      # uninstall

pipx upgrade ihy-omr           # if you installed with pipx
pipx uninstall ihy-omr
```

To move to a specific version, run the install command again with the tag (for example `@v0.2.0`) and add `--force`.

## Tips for good results

- Scan at **300 dpi or more**. With a phone, fill the frame with the page and keep the camera parallel to it.
- Keep the page **flat**, with even lighting and **good contrast** (black notes on white paper, no shadows).
- Use **one page per image**. Crop away anything that isn't music if you can.
- If a result looks wrong, try `--no-preprocess`. For unevenly lit photos, try `--binarise`. Don't use `--binarise` on thick, low-resolution scans, because it can merge the symbols together.
- When correcting in MuseScore, **check the clef, key signature and time signature first**. A mistake there throws off everything after it. Then check note lengths bar by bar.

## Troubleshooting

**Typing `ihy` in PowerShell shows "Cannot locate the history for command line" or re-runs an old command.**
PowerShell has a built-in alias `ihy` (Invoke-History). Use `ihy-omr` or `ihy.exe` instead. See the note under [Install](#install).

**`ihy: command not found` (or "not recognized") after installing.**
Open a new terminal so the updated PATH is picked up. If that doesn't help, run `uv tool update-shell` and open a new terminal again. The command lives in `~/.local/bin` (Windows: `%USERPROFILE%\.local\bin`). Add that folder to your PATH if needed.

**Model download fails.**
The first run needs internet access to `github.com` (homr's models are published as GitHub release files). Check your connection, proxy or firewall, then run `ihy --download-models` again. An interrupted download is retried automatically next time.

**"homr could not recognise the image" or another homr error.**
homr couldn't find staves in the picture. Check that the image shows printed music the right way up and that it is in focus. Try `--no-preprocess`, or crop the image more tightly. Run with `--keep-temp` to look at the preprocessed image ihy handed to homr. If the error says homr is not installed, reinstall ihy with one of the install commands.

**MuseScore won't open the file, or ihy reports "invalid MusicXML".**
homr produced MusicXML that music21 couldn't read. ihy keeps homr's raw output as a `.musicxml` file next to the intended `.mxl`, so try opening that in MuseScore instead. If that also fails, the page is probably too hard to recognise. Try a cleaner, higher-resolution scan.

**No notes, or very few notes, in the result.**
The image is probably too small, blurry or low-contrast. See the tips above.

## Licence and credits

ihy is licensed under the **GNU Affero General Public License v3.0** ([LICENSE](LICENSE)). ihy depends on and installs **homr**, which is licensed under the AGPL-3.0. Because ihy is distributed together with homr as one program, a permissive licence such as MIT would not apply to the combined work, so ihy uses the same licence as homr. The other main dependencies, music21 (BSD-3-Clause) and OpenCV (Apache-2.0), are compatible with it.

Built on:

- [homr](https://github.com/liebharc/homr) by liebharc and contributors, the optical music recognition engine (AGPL-3.0).
- [oemer](https://github.com/BreezeWhite/oemer) by BreezeWhite and contributors, whose segmentation work homr builds on.
- [music21](https://github.com/cuthbertLab/music21) by Michael Scott Asato Cuthbert and contributors (BSD-3-Clause).
- [OpenCV](https://opencv.org) (Apache-2.0).

The sample images in [tests/samples](tests/samples) are in the public domain. See [SOURCES.md](tests/samples/SOURCES.md).
