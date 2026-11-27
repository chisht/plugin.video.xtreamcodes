#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Writes the tiny solid-colour PNGs the skins use (no image library needed).

  python3 tools/make_media.py

Every skin folder needs the same files:
  white.png        a plain white pixel block, tinted with colordiffuse in the XML
  guide_btn.png    grid guide programme block
  guide_now.png    the programme airing now
  guide_focus.png  the focused programme
"""
import os
import struct
import zlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(HERE, 'resources', 'skins')

# skin -> {file: (size, rgba)}
FILES = {
    'stbemu': {
        'white.png': (8, (0xFF, 0xFF, 0xFF, 0xFF)),
        'guide_btn.png': (16, (0x1C, 0x1C, 0x1C, 0xFF)),
        'guide_now.png': (16, (0x2A, 0x22, 0x10, 0xFF)),
        'guide_focus.png': (16, (0xE0, 0x8A, 0x1E, 0xFF)),
    },
}


def png(size, rgba):
    row = b'\x00' + bytes(rgba) * size
    raw = row * size

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))


def main():
    for skin, files in FILES.items():
        folder = os.path.join(MEDIA, skin, 'media')
        os.makedirs(folder, exist_ok=True)
        for name, (size, rgba) in files.items():
            path = os.path.join(folder, name)
            with open(path, 'wb') as f:
                f.write(png(size, rgba))
            print('%s  %d bytes' % (path, os.path.getsize(path)))


if __name__ == '__main__':
    main()
