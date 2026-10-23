#!/usr/bin/env bash
# Download Maia, the human-like chess model, into a directory: get-maia.sh DIR
#
# Used by the Docker image, CI and `just maia`, so all three use the same model (ADR 0017). It
# is Maia-3 5M (https://github.com/CSSLab/maia3, AGPL-3.0) as ONNX, converted from the official
# checkpoint by docker/convert-maia.py and attached to a release of Home-Rank. The download is
# checked against the checksum below. Maia's licence comes along for the Docker image.
#
# Leaves DIR/maia3-5m.onnx and DIR/LICENSE.
#
# A new model: run `uv run docker/convert-maia.py OUT_DIR`, which prints the model's checksum,
# and copy OUT_DIR/maia3-5m-expected.json to backend/homerank/engine/tests/fixtures/. Publish
# the model as a release that isn't the latest one, so the install docs' "latest release"
# downloads keep pointing at Home-Rank itself:
#
#   gh release create maia3-5m-vN OUT_DIR/maia3-5m.onnx --latest=false --title "..." --notes "..."
#
# Then change MAIA_RELEASE and SHA256 below.
set -euo pipefail

MAIA_RELEASE="maia3-5m-v1"
SHA256="bb6502309b63b498bf87677d8eb4b2d83c9b88eca081539a3a90546683ef7b8c"
# Maia's licence, from the commit of Maia's code the conversion used.
LICENSE_URL="https://raw.githubusercontent.com/CSSLab/maia3/1e13597c42d4858b7cfd7cfdae01e297263364b2/LICENSE"
LICENSE_SHA256="8486a10c4393cee1c25392769ddd3b2d6c242d6ec7928e1414efff7dfb2f07ef"

dir=${1:?usage: get-maia.sh DIR}
mkdir -p "$dir"

# Into FILE only once the checksum matches, so a failed download leaves nothing behind.
download() { # URL FILE SHA256
    curl --fail --silent --show-error --location --output "$2.part" "$1"
    echo "$3  $2.part" | sha256sum --check --quiet - || { rm -f "$2.part"; exit 1; }
    mv "$2.part" "$2"
}

download "https://github.com/januhrhammer/Home-Rank/releases/download/$MAIA_RELEASE/maia3-5m.onnx" \
    "$dir/maia3-5m.onnx" "$SHA256"
download "$LICENSE_URL" "$dir/LICENSE" "$LICENSE_SHA256"
echo "Maia ($MAIA_RELEASE) is in $dir/maia3-5m.onnx"
