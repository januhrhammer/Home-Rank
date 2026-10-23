#!/usr/bin/env bash
# Download Stockfish, the chess engine, into a directory: get-stockfish.sh DIR
#
# Used by the Docker image, CI and `just stockfish`, so all three run the same version. It is
# the official release's "universal" Linux build, which picks the fastest variant for the CPU
# it runs on. The download is checked against the checksum below; the archive also holds
# Stockfish's source code and licence (GPL-3.0), which the Docker image keeps (ADR 0002).
#
# Leaves DIR/stockfish (the program), DIR/src, DIR/Copying.txt and the release's other files.
#
# A new version: change STOCKFISH_VERSION and both checksums, shown on the release page next to
# each download (https://github.com/official-stockfish/Stockfish/releases).
set -euo pipefail

STOCKFISH_VERSION="19"
SHA256_X86_64="9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f"
SHA256_ARM64="fe26cfd1d9db4c8af3d21e24d9ff34cacb31c1f940085a7583da11796f2bac01"

dir=${1:?usage: get-stockfish.sh DIR}

case "$(uname -m)" in
    x86_64) arch=x86-64 sha256=$SHA256_X86_64 ;;
    aarch64 | arm64) arch=arm64 sha256=$SHA256_ARM64 ;;
    *) echo "No Stockfish build for $(uname -m)" >&2; exit 1 ;;
esac

url="https://github.com/official-stockfish/Stockfish/releases/download/sf_${STOCKFISH_VERSION}/stockfish-linux-${arch}-universal.tar.gz"
archive=$(mktemp)
trap 'rm -f "$archive"' EXIT

curl --fail --silent --show-error --location --output "$archive" "$url"
echo "$sha256  $archive" | sha256sum --check --quiet -
mkdir -p "$dir"
tar --extract --gzip --file "$archive" --directory "$dir" --strip-components=1
mv "$dir/stockfish-linux-${arch}-universal" "$dir/stockfish"
echo "Stockfish $STOCKFISH_VERSION is in $dir/stockfish"
