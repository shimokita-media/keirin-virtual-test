"""サーバーへ持っていく keirin_deploy.tar.gz を作る（PC側で実行）。
- keirin.sqlite は SQLite のバックアップ機能でコピーするため、ループ稼働中でも壊れない
- logs/ と out/ は含めない（サーバー側で作り直される）
使い方: python deploy/build_package.py  ->  deploy/keirin_deploy.tar.gz"""
import os
import sqlite3
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
CODE = ["kr.py", "run_day.py", "export.py", "history.py", "backfill.py", "notion_rows.py", "README.md",
        "tomorrow.json"]
DEPLOY = ["run_daily.sh", "requirements.txt"]


def main():
    out = os.path.join(HERE, "keirin_deploy.tar.gz")
    with tempfile.TemporaryDirectory() as tmp:
        snap = os.path.join(tmp, "keirin.sqlite")
        src = sqlite3.connect(os.path.join(APP, "keirin.sqlite"), timeout=60)
        dst = sqlite3.connect(snap)
        src.backup(dst)
        n = dst.execute("SELECT COUNT(*) FROM races").fetchone()[0]
        p = dst.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        dst.close(); src.close()
        with tarfile.open(out, "w:gz") as tar:
            for f in CODE:
                if os.path.exists(os.path.join(APP, f)):
                    tar.add(os.path.join(APP, f), arcname=f)
            for f in DEPLOY:
                ti = tar.gettarinfo(os.path.join(HERE, f), arcname=f)
                ti.mode = 0o755 if f.endswith(".sh") else 0o644
                with open(os.path.join(HERE, f), "rb") as fh:
                    data = fh.read().replace(b"\r\n", b"\n")  # Windows 改行を除去
                import io
                ti.size = len(data)
                tar.addfile(ti, io.BytesIO(data))
            tar.add(snap, arcname="keirin.sqlite")
    print(f"{out}  {os.path.getsize(out)/1e6:.1f} MB  (races={n}, predictions={p})")


if __name__ == "__main__":
    main()
