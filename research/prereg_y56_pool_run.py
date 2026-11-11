"""★事前登録「5・6年目まとめて」の段取り（2026-11-11 登録）。y5・y6 の取り込みが終わってから実行：
  python -I -X utf8 research/prereg_y56_pool_run.py
y5・y6 それぞれ 選手表→3連単の表→side→表 を作り（prereg_full_2024.py の②〜④と同じスクリプト・同じ置き場所 out/y5・out/y6）、
research/prereg_eval_y56_pool.py で判定 → reports/prereg_y56_pool.md。ほかの登録の判定は回さない（y5 で別に登録するものの結果を先に見ないため）。
できた分は飛ばす。取り込みが終わっていなければ終了コード 2"""
import sys, os, re, subprocess, datetime as dt
K = "C:/Users/take0/.claude/keirin/"
P = {"y5": ("20211108", "20221107", "backfill_y5.log"), "y6": ("20201108", "20211107", "backfill_y6.log")}
def say(*a): print(dt.datetime.now().strftime("%H:%M:%S"), *a, flush=True)
def last(log):
    try: L = [l for l in open(K + "logs/" + log, encoding="utf-8", errors="ignore") if re.match(r"^\d{8} ", l)]; return L[-1][:8] if L else ""
    except FileNotFoundError: return ""
for tag, (d0, d1, log) in P.items():
    if last(log) < d1: say(f"{tag} の取り込みがまだ（最後 {last(log) or 'なし'}／{d1} で完了）"); sys.exit(2)
def run(cmd, out, env=None):
    if os.path.exists(out): say("できている", out); return
    e = dict(os.environ); e.update(env or {}); say("開始", " ".join(cmd))
    r = subprocess.run([sys.executable, "-I", "-X", "utf8"] + cmd, cwd=K, env=e)
    if r.returncode != 0 or not os.path.exists(out): say("失敗", cmd); sys.exit(1)
for tag, (d0, d1, _) in P.items():
    O = K + f"out/{tag}/"; os.makedirs(O, exist_ok=True)
    run(["research/ana_build_small.py", d0, d1, O + "ana.pkl"], O + "ana.pkl")
    run(["research/tri3_build_small.py", O + "ana.pkl", O + "tri.pkl"], O + "tri.pkl")
    s0 = (dt.datetime.strptime(d0, "%Y%m%d") - dt.timedelta(days=75)).strftime("%Y%m%d")
    run(["research/angle_side2.py", K + "keirin.sqlite", s0, d1, tag], K + f"out/side_races_{tag}.pkl")
    run(["research/build_cache_period.py", O + "tri.pkl", f"_{tag}", O + "cache.pkl"], O + "cache.pkl")
rep = K + "reports/prereg_y56_pool.md"
run(["research/prereg_eval_y56_pool.py", K + "out/y5/cache.pkl", "_y5", *P["y5"][:2], K + "out/y6/cache.pkl", "_y6", *P["y6"][:2], rep], rep)
say("完了", rep)
