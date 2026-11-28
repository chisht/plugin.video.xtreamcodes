#!/usr/bin/env python3
"""Build the Kodi repository files into repo_out/ (default outdir).

Layout produced (served from the `kodi-repo` branch):
  addons.xml, addons.xml.md5, index.html
  zips/<id>/<id>-<version>.zip (+ .sha256), icon.png, fanart.jpg
  repository.chisht.zip  (stable name, for the first install)

Existing zips in <outdir>/zips are kept, so older versions stay available.
`main(outdir)` is the entry point; `tools/release_repo.py` calls it and pushes
the result to the repository branch.
"""
import hashlib
import os
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True

# addon id -> (source dir, files/dirs to package)
ADDONS = {
    "plugin.video.xtreamcodes": (
        ROOT, ["addon.xml", "main.py", "service.py", "icon.png", "fanart.jpg", "resources"]),
    "repository.chisht": (
        os.path.join(ROOT, "repository.chisht"), ["addon.xml", "icon.png", "fanart.jpg"]),
}
SKIP_DIRS = {"__pycache__"}
SKIP_EXT = {".pyc", ".pyo"}


def iter_files(src, entries):
    for entry in entries:
        path = os.path.join(src, entry)
        if os.path.isfile(path):
            yield path, entry
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                if os.path.splitext(name)[1] in SKIP_EXT:
                    continue
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(full, src)


def make_zip(addon_id, src, entries, dest):
    # fixed timestamps so an unchanged add-on gives an identical zip
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, rel in iter_files(src, entries):
            info = zipfile.ZipInfo(f"{addon_id}/{rel.replace(os.sep, '/')}", (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                zf.writestr(info, fh.read())


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(outdir=None):
    OUT = outdir or os.path.join(ROOT, "repo_out")
    os.makedirs(OUT, exist_ok=True)
    xml_parts = []
    for addon_id, (src, entries) in ADDONS.items():
        tree = ET.parse(os.path.join(src, "addon.xml"))
        root = tree.getroot()
        if root.get("id") != addon_id:
            sys.exit(f"{src}/addon.xml has id {root.get('id')!r}, expected {addon_id!r}")
        version = root.get("version")
        zdir = os.path.join(OUT, "zips", addon_id)
        os.makedirs(zdir, exist_ok=True)
        zpath = os.path.join(zdir, f"{addon_id}-{version}.zip")
        make_zip(addon_id, src, entries, zpath)
        with open(zpath + ".sha256", "w") as fh:
            fh.write(sha256(zpath))
        for asset in ("icon.png", "fanart.jpg"):
            shutil.copy2(os.path.join(src, asset), os.path.join(zdir, asset))
        if addon_id.startswith("repository."):
            shutil.copy2(zpath, os.path.join(OUT, f"{addon_id}.zip"))
        with open(os.path.join(src, "addon.xml"), encoding="utf-8") as fh:
            text = fh.read()
        xml_parts.append(text[text.index("<addon"):].strip())
        print(f"{addon_id} {version}")

    addons_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
                  + "\n".join(xml_parts) + "\n</addons>\n")
    with open(os.path.join(OUT, "addons.xml"), "w", encoding="utf-8") as fh:
        fh.write(addons_xml)
    with open(os.path.join(OUT, "addons.xml.md5"), "w") as fh:
        fh.write(hashlib.md5(addons_xml.encode("utf-8")).hexdigest())
    with open(os.path.join(OUT, "index.html"), "w") as fh:
        fh.write('<!DOCTYPE html>\n<html><body>\n'
                 '<a href="repository.chisht.zip">repository.chisht.zip</a>\n'
                 '</body></html>\n')
    print(f"written to {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
