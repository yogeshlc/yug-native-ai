#!/bin/bash
# Yug Native AI: inspect first, then install only after confirmation.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHECK_ONLY=0
ASSUME_YES=0
REQUESTED_MODEL=""
usage() {
  echo 'Usage: bash setup-mac.sh [--check-only] [--yes] [--model qwen3.5:35b]'
  echo 'Default: discover newest stable general-purpose Qwen family with a fitting local model.'
  echo '--check-only performs metadata/system checks without installing or downloading weights.'
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --check-only) CHECK_ONLY=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --model) [ "$#" -ge 2 ] || { usage; exit 1; }; REQUESTED_MODEL="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac
done
[ "$(uname -s)" = Darwin ] || { echo 'This installer supports macOS only.'; exit 1; }
[ "$(uname -m)" = arm64 ] || { echo 'Use an Apple Silicon Mac and an ARM-native Terminal (disable Rosetta). Intel CPU-only setup is not supported by this script.'; exit 1; }
MACOS_VERSION="$(sw_vers -productVersion)"
[ "${MACOS_VERSION%%.*}" -ge 14 ] || { echo 'macOS Sonoma 14 or newer is required.'; exit 1; }
command -v python3 >/dev/null || { echo 'Install Python 3.10+ from https://www.python.org/downloads/macos/ and rerun.'; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || { echo 'Python 3.10+ is required.'; exit 1; }
python3 -c 'import shutil,sys,os; paths=[os.path.expanduser("~"),os.environ.get("TMPDIR","/tmp")]; sys.exit(0 if all(shutil.disk_usage(p).free >= 3*2**30 for p in paths) else 1)' || { echo 'At least 3 GiB free on home and temporary volumes is required for Ollama installation.'; exit 1; }
RAM_BYTES="$(sysctl -n hw.memsize)"
[ "$RAM_BYTES" -ge 8589934592 ] || { echo 'This setup requires at least 8 GiB RAM.'; exit 1; }
MODEL_DIR="${OLLAMA_MODELS:-$HOME/.ollama/models}"
# Check the nearest existing ancestor, including a custom model volume.
DISK_PATH="$MODEL_DIR"
while [ ! -d "$DISK_PATH" ]; do DISK_PATH="$(dirname "$DISK_PATH")"; done
FREE_BYTES="$(python3 -c 'import shutil,sys; print(shutil.disk_usage(sys.argv[1]).free)' "$DISK_PATH")"
echo "macOS: $MACOS_VERSION | Architecture: $(uname -m)"
python3 -c 'import sys; print("RAM: %.1f GiB | Free model-volume space: %.1f GiB" % (int(sys.argv[1])/2**30,int(sys.argv[2])/2**30))' "$RAM_BYTES" "$FREE_BYTES"
echo 'Checking live Ollama model metadata (no weights downloaded yet)…'
YUG_TMP="$(mktemp -d "${TMPDIR:-/tmp}/yug-setup.XXXXXX")"
MOUNT_POINT=""
cleanup() {
  if [ -n "$MOUNT_POINT" ]; then hdiutil detach "$MOUNT_POINT" -quiet || true; fi
  rm -rf "$YUG_TMP"
}
trap cleanup EXIT
if [ -n "$REQUESTED_MODEL" ]; then
  python3 "$SCRIPT_DIR/scripts/select_qwen.py" --ram "$RAM_BYTES" --free "$FREE_BYTES" --model "$REQUESTED_MODEL" > "$YUG_TMP/model"
else
  python3 "$SCRIPT_DIR/scripts/select_qwen.py" --ram "$RAM_BYTES" --free "$FREE_BYTES" > "$YUG_TMP/model"
fi
MODEL="$(sed -n '1p' "$YUG_TMP/model")"
MODEL_BYTES="$(sed -n '2p' "$YUG_TMP/model")"
echo "Selected model: $MODEL"
python3 -c 'import sys; print("Full download budget: %.1f GiB" % (int(sys.argv[1])/2**30))' "$MODEL_BYTES"
echo 'Selection is a conservative estimate; it does not guarantee inference speed or memory fit.'
echo 'The newest discovered family is preferred; older families are used only if newer ones do not fit.'
if [ "$CHECK_ONLY" -eq 1 ]; then echo 'Check complete. No software or model was installed.'; exit 0; fi
if [ "$ASSUME_YES" -ne 1 ]; then
  read -r -p "Install/update official Ollama and pull $MODEL? [y/N] " answer
  case "$answer" in y|Y|yes|YES) ;; *) echo 'Cancelled.'; exit 0 ;; esac
fi
# Resolve the latest stable release from Ollama's official GitHub repository.
python3 - "$YUG_TMP" <<'PY'
import json, pathlib, sys, urllib.request
req=urllib.request.Request('https://api.github.com/repos/ollama/ollama/releases/latest',headers={'User-Agent':'Yug-Native-AI-Setup'})
with urllib.request.urlopen(req,timeout=30) as r: release=json.load(r)
assets=release.get('assets',[])
asset=next((a for a in assets if a['name']=='Ollama.dmg'),None) or next((a for a in assets if a['name']=='Ollama-darwin.zip'),None)
if not asset: sys.exit('No supported Mac app asset found in latest stable release. Install manually: https://ollama.com/download/mac')
url=asset['browser_download_url']
if not url.startswith('https://github.com/ollama/ollama/releases/download/'): sys.exit('Unexpected download source')
p=pathlib.Path(sys.argv[1]); (p/'url').write_text(url); (p/'asset').write_text(asset['name'])
print('Ollama release:',release['tag_name'])
PY
ASSET="$(cat "$YUG_TMP/asset")"
curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' "$(cat "$YUG_TMP/url")" -o "$YUG_TMP/$ASSET"
if [ "$ASSET" = Ollama.dmg ]; then
  MOUNT_POINT="$YUG_TMP/mount"
  mkdir "$MOUNT_POINT"
  hdiutil attach "$YUG_TMP/$ASSET" -mountpoint "$MOUNT_POINT" -nobrowse -quiet
  APP_SOURCE="$MOUNT_POINT/Ollama.app"
else
  ditto -x -k "$YUG_TMP/$ASSET" "$YUG_TMP/unpacked"
  APP_SOURCE="$YUG_TMP/unpacked/Ollama.app"
fi
[ -d "$APP_SOURCE" ] || { echo 'Ollama.app missing from archive.'; exit 1; }
codesign --verify --deep --strict "$APP_SOURCE"
spctl --assess --type execute "$APP_SOURCE"
# Install per-user without sudo; preserve any previous per-user application.
INSTALL_DIR="$HOME/Applications"
mkdir -p "$INSTALL_DIR"
TARGET_APP="$INSTALL_DIR/Ollama.app"
if pgrep -x Ollama >/dev/null; then
  echo 'Quit the running Ollama app, then press Return to continue.'
  read -r
  pgrep -x Ollama >/dev/null && { echo 'Ollama is still running. Rerun after quitting.'; exit 1; }
fi
if [ -e "$TARGET_APP" ]; then mv "$TARGET_APP" "$INSTALL_DIR/Ollama.backup.$(date +%Y%m%d%H%M%S).app"; fi
ditto "$APP_SOURCE" "$TARGET_APP"
OLLAMA_BIN="$TARGET_APP/Contents/Resources/ollama"
[ -x "$OLLAMA_BIN" ] || { echo 'Ollama CLI missing from app.'; exit 1; }
# Use the installed binary directly; do not alter PATH or shell profiles.
open "$TARGET_APP"
echo 'Waiting up to 60 seconds for local Ollama. Complete any macOS first-run prompt.'
READY=0
for ((i=0; i<30; i++)); do
  if curl --fail --silent --max-time 2 http://127.0.0.1:11434/api/version >/dev/null; then READY=1; break; fi
  sleep 2
done
[ "$READY" -eq 1 ] || { echo 'Open Ollama and rerun; its local API is not ready.'; exit 1; }
OLLAMA_HOST=http://127.0.0.1:11434 "$OLLAMA_BIN" pull "$MODEL"
OLLAMA_HOST=http://127.0.0.1:11434 "$OLLAMA_BIN" list
echo "Setup complete. Selected model: $MODEL"
echo 'Start Yug from the project folder: python3 server.py'
echo 'Open http://127.0.0.1:8787 and refresh/select the downloaded model.'
