"""本番の記録での前向きの確認を、一発で最新にする（2026-11-09 作成）。
①本番DB（GitHub リリース db）をダウンロード → ②締切1分前（T1）の表を 11/7〜最新で作り直す → ③side（本番DB分）を作り直して side_*_full をまとめ直す
→ ④1分前の表（angle_base 形式）→ ⑤事前登録Z の前向き確認（機械 D・v2full）→ ⑥1分前の深い分析（買い方ごと）
使い方: python -I -X utf8 research/daily_forward.py   （本番DBのコピーを読むだけなので、取り込み中のローカルDBには触らない）"""
import os, sys, gzip, shutil, sqlite3, subprocess, datetime as dt
import pandas as pd
K = "C:/Users/take0/.claude/keirin/"; LDB = K + "out/live_db/keirin.sqlite"
def sh(cmd, env=None):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, cwd=K, env=e, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print(" ".join(cmd[-3:]), "→ rc", r.returncode, (r.stdout or "").strip().splitlines()[-1:] if r.stdout else "", flush=True)
    if r.returncode != 0: print((r.stderr or "")[-1500:]); sys.exit(1)
PY = [sys.executable, "-I", "-X", "utf8"]
# ① 本番DB
sh(["gh", "release", "download", "db", "-p", "keirin.sqlite.gz", "-D", K + "out/live_db", "--clobber"])
with gzip.open(K + "out/live_db/keirin.sqlite.gz", "rb") as f, open(LDB, "wb") as g: shutil.copyfileobj(f, g)
con = sqlite3.connect("file:" + LDB + "?mode=ro", uri=True)
days = [d for (d,) in con.execute("SELECT DISTINCT substr(race_id,-8) FROM payouts WHERE substr(race_id,-8) >= '20261107' ORDER BY 1")]
last = days[-1] if days else "20261107"; con.close()
print("本番DBの確定済みの最後の日:", last)
# ② 1分前の表
env = {"KDB": LDB, "KPH": "T1"}
sh(PY + [K + "research/ana_build.py", "20261107", last, K + "out/live_t1/ana.pkl"], env)
sh(PY + [K + "research/tri3_build.py", K + "out/live_t1/ana.pkl", K + "out/live_t1/tri.pkl"], env)
# ③ side（本番DB分）を作り直し、full をまとめ直す
sh(PY + [K + "research/angle_side2.py", LDB, "20261106", last, "live"])
for nm, keys in (("races", ["race_id"]), ("entries", ["race_id", "number"]), ("results", ["race_id", "rank", "number"])):
    pd.concat([pd.read_pickle(K + f"out/side_{nm}{s}.pkl") for s in ("", "_live", "_y2024a")]).drop_duplicates(keys, keep="last").to_pickle(K + f"out/side_{nm}_full.pkl")
# ④〜⑥
sh(PY + [K + "research/build_cache_period.py", K + "out/live_t1/tri.pkl", "_full", K + "out/angle_base_t1.pkl"])
sh(PY + [K + "research/z_forward.py", K + "reports/z_forward.md"], {"ANGLE_CACHE": K + "out/angle_base_t1.pkl"})
sh(PY + [K + "research/preclose_1min.py", K + "reports/preclose_1min.md"])
print("完了：reports/z_forward.md・reports/preclose_1min.md")
