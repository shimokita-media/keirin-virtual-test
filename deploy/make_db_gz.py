"""GitHub のリリースに置くデータベース（keirin.sqlite.gz）を作る。ループ稼働中でも安全にコピーする。"""
import gzip, os, shutil, sqlite3, tempfile
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with tempfile.TemporaryDirectory() as t:
    snap = os.path.join(t, "k.sqlite")
    s = sqlite3.connect(os.path.join(BASE, "keirin.sqlite"), timeout=60); d = sqlite3.connect(snap); s.backup(d); d.close(); s.close()
    with open(snap, "rb") as f, gzip.open(os.path.join(BASE, "keirin.sqlite.gz"), "wb", 6) as g:
        shutil.copyfileobj(f, g)
print("keirin.sqlite.gz", round(os.path.getsize(os.path.join(BASE, "keirin.sqlite.gz")) / 1e6, 1), "MB")
