#!/usr/bin/env bash
# Local one-shot build (Linux/macOS):  bash packaging/build.sh   → dist/ProTrader/ (+ ProTrader.app on macOS) and release/*.tar.gz|.dmg
set -e
cd "$(dirname "$0")/.."
python -m pip install -q -r requirements.txt pyinstaller pillow
python packaging/make_icons.py
pyinstaller --noconfirm protrader.spec
mkdir -p release
VER="${PT_VERSION:-$(git describe --tags --always 2>/dev/null || echo dev)}"
if [[ "$OSTYPE" == "darwin"* ]]; then
  hdiutil create -volname "ProTrader" -srcfolder dist/ProTrader.app -ov -format UDZO "release/ProTrader-$VER-macos.dmg"
else
  tar -C dist -czf "release/ProTrader-$VER-linux-x64.tar.gz" ProTrader
fi
echo "done → release/"
