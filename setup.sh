#!/usr/bin/env bash
set -euo pipefail

case "$(uname -s)" in
    Linux|Darwin) ;;
    *)
        echo "setup.sh supports Linux and macOS. Windows is not supported."
        exit 1
        ;;
esac

PYTHON=""
for candidate in python3.13 python3; do
    if command -v "$candidate" >/dev/null && [[ "$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == "3.13" ]]; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "Python 3.13 is required but was not found."
    echo "Install Python 3.13 with your system package manager, then run ./setup.sh again."
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .git ]]; then
    echo "This checkout needs its Git submodules. Clone the repository, then run ./setup.sh."
    exit 1
fi

git submodule update --init dependencies/nl2ltl dependencies/Flat

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .

install_mona() {
    SUDO=()

    if command -v mona >/dev/null; then
        return
    fi

    if [[ "$EUID" -eq 0 ]]; then
        SUDO=()
    elif command -v sudo >/dev/null; then
        SUDO=(sudo)
    fi

    if command -v apt-get >/dev/null; then
        "${SUDO[@]}" apt-get update && "${SUDO[@]}" apt-get install -y mona || true
    elif command -v dnf >/dev/null; then
        "${SUDO[@]}" dnf install -y mona || true
    elif command -v brew >/dev/null; then
        brew install mona || true
    fi

    if command -v mona >/dev/null; then
        return
    fi

    command -v curl >/dev/null || { echo "MONA needs curl for the source fallback."; exit 1; }
    command -v make >/dev/null || { echo "MONA needs make for the source fallback."; exit 1; }

    build_dir="$(mktemp -d)"
    trap 'rm -rf "$build_dir"' RETURN
    curl -fsSL -o "$build_dir/mona.tar.gz" https://www.brics.dk/mona/download/mona-1.4-18.tar.gz
    tar -xzf "$build_dir/mona.tar.gz" -C "$build_dir"
    (
        cd "$build_dir/mona-1.4-18"
        ./configure --prefix="$HOME/.local"
        make
        make install
    )
    export PATH="$HOME/.local/bin:$PATH"
}

install_mona

if [[ -x "$HOME/.local/bin/mona" ]]; then
    ln -sf "$HOME/.local/bin/mona" .venv/bin/mona
fi

if [[ ! -f .env ]]; then
    cp example.env .env
fi

mona -v
echo "Setup complete. Activate the environment with: source .venv/bin/activate"
