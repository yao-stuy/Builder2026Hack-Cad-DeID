#!/usr/bin/env python3
"""Fast resumable downloader for the Machina input.

Usage: fetch.py MANIFEST.tsv DEST_DIR [THREADS]

Reads the organizer manifest and fetches every file that does not already have
the manifest size. Primary source is the public S3 bucket named in
challenge.pdf (anonymous HTTPS, about 1.4 MB/s per connection here); the
Builders mirror (about 0.2 MB/s per connection) is the fallback. Large files
are fetched as parallel byte ranges. One persistent connection per thread and
host. Stdlib only.
"""
import http.client
import os
import queue
import random
import sys
import threading
import time
import urllib.parse
import zlib

S3_HOST = "machina-deid-v1-challenge.s3.us-west-2.amazonaws.com"
S3_PREFIX = "/releases/v1/corpus/"
MIRROR_HOST = "machina-input.joinbuilders.org"
PART = 24 << 20
PRIMARY = os.environ.get("FETCH_PRIMARY", "s3")          # "s3" or "mirror"
SHARD = os.environ.get("FETCH_SHARD", "0/1")             # "k/n": only files with crc32(path) % n == k


def load(manifest, dest):
    todo, have = [], 0
    for line in open(manifest, encoding="utf-8", errors="surrogateescape"):
        if line.startswith("#"):
            continue
        a = line.rstrip("\n").split("\t")
        if len(a) < 4:
            continue
        path, size, url = a[0], int(a[1]), a[3]
        fp = os.path.join(dest, path)
        try:
            if os.path.getsize(fp) == size:
                have += 1
                continue
        except OSError:
            pass
        k, n = (int(x) for x in SHARD.split("/"))
        if zlib.crc32(path.encode("utf-8", "surrogateescape")) % n != k:
            continue
        todo.append((path, size, url))
    return todo, have


class FileState:
    __slots__ = ("path", "size", "url", "left", "lock", "ready", "failed")

    def __init__(self, path, size, url, nparts):
        self.path, self.size, self.url = path, size, url
        self.left = nparts
        self.lock = threading.Lock()
        self.ready = False
        self.failed = False


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.files = 0
        self.bytes = 0
        self.fail = 0
        self.mirror = 0


def fetch_range(conns, host, upath, off, length, whole, fd, st):
    conn = conns.get(host)
    if conn is None:
        conn = conns[host] = http.client.HTTPSConnection(host, timeout=120)
    headers = {"User-Agent": "fetch.py"}
    if not whole:
        headers["Range"] = f"bytes={off}-{off + length - 1}"
    conn.request("GET", upath, headers=headers)
    r = conn.getresponse()
    if r.status not in (200, 206) or (not whole and r.status != 206):
        r.read()
        raise RuntimeError(f"HTTP {r.status}")
    pos, got = off, 0
    while True:
        chunk = r.read(1 << 20)
        if not chunk:
            break
        os.pwrite(fd, chunk, pos)
        pos += len(chunk)
        got += len(chunk)
        with st.lock:
            st.bytes += len(chunk)
    if got != length:
        raise RuntimeError(f"short read {got} != {length}")


def worker(q, dest, st, errlog):
    conns = {}
    while True:
        try:
            fs, off, length = q.get_nowait()
        except queue.Empty:
            return
        fp = os.path.join(dest, fs.path)
        tmp = fp + ".part~"
        with fs.lock:
            if not fs.ready:
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(tmp, "wb") as f:
                    f.truncate(fs.size)
                fs.ready = True
        whole = length == fs.size
        s3path = S3_PREFIX + urllib.parse.quote(fs.path.encode("utf-8", "surrogateescape"), safe="/")
        mpath = "/" + fs.url
        try:
            mpath.encode("ascii")
        except UnicodeError:
            mpath = "/" + urllib.parse.quote(fs.url.encode("utf-8", "surrogateescape"), safe="/%")
        ok, err = False, ""
        fd = os.open(tmp, os.O_WRONLY)
        try:
            for attempt in range(7):
                first = attempt < 4
                if (PRIMARY == "s3") == first:
                    host, upath = S3_HOST, s3path
                else:
                    host, upath = MIRROR_HOST, mpath
                try:
                    fetch_range(conns, host, upath, off, length, whole, fd, st)
                    ok = True
                    if not first:
                        with st.lock:
                            st.mirror += 1
                    break
                except Exception as e:  # noqa: BLE001 - retry anything
                    err = f"{host}: {e!r}"
                    c = conns.pop(host, None)
                    try:
                        if c is not None:
                            c.close()
                    except Exception:  # noqa: BLE001
                        pass
                    time.sleep(min(20, 1.5 ** attempt))
        finally:
            os.close(fd)
        with fs.lock:
            if not ok:
                fs.failed = True
            fs.left -= 1
            done = fs.left == 0
            failed = fs.failed
        if done:
            with st.lock:
                if failed:
                    st.fail += 1
                    errlog.write(f"{fs.path}\t{err}\n")
                    errlog.flush()
                else:
                    st.files += 1
            if not failed:
                os.replace(tmp, fp)


def main():
    manifest, dest = sys.argv[1], sys.argv[2]
    nthreads = int(sys.argv[3]) if len(sys.argv) > 3 else 96
    todo, have = load(manifest, dest)
    total_b = sum(t[1] for t in todo)
    print(f"have {have} files; to fetch {len(todo)} files, {total_b / 1e9:.1f} GB", flush=True)
    os.makedirs(dest, exist_ok=True)
    st = Stats()
    jobs = []
    for path, size, url in todo:
        if size == 0:
            fp = os.path.join(dest, path)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            open(fp, "wb").close()
            st.files += 1
            continue
        nparts = max(1, -(-size // PART))
        fs = FileState(path, size, url, nparts)
        for i in range(nparts):
            off = i * PART
            jobs.append((fs, off, min(PART, size - off)))
    random.Random(1).shuffle(jobs)  # mixed sample of every file type early
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    errlog = open(os.path.join(dest, f".fetch-errors-{PRIMARY}.tsv"), "a", encoding="utf-8", errors="surrogateescape")
    threads = [threading.Thread(target=worker, args=(q, dest, st, errlog), daemon=True) for _ in range(nthreads)]
    for t in threads:
        t.start()
    t0 = time.time()
    last_b = 0
    while any(t.is_alive() for t in threads):
        time.sleep(60)
        with st.lock:
            f, b, fl, mi = st.files, st.bytes, st.fail, st.mirror
        print(f"{time.strftime('%H:%M:%S')} files {f}/{len(todo)} bytes {b / 1e9:.1f}/{total_b / 1e9:.1f} GB "
              f"rate {(b - last_b) / 60e6:.1f} MB/s failed {fl} via-fallback {mi}", flush=True)
        last_b = b
    print(f"DONE files {st.files} failed {st.fail} in {(time.time() - t0) / 60:.1f} min", flush=True)
    sys.exit(1 if st.fail else 0)


if __name__ == "__main__":
    main()
