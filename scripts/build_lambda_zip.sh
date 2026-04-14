#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAMBDA="${ROOT}/lambda"
PKG="${LAMBDA}/package"
ZIP="${LAMBDA}/deployment.zip"

rm -rf "${PKG}" "${ZIP}"
mkdir -p "${PKG}"

python -m pip install -r "${LAMBDA}/requirements.txt" -t "${PKG}"
cp "${LAMBDA}/redact_handler.py" "${PKG}/"
cp -r "${LAMBDA}/lib" "${PKG}/"

(
  cd "${PKG}"
  zip -r "${ZIP}" . -q
)

echo "Wrote ${ZIP}"
