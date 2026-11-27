# -*- coding: utf-8 -*-
"""XMLTV -> SQLite, streamed so large guides don't exhaust memory."""
import calendar
import datetime
import gzip
import http.client
import os
import sqlite3
import threading
import time
import uuid
import xml.etree.ElementTree as ET
import zlib

from . import common

SCHEMA = """
CREATE TABLE channels(id TEXT PRIMARY KEY, name TEXT, icon TEXT);
CREATE TABLE programmes(channel TEXT, start INTEGER, stop INTEGER, title TEXT,
                        subtitle TEXT, descr TEXT, category TEXT, icon TEXT);
"""


def parse_time(value):
    """'20240101100000 +0100' -> UTC epoch seconds."""
    value = (value or '').strip()
    if len(value) < 12:
        return None
    try:
        dt = datetime.datetime.strptime(value[:14].ljust(14, '0'), '%Y%m%d%H%M%S')
    except ValueError:
        return None
    ts = calendar.timegm(dt.timetuple())
    rest = value[14:].strip()
    if len(rest) >= 5 and rest[0] in '+-' and rest[1:5].isdigit():
        offset = int(rest[1:3]) * 3600 + int(rest[3:5]) * 60
        ts += -offset if rest[0] == '+' else offset
    return ts


def _text(elem, tag):
    child = elem.find(tag)
    return (child.text or '').strip() if child is not None and child.text else ''


def _lower_priority():
    """Run this (service) thread at low CPU priority on Linux."""
    try:
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 15)
    except (AttributeError, OSError):
        pass


def _ui_busy():
    """Something the user is looking at: give it more room."""
    try:
        import xbmc
        import xbmcgui
        return bool(xbmcgui.Window(10000).getProperty(common.PROP_UI_OPEN)) or xbmc.Player().isPlaying()
    except Exception:
        return False


class StreamError(Exception):
    """Reading the guide from the network failed part-way (not a storage error)."""


# a guide cut off or garbled in transit (gzip complains in its own ways)
STREAM_ERRORS = (StreamError, EOFError, gzip.BadGzipFile, zlib.error)


class _Reader(object):
    """Counts bytes read and lets us peek at the first ones, for a file or a
    network stream alike (a stream cannot seek back after the gzip check)."""

    def __init__(self, raw):
        self.raw = raw
        self.pos = 0
        self._head = b''

    def _raw_read(self, n=-1):
        try:
            return self.raw.read(n) if n is not None and n >= 0 else self.raw.read()
        except (OSError, http.client.HTTPException) as e:
            raise StreamError(str(e) or e.__class__.__name__)

    def peek(self, n):
        while len(self._head) < n:
            chunk = self._raw_read(n - len(self._head))
            if not chunk:
                break
            self._head += chunk
        return self._head[:n]

    def read(self, n=-1):
        if n is None or n < 0:
            data, self._head = self._head + self._raw_read(), b''
        elif self._head:
            data, self._head = self._head[:n], self._head[n:]
            if len(data) < n:
                data += self._raw_read(n - len(data))
        else:
            data = self._raw_read(n)
        self.pos += len(data)
        return data

    def close(self):
        self.raw.close()


def build_db(xml_src, db_path, past_days=7, progress=None, abort=None, offset_min=0, total=0):
    """Build the guide database from XMLTV (plain or gzip).

    xml_src: a file path, or a binary stream such as the HTTP response itself, so
    the guide never has to be written to storage first (`total` = its size in
    bytes if known, for progress).
    """
    # A big guide (hundreds of thousands of programmes) keeps Python busy for
    # minutes. Kodi's add-ons share one interpreter, so without pauses every
    # other add-on (including TV mode) becomes very slow meanwhile.
    _lower_priority()
    pause_at = 1000
    shift = int(offset_min) * 60   # user correction for guides that are off
    if isinstance(xml_src, str):
        total = os.path.getsize(xml_src)
        xml_src = open(xml_src, 'rb')
    raw = _Reader(xml_src)
    size = total or 0
    gz = raw.peek(2) == b'\x1f\x8b'
    src = gzip.GzipFile(fileobj=raw) if gz else raw

    tmp = '%s.%s.tmp' % (db_path, uuid.uuid4().hex[:8])
    con = sqlite3.connect(tmp)
    con.execute('PRAGMA journal_mode=OFF')
    con.execute('PRAGMA synchronous=OFF')
    con.executescript(SCHEMA)

    cutoff = int(time.time()) - past_days * 86400
    batch = []
    count = 0
    root = None
    last = 0
    try:
        for event, elem in ET.iterparse(src, events=('start', 'end')):
            if root is None:
                root = elem
            if event != 'end':
                continue
            tag = elem.tag
            if tag == 'programme':
                start = parse_time(elem.get('start'))
                stop = parse_time(elem.get('stop'))
                if start is not None and shift:
                    start += shift
                    stop = stop + shift if stop is not None else None
                if start is not None:
                    if stop is None or stop <= start:
                        stop = start + 1800
                    if stop >= cutoff:
                        icon = elem.find('icon')
                        batch.append((
                            (elem.get('channel') or '').strip().lower(), start, stop,
                            _text(elem, 'title'), _text(elem, 'sub-title'),
                            _text(elem, 'desc'), _text(elem, 'category'),
                            icon.get('src', '') if icon is not None else ''))
                root.clear()
                pause_at -= 1
                if pause_at <= 0:
                    pause_at = 1000
                    time.sleep(0.08 if _ui_busy() else 0.01)
                if len(batch) >= 5000:
                    con.executemany('INSERT INTO programmes VALUES (?,?,?,?,?,?,?,?)', batch)
                    count += len(batch)
                    batch = []
                    if abort and abort():
                        raise common.Aborted()
                    if progress and time.time() - last > 1:
                        last = time.time()
                        progress(int(raw.pos * 100 / size) if size else 0,
                                 'Processing EPG: %d programmes (%.1f MB)'
                                 % (count, raw.pos / 1048576.0))
            elif tag == 'channel':
                icon = elem.find('icon')
                con.execute('INSERT OR IGNORE INTO channels VALUES (?,?,?)', (
                    (elem.get('id') or '').strip().lower(), _text(elem, 'display-name'),
                    icon.get('src', '') if icon is not None else ''))
                root.clear()
        if batch:
            con.executemany('INSERT INTO programmes VALUES (?,?,?,?,?,?,?,?)', batch)
            count += len(batch)
        if progress:
            progress(99, 'Indexing EPG...')
        con.execute('CREATE INDEX i_prog ON programmes(channel, start)')
        con.commit()
    except ET.ParseError as e:
        con.close()
        os.remove(tmp)
        raise ValueError('EPG is not valid XMLTV: %s' % e)
    except BaseException:
        con.close()
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    finally:
        if src is not raw:
            src.close()
        raw.close()
    con.close()
    common.atomic_replace(tmp, db_path)
    return count


MAX_LEN = 24 * 3600   # longest programme we expect; bounds index scans


class EPG(object):
    def __init__(self, path):
        self.ok = os.path.exists(path)
        self._con = None
        if self.ok:
            try:
                self._con = sqlite3.connect(path, check_same_thread=False)
                self._con.row_factory = sqlite3.Row
            except sqlite3.Error:
                self.ok = False

    def close(self):
        if self._con is not None:
            self._con.close()
            self._con = None

    def now_next(self, channel_ids, count=2):
        """{channel_id: [prog, ...]} for current and upcoming programmes."""
        result = {}
        if not self.ok:
            return result
        ids = sorted({(c or '').lower() for c in channel_ids if c})
        now = int(time.time())
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            # The lower bound on start keeps the index scan short: without it every
            # past programme of the channel (days of catch-up) is read from disk.
            sql = ('SELECT * FROM programmes WHERE channel IN (%s) AND start > ? AND stop > ? '
                   'AND start < ? ORDER BY channel, start' % ','.join('?' * len(chunk)))
            for row in self._con.execute(sql, chunk + [now - MAX_LEN, now, now + 12 * 3600]):
                lst = result.setdefault(row['channel'], [])
                if len(lst) < count:
                    lst.append(dict(row))
        return result

    def listings(self, channel_id, start, end):
        if not self.ok or not channel_id:
            return []
        rows = self._con.execute(
            'SELECT * FROM programmes WHERE channel=? AND start > ? AND stop > ? AND start < ? '
            'ORDER BY start', (channel_id.lower(), start - MAX_LEN, start, end))
        return [dict(r) for r in rows]

    def search(self, term, since, limit=300):
        if not self.ok:
            return []
        rows = self._con.execute(
            'SELECT * FROM programmes WHERE title LIKE ? AND stop > ? ORDER BY start LIMIT ?',
            ('%' + term + '%', since, limit))
        return [dict(r) for r in rows]

    def programme_count(self):
        if not self.ok:
            return 0
        return self._con.execute('SELECT COUNT(*) FROM programmes').fetchone()[0]
