#!/usr/bin/env python3
"""Channel-change timings from a Kodi log (no log content is printed).

    python3 tools/log_timing.py kodi.log [more.log ...]

Phases per channel change, median / max in seconds:
  add-on      key handled / channel chosen -> Kodi asked to play (OpenFile)
  close old   OpenFile -> new input stream created (Kodi closing the previous stream)
  connect     input stream -> demuxer (HTTP connection to the provider)
  probe       demuxer -> decoder opened
  picture     decoder opened -> first picture (keyframe, buffering)
"""
import datetime
import re
import statistics
import sys

STAMP = re.compile(r'(\d+-\d+-\d+ \d+:\d+:\d+\.\d+)')
PHASES = [('key', 'open', 'add-on'), ('open', 'input', 'close old'), ('input', 'demux', 'connect'),
          ('demux', 'dec', 'probe'), ('dec', 'pic', 'picture'), ('key', 'pic', 'TOTAL')]


def stamp(line):
    m = STAMP.match(line)
    return datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S.%f').timestamp() if m else None


def changes(path):
    rows, cur = [], None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            t = stamp(line)
            if t is None:
                continue
            if 'xtreamcodes] Channel change to' in line or 'xtreamcodes] Opening ' in line:
                cur = {'key': t}
            elif cur is None:
                continue
            elif 'VideoPlayer::OpenFile' in line and '/timeshift/' not in line:
                cur.setdefault('open', t)
            elif 'Creating InputStream' in line:
                cur.setdefault('input', t)
            elif 'Creating Demuxer' in line:
                cur.setdefault('demux', t)
            elif 'Open decoder' in line:
                cur.setdefault('dec', t)
            elif 'Picture on screen' in line:
                cur['pic'] = t
                if all(k in cur for k in ('open', 'input', 'demux', 'dec')):
                    rows.append(cur)
                cur = None
    return rows


def main(paths):
    for path in paths:
        rows = changes(path)
        print('%s: %d channel changes' % (path, len(rows)))
        if not rows:
            continue
        for a, b, name in PHASES:
            vals = [r[b] - r[a] for r in rows]
            print('  %-10s %5.2f / %5.2f' % (name, statistics.median(vals), max(vals)))


if __name__ == '__main__':
    main(sys.argv[1:] or sys.exit(__doc__))
