"""事前登録 R・S・T・Y・Z を、まだ見ていない期間で一発で判定する段取り（2026-11-09 作成、11/10 18:00 の予約から呼ぶ）。
使い方: python -I -X utf8 research/prereg_full_2024.py [開始日 終了日 前半の最終日 名前] [--no-check] [--force]
既定: 20231108 20250131 20240615 y2024full（事前登録で決めた期間）
y4（事前登録 U・V・W・X・Z）: 20221108 20231107 20230508 y4 → ⑤のあと機械v1 の予測（X用）を作り、判定は prereg_eval_y4.py を使う。取り込み y4 が 20231107 まで終わっていないと止まる
段取り：①取り込みの完了確認 → ②選手表・3連単の表（小分け読み込み）→ ③side（小分け）→ ④angle_base 形式の表 → ⑤機械 v2・D の予測 → ⑥判定の表
- できた分は飛ばす（途中で止まってもやり直せる）。--force で作り直し
- 取り込み中のDBは長く読まない（各スクリプトは小分け・休みを入れて読む）。最後に取り込みが生きているか確認する"""
import sys, os, re, subprocess, datetime as dt
K = "C:/Users/take0/.claude/keirin/"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
d0, d1, half, tag = (args + ["20231108", "20250131", "20240615", "y2024full"][len(args):])[:4] if len(args) < 4 else args[:4]
CHECK, FORCE = "--no-check" not in sys.argv, "--force" in sys.argv
Y4 = ("20221108", "20231107")  # 事前登録 U・V・W・X・Z を判定する期間（KNOWLEDGE.md の登録どおり）
if (d0, d1) == Y4 and half != "20230508":
    print(f"y4 の前半の最終日は 20230508（365日を 182日・183日に2等分）。指定 {half} は登録の「日付で2等分」とずれるので止める"); sys.exit(2)
Y5 = ("20211108", "20221107")  # y5：下書き reports/y5_prereg_draft.md。正式な登録の前は、表と予測を作るところまでで止める
if (d0, d1) == Y5 and half != "20220508":
    print(f"y5 の前半の最終日は 20220508（182日・183日に2等分）。指定 {half} はずれるので止める"); sys.exit(2)
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
# ① 取り込みの完了確認：判定する期間に重なる取り込み（logs/resume_backfill.bat の期間）が、すべて最後の日まで終わっているか
#   （2026-11-11 Codex のレビューで、y2・y3 しか見ておらず y4 以降の期間では確認にならないと指摘 → 期間から選ぶ形に直した）
BACKFILL = {"backfill_y2.log": ("20240201", "20250131"), "backfill_y3.log": ("20231108", "20240131"),
            "backfill_y4.log": ("20221108", "20231107"), "backfill_y5.log": ("20211108", "20221107"), "backfill_y6.log": ("20201108", "20211107")}
if CHECK:
    need = {lg: e for lg, (s, e) in BACKFILL.items() if s <= d1 and e >= d0}
    if not need and d1 <= "20250131":
        say("[1] この期間に当てはまる取り込みのログがない。--no-check で動かす前に、取り込み済みか自分で確かめる"); sys.exit(2)
    got = {lg: last_date(lg) for lg in need}
    say("[1] 取り込みの最後の日：" + "・".join(f"{lg[9:11]}={got[lg] or 'なし'}（{e} で完了）" for lg, e in need.items()))
    if any(got[lg] < e for lg, e in need.items()):
        say("[1] まだ取り込み中。終わってからもう一度実行する"); sys.exit(2)
PY = ["python", "-I"]
run("2a 選手表", PY + ["research/ana_build_small.py", d0, d1, OUTD + "ana.pkl"], OUTD + "ana.pkl")
# 2a+ 直近の着順・番狂わせの履歴（機械の特徴量）を足す。2026-11-11 まで飛ばしていて、機械の重み16〜25%の特徴量が空だった
run("2a+ 追加の手がかり", PY + ["research/ext_small.py", OUTD + "ana.pkl", OUTD + "ana_ext.pkl"], OUTD + "ana_ext.pkl")
run("2b 3連単の表", PY + ["research/tri3_build_small.py", OUTD + "ana_ext.pkl", OUTD + "tri.pkl"], OUTD + "tri.pkl")
s0 = (dt.datetime.strptime(d0, "%Y%m%d") - dt.timedelta(days=75)).strftime("%Y%m%d")  # 得点の流れ（60日前）などのため少し前から
# 完了の印は最後に書く results（angle_side2.py は races → entries → results の順に書く。途中で止まると races だけ残るため。2026-11-11 Codex の指摘）
run("3 side", PY + ["research/angle_side2.py", K + "keirin.sqlite", s0, d1, tag], K + f"out/side_results_{tag}.pkl")
run("4 表", PY + ["research/build_cache_period.py", OUTD + "tri.pkl", f"_{tag}", OUTD + "cache.pkl"], OUTD + "cache.pkl")
run("5 予測", PY + ["research/z_predict_period.py", OUTD + "zpred.pkl"], OUTD + "zpred.pkl", env={"ANGLE_CACHE": OUTD + "cache.pkl", "SIDE_SUFFIX": f"_{tag}"})
rep = K + f"reports/prereg_{tag}.md"
if (d0, d1) == Y5:
    # 2026-11-11 15:50 ★事前登録（y5）「案A」（KNOWLEDGE.md）：① 一番の目（全体）・⑥ 400mの一番の目×弱い3着、BH の m=2。登録どおり判定まで自動で回す
    # 報告は out/y5/staging/ に書いてから reports/ に移す（途中で失敗しても判定が見える状態で止まらない）
    import shutil
    STG = OUTD + "staging/"
    if os.path.isdir(STG) and not os.path.exists(STG + "DONE"): shutil.rmtree(STG)
    os.makedirs(STG, exist_ok=True)
    if os.path.exists(rep) and not FORCE: os.remove(rep)
    run("6 判定（y5・案A）", PY + ["research/prereg_eval_y5.py", OUTD + "cache.pkl", f"_{tag}", d0, d1, half, "2", STG + "main.md", "--plan=A"], STG + "main.md")
    # 2026-11-11 18:00 ★事前登録（y5）「ライン順×最下位級の3着」（L1・L2、別の組・BH の m=2）
    rep_lo = K + f"reports/prereg_{tag}_lo.md"
    if os.path.exists(rep_lo) and not FORCE: os.remove(rep_lo)
    run("6d 判定（y5・ライン順×最下位級の3着）", PY + ["research/prereg_eval_y5_lo.py", OUTD + "cache.pkl", d0, d1, half, STG + "lo.md"], STG + "lo.md")
    shutil.copyfile(STG + "main.md", rep); shutil.copyfile(STG + "lo.md", rep_lo); open(STG + "DONE", "w").close()
    say(f"[6] 判定の報告を reports/ に移した：{os.path.basename(rep)}・{os.path.basename(rep_lo)}（「5・6年目まとめて」は y6 の後に別に回す）")
    sys.exit(0)
Y6 = ("20201108", "20211107")
if (d0, d1) == Y6:
    # 2026-11-12：y6 の判定。★「ライン順の機械・4年版」（y6 だけ・m=2）と ★「5・6年目まとめて（ライン順）」（y5＋y6・m=4）を登録どおり回す。
    # 別セッションの「5・6年目まとめて」（一番の目の絞り込み、prereg_y56_pool_run.py）はここでは回さない（同時に回すと out/y5・out/y6 がぶつかるので、この後に別に回す）
    import shutil
    if half != "20210508": say(f"y6 の前半の最終日は 20210508。指定 {half} はずれるので止める"); sys.exit(2)
    STG = OUTD + "staging/"
    if os.path.isdir(STG) and not os.path.exists(STG + "DONE"): shutil.rmtree(STG)
    os.makedirs(STG, exist_ok=True)
    finals = {STG + "lo4.md": K + "reports/prereg_y6_lo4.md", STG + "y56_lo.md": K + "reports/prereg_y56_lo.md", STG + "ev.md": K + "reports/prereg_y6_ev.md"}
    for dst in finals.values():
        if os.path.exists(dst) and not FORCE: os.remove(dst)
    run("6 判定（y6・ライン順の機械・4年版）", PY + ["research/prereg_eval_y6_lo4.py", OUTD + "cache.pkl", d0, d1, half, STG + "lo4.md"], STG + "lo4.md")
    run("6b 判定（5・6年目まとめて・ライン順）", PY + ["research/prereg_eval_y56_lo.py", K + "out/y5/cache.pkl", "20211108", "20221107", OUTD + "cache.pkl", d0, d1, STG + "y56_lo.md"], STG + "y56_lo.md")
    # 2026-11-12 夜：★「ライン順の機械・期待値の線と配分」（E1〜E3、5年まとめ・m=3）も登録どおり回す
    run("6c 判定（y6・期待値の線と配分）", PY + ["research/prereg_eval_y6_ev.py", OUTD + "cache.pkl", d0, d1, half, STG + "ev.md"], STG + "ev.md")
    for src, dst in finals.items(): shutil.copyfile(src, dst)
    open(STG + "DONE", "w").close()
    say("[6] 判定の報告を reports/ に移した：prereg_y6_lo4.md・prereg_y56_lo.md・prereg_y6_ev.md（別セッションの「5・6年目まとめて」は prereg_y56_pool_run.py で後から回す）")
    sys.exit(0)
if os.path.exists(rep) and not FORCE: os.remove(rep)
if (d0, d1) == Y4:
    # y4 は事前登録 U・V・W・X・Z の判定。X 用に機械v1 の予測も作る（作らないと X が「未判定」になる）
    run("5b 予測（機械v1・X用）", PY + ["research/x_predict_period.py", OUTD + "xpred.pkl"], OUTD + "xpred.pkl", env={"ANGLE_CACHE": OUTD + "cache.pkl", "SIDE_SUFFIX": f"_{tag}"})
    # 判定の報告は、いったん out/y4/staging/ に書き、3つ全部そろってから reports/ に移す（途中で失敗したとき、先にできた判定が見える状態で止まらないため。2026-11-11 Codex の指摘）
    # 途中で止まったら staging の中は開かずに原因を直し、staging を消してからやり直す
    import shutil
    STG = OUTD + "staging/"
    if os.path.isdir(STG) and not os.path.exists(STG + "DONE"): shutil.rmtree(STG)  # 前回の途中の分は見ずに消す
    os.makedirs(STG, exist_ok=True)
    finals = {STG + "main.md": rep, STG + "avoid.md": K + f"reports/prereg_{tag}_avoid.md", STG + "weak3.md": K + f"reports/prereg_{tag}_weak3.md"}
    for dst in finals.values():  # 専用の報告も毎回作り直す（残っていると古い結果が残る）
        if os.path.exists(dst) and not FORCE: os.remove(dst)
    run("6 判定（y4）", PY + ["research/prereg_eval_y4.py", OUTD + "cache.pkl", f"_{tag}", OUTD + "zpred.pkl", d0, d1, half, STG + "main.md", OUTD + "xpred.pkl"], STG + "main.md")
    # 事前登録「一番の目×割高な目を外す」（2026-11-11 2:25 登録・y4 を見る前）。別の表・BH は m=1
    run("6c 判定（y4・一番の目×割高な目を外す）", PY + ["research/prereg_eval_y4_avoid.py", OUTD + "cache.pkl", f"_{tag}", d0, d1, half, STG + "avoid.md"], STG + "avoid.md")
    # 事前登録「弱い3着」2つ（2026-11-11 0:50 登録・y4 を見る前）。U〜Z とは別の表・別の BH 補正
    run("6b 判定（y4・弱い3着）", PY + ["research/prereg_eval_y4_weak3.py", OUTD + "cache.pkl", f"_{tag}", d0, d1, half, STG + "weak3.md"], STG + "weak3.md")
    for src, dst in finals.items(): shutil.copyfile(src, dst)
    open(STG + "DONE", "w").close()
    say("[6] 判定の報告3つを reports/ に移した：" + "、".join(os.path.basename(d) for d in finals.values()))
else:
    run("6 判定", PY + ["research/prereg_eval_full.py", OUTD + "cache.pkl", f"_{tag}", OUTD + "zpred.pkl", d0, d1, half, rep], rep)
# 取り込みが生きているか
try:
    ps = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*backfill.py*' }).CommandLine"], capture_output=True, text=True).stdout.strip()
    say("取り込み：", ps if ps else "動いていない（止まっていたら logs\\resume_backfill.bat で再開。勝手に再起動はしない）")
except Exception as e:
    say("取り込みの確認に失敗：", e)
say(f"=== 完了：{rep} ===")
