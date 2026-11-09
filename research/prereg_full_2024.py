"""事前登録 R・S・T・Y・Z を、まだ見ていない期間で一発で判定する段取り（2026-11-09 作成、11/10 18:00 の予約から呼ぶ）。
使い方: python -I -X utf8 research/prereg_full_2024.py [開始日 終了日 前半の最終日 名前] [--no-check] [--force]
既定: 20231108 20250131 20240615 y2024full（事前登録で決めた期間）
段取り：①取り込みの完了確認 → ②選手表・3連単の表（小分け読み込み）→ ③side（小分け）→ ④angle_base 形式の表 → ⑤機械 v2・D の予測 → ⑥判定の表
- できた分は飛ばす（途中で止まってもやり直せる）。--force で作り直し
- 取り込み中のDBは長く読まない（各スクリプトは小分け・休みを入れて読む）。最後に取り込みが生きているか確認する"""
import sys, os, re, subprocess, datetime as dt
K = "C:/Users/take0/.claude/keirin/"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
d0, d1, half, tag = (args + ["20231108", "20250131", "20240615", "y2024full"][len(args):])[:4] if len(args) < 4 else args[:4]
CHECK, FORCE = "--no-check" not in sys.argv, "--force" in sys.argv
OUTD = K + f"out/{tag}/"; os.makedirs(OUTD, exist_ok=True)
LOG = open(OUTD + "run.log", "a", encoding="utf-8")
def say(*a):
    msg = dt.datetime.now().strftime("%H:%M:%S ") + " ".join(str(x) for x in a); print(msg, flush=True); print(msg, file=LOG, flush=True)
def last_date(log):
    try:
        lines = [l for l in open(K + "logs/" + log, encoding="utf-8", errors="ignore") if re.match(r"^\d{8} ", l)]
        return lines[-1][:8] if lines else ""
    except FileNotFoundError:
        return ""
def run(step, cmd, out, env=None):
    if os.path.exists(out) and not FORCE:
        say(f"[{step}] できている：{out}"); return
    say(f"[{step}] 開始：{' '.join(cmd[2:])}")
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run([sys.executable, "-I", "-X", "utf8"] + cmd[2:], cwd=K, env=e, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    tail = (r.stdout or "").strip().splitlines()[-2:] + [l for l in (r.stderr or "").strip().splitlines() if "Error" in l or "Traceback" in l][-3:]
    say(f"[{step}] 終了 rc={r.returncode}：" + " / ".join(tail))
    if r.returncode != 0 or not os.path.exists(out):
        say(f"[{step}] 失敗。ここで止める"); sys.exit(1)
say(f"=== 期間 {d0}〜{d1}（前半〜{half}）名前 {tag} ===")
# ① 取り込みの完了確認（事前登録の期間 2023/11〜2025/1 は y2・y3）
if CHECK:
    y2, y3 = last_date("backfill_y2.log"), last_date("backfill_y3.log")
    say(f"[1] 取り込みの最後の日：y2={y2}（20250131 で完了）・y3={y3}（20240131 で完了）")
    if y2 < "20250131" or y3 < "20240131":
        say("[1] まだ取り込み中。終わってからもう一度実行する"); sys.exit(2)
PY = ["python", "-I"]
run("2a 選手表", PY + ["research/ana_build_small.py", d0, d1, OUTD + "ana.pkl"], OUTD + "ana.pkl")
run("2b 3連単の表", PY + ["research/tri3_build_small.py", OUTD + "ana.pkl", OUTD + "tri.pkl"], OUTD + "tri.pkl")
s0 = (dt.datetime.strptime(d0, "%Y%m%d") - dt.timedelta(days=75)).strftime("%Y%m%d")  # 得点の流れ（60日前）などのため少し前から
run("3 side", PY + ["research/angle_side2.py", K + "keirin.sqlite", s0, d1, tag], K + f"out/side_races_{tag}.pkl")
run("4 表", PY + ["research/build_cache_period.py", OUTD + "tri.pkl", f"_{tag}", OUTD + "cache.pkl"], OUTD + "cache.pkl")
run("5 予測", PY + ["research/z_predict_period.py", OUTD + "zpred.pkl"], OUTD + "zpred.pkl", env={"ANGLE_CACHE": OUTD + "cache.pkl", "SIDE_SUFFIX": f"_{tag}"})
rep = K + f"reports/prereg_{tag}.md"
if os.path.exists(rep) and not FORCE: os.remove(rep)
run("6 判定", PY + ["research/prereg_eval_full.py", OUTD + "cache.pkl", f"_{tag}", OUTD + "zpred.pkl", d0, d1, half, rep], rep)
# 取り込みが生きているか
try:
    ps = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*backfill.py*' }).CommandLine"], capture_output=True, text=True).stdout.strip()
    say("取り込み：", ps if ps else "動いていない（止まっていたら logs\\resume_backfill.bat で再開。勝手に再起動はしない）")
except Exception as e:
    say("取り込みの確認に失敗：", e)
say(f"=== 完了：{rep} ===")
