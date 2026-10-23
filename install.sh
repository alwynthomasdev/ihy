#!/bin/sh
# Install the ihy command (macOS / Linux).
#
#   curl -LsSf https://raw.githubusercontent.com/<owner>/ihy/main/install.sh | sh
#   curl -LsSf https://raw.githubusercontent.com/<owner>/ihy/main/install.sh | sh -s -- [REPO_URL] [REF]
#
# REPO_URL defaults to the main ihy repository; REF is an optional branch or
# tag such as v0.1.0. Both can also be set with IHY_REPO / IHY_REF.
set -eu

DEFAULT_REPO="https://github.com/<owner>/ihy.git"
PYTHON_VERSION="3.12"
REPO="${1:-${IHY_REPO:-$DEFAULT_REPO}}"
REF="${2:-${IHY_REF:-}}"

say() { printf 'ihy install: %s\n' "$1"; }
fail() { printf 'ihy install: ERROR: %s\n' "$1" >&2; exit 1; }

# 1. uv
if ! command -v uv >/dev/null 2>&1; then
    say "uv not found, installing it (https://docs.astral.sh/uv/)..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh || fail "could not install uv with curl"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh || fail "could not install uv with wget"
    else
        fail "need curl or wget to install uv"
    fi
fi

# 2. Make uv and installed tools visible in this session.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
command -v uv >/dev/null 2>&1 || fail "uv was installed but is not on PATH; open a new terminal and run this script again"

# 3. Install ihy in its own environment, with a Python uv downloads itself.
#    Installing from git+ needs git; without git, fall back to GitHub's zip archive.
if command -v git >/dev/null 2>&1; then
    SPEC="git+$REPO"
    [ -n "$REF" ] && SPEC="$SPEC@$REF"
else
    case "$REPO" in
        https://github.com/*)
            BASE="${REPO%.git}"
            SPEC="ihy-omr @ $BASE/archive/${REF:-refs/heads/main}.zip"
            say "git not found, installing from $BASE/archive/${REF:-refs/heads/main}.zip"
            ;;
        *) fail "git is required to install from $REPO" ;;
    esac
fi

say "installing $SPEC with Python $PYTHON_VERSION..."
uv tool install --python "$PYTHON_VERSION" "$SPEC" || fail "uv tool install failed (see messages above)"

# 4. Make sure the tool folder stays on PATH in future shells.
uv tool update-shell >/dev/null 2>&1 || true

command -v ihy >/dev/null 2>&1 || fail "ihy was installed but is not on PATH; open a new terminal and try again"
say "done: $(ihy --version)"
echo
echo "Next step:"
echo "  ihy --help              # see what ihy can do"
echo "  ihy --download-models   # optional: fetch the recognition models now (~150 MB)"
