#!/bin/sh
# Builds dist/plugin.video.xtreamcodes-<version>.zip, ready to install in Kodi.
set -e
cd "$(dirname "$0")"
ver=$(python3 -c "import xml.etree.ElementTree as E; print(E.parse('addon.xml').getroot().get('version'))")
rm -rf build && mkdir -p build/plugin.video.xtreamcodes dist
cp -r addon.xml main.py service.py icon.png fanart.jpg resources build/plugin.video.xtreamcodes/
find build -name __pycache__ -prune -exec rm -rf {} +
(cd build && zip -qr "../dist/plugin.video.xtreamcodes-$ver.zip" plugin.video.xtreamcodes)
rm -rf build
echo "dist/plugin.video.xtreamcodes-$ver.zip"
