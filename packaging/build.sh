#!/usr/bin/env bash
# proki, shipped: the engine as one program (PyInstaller) with nats-server beside it, put inside the
# app, then the app's installer for this machine's OS. The app starts the engine itself.
#
#     packaging/build.sh
#
# Needs uv, Node and Rust. macOS makes a .dmg, Windows (Git Bash) an installer .exe; both land in
# ui/app/target/release/bundle/. The .dmg is signed with the certificate APPLE_SIGNING_IDENTITY names, else
# ad hoc; neither is notarized: see the README for opening them.
set -euo pipefail
cd "$(dirname "$0")/.."

NATS=2.15.0   # the nats-server shipped, checked against its release's SHA256SUMS
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)               os=darwin  arch=arm64 pack=tar.gz bundles=app,dmg ;;
  Darwin-x86_64)              os=darwin  arch=amd64 pack=tar.gz bundles=app,dmg ;;
  MINGW*|MSYS*|CYGWIN*)       os=windows arch=amd64 pack=zip    bundles=nsis    ;;
  *)                          echo "build on macOS or Windows" >&2; exit 1 ;;
esac

rm -rf build/engine build/nats build/input-venv build/input-pyinstaller   # a fresh start: uv won't make a venv over the last one
uv run pyinstaller packaging/proki-engine.spec --distpath build/engine --workpath build/pyinstaller --noconfirm

# The input watcher is not part of ActivityWatch's standard release. Freeze it in
# its own environment: its aw-core pins conflict with the engine's platformdirs.
uv venv --python 3.12 build/input-venv
if [ "$os" = windows ]; then
  watcher_python=build/input-venv/Scripts/python.exe
  watcher_exe=aw-watcher-input.exe
else
  watcher_python=build/input-venv/bin/python
  watcher_exe=aw-watcher-input
fi
uv pip install --python "$watcher_python" --no-deps -r packaging/input-watcher.txt   # each package at the version it was tried with; the list has them all, so none is looked up again
"$watcher_python" -m PyInstaller packaging/input-watcher.py --name aw-watcher-input \
  --distpath build/engine/proki-engine --workpath build/input-pyinstaller --specpath build \
  --collect-submodules aw_watcher_afk --collect-submodules pynput --noconfirm
"build/engine/proki-engine/aw-watcher-input/$watcher_exe" --help

name="nats-server-v$NATS-$os-$arch"
url="https://github.com/nats-io/nats-server/releases/download/v$NATS"
mkdir -p build/nats
curl -fsSL -o "build/nats/$name.$pack" "$url/$name.$pack"
curl -fsSL -o build/nats/SHA256SUMS "$url/SHA256SUMS"
(cd build/nats && grep " $name.$pack\$" SHA256SUMS | $(command -v sha256sum || echo shasum -a 256) -c -)
if [ "$pack" = zip ]; then unzip -q "build/nats/$name.$pack" -d build/nats; else tar -xzf "build/nats/$name.$pack" -C build/nats; fi
cp build/nats/"$name"/nats-server* build/engine/proki-engine/

cd ui
npm ci
# Signed with the certificate named in APPLE_SIGNING_IDENTITY when there is one (in a keychain, trusted for
# signing code: packaging/signing-cert.sh), so macOS keeps its permissions across releases; else ad hoc, as the release config says.
if [ -n "${APPLE_SIGNING_IDENTITY:-}" ]; then
  signed=(--config "{\"bundle\":{\"macOS\":{\"signingIdentity\":\"$APPLE_SIGNING_IDENTITY\"}}}")
else
  unset APPLE_SIGNING_IDENTITY   # set but empty: no secret
  signed=()
fi
CI=true npx tauri build --config app/tauri.release.json ${signed[@]+"${signed[@]}"} --bundles "$bundles"   # CI: the .dmg without asking Finder to lay out its window
if [ "$os" = darwin ]; then
  codesign --verify --deep --strict --verbose=2 app/target/release/bundle/macos/Proki.app
fi
