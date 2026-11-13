"""年ごとのDB（out/bf/yN/keirin.sqlite、backfill_to.py で取り込んだもの）から、判定用の表 out/yN/cache.pkl を作る（2026-11-13）。
prereg_full_2024.py の ②〜④ と同じスクリプトを、DB の場所（KDB）だけ変えて順に回す。表ができたら中間の tri.pkl は消す（ディスク節約・作り直せる）。
使い方: python -I -X utf8 research/build_year.py y9 20171108 20181107"""
import sys, os, subprocess, datetime as dt
K = "C:/Users/take0/.claude/keirin/"
tag, d0, d1 = sys.argv[1:4]; DB = K + f"out/bf/{tag}/keirin.sqlite"; O = K + f"out/{tag}/"; os.makedirs(O, exist_ok=True)
assert os.path.exists(DB), DB
def run(step, args, out):
    if os.path.exists(out): print(step, "できている", flush=True); return
    t = dt.datetime.now(); e = dict(os.environ, KDB=DB)
    r = subprocess.run([sys.executable, "-I", "-X", "utf8"] + args, cwd=K, env=e, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print(step, "rc", r.returncode, f"{(dt.datetime.now() - t).seconds}秒", (r.stdout or "").strip().splitlines()[-1:] , [l for l in (r.stderr or "").splitlines() if "Error" in l][-2:], flush=True)
    if r.returncode != 0 or not os.path.exists(out): sys.exit(1)
s0 = (dt.datetime.strptime(d0, "%Y%m%d") - dt.timedelta(days=75)).strftime("%Y%m%d")
run("2a 選手表", ["research/ana_build_small.py", d0, d1, O + "ana.pkl"], O + "ana.pkl")
run("2a+ 追加", ["research/ext_small.py", O + "ana.pkl", O + "ana_ext.pkl"], O + "ana_ext.pkl")
run("2b 3連単", ["research/tri3_build_small.py", O + "ana_ext.pkl", O + "tri.pkl"], O + "tri.pkl")
run("3 side", ["research/angle_side2.py", DB, s0, d1, tag], K + f"out/side_results_{tag}.pkl")
run("4 表", ["research/build_cache_period.py", O + "tri.pkl", f"_{tag}", O + "cache.pkl"], O + "cache.pkl")
os.remove(O + "tri.pkl"); print("完了", tag, flush=True)
