"""固定した機械（ワイドの機械 wide_model.txt ＋ 倍率の下がりの機械 drift_model.txt、どちらも 2026-11-08 に固定）を、
11/9 以降の新しいレースで答え合わせする（機械は学び直さない＝本当の実力）。
使い方: python research/daily_eval.py   → reports/drift_live.md を更新
- クラウドの DB（リリース db）をダウンロードし、締切前の記録（T10/T5/B1R/T1）から買い目を選んで、確定の払戻で集計
- 仮想の事後計算のみ。予想記録（predictions）には一切触らない"""
import gzip, os, shutil, subprocess, sys
import numpy as np
import pandas as pd
import lightgbm as lgb

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
WORK = os.path.join(BASE, "out", "eval_work")
START = "20261109"
MIN = {"T10": 10, "T5": 5, "B1R": 2.7, "T1": 1}
DRIFT_FEATS = ["lodds", "mkt_gap", "ev", "pm", "mins", "sameF", "pop_w", "S", "entries_number", "a_pos", "b_pos", "a_mk_rank", "b_mk_rank", "lpw"]


def download():
    os.makedirs(WORK, exist_ok=True)
    subprocess.run(["gh", "release", "download", "db", "-R", "shimokita-media/keirin-virtual-test", "--clobber", "-D", WORK], check=True)
    with gzip.open(os.path.join(WORK, "keirin.sqlite.gz"), "rb") as f, open(os.path.join(WORK, "keirin.sqlite"), "wb") as g:
        shutil.copyfileobj(f, g)
    return os.path.join(WORK, "keirin.sqlite").replace("\\", "/")


def build(db, phase, end):
    env = dict(os.environ, KDB=db, KPH=phase, PYTHONIOENCODING="utf-8")
    a, w = os.path.join(WORK, f"ana_{phase}.pkl"), os.path.join(WORK, f"wide_{phase}.pkl")
    subprocess.run([sys.executable, os.path.join(HERE, "ana_build.py"), START, end, a], env=env, check=True, cwd=WORK, capture_output=True)
    subprocess.run([sys.executable, os.path.join(HERE, "wide_build.py"), a, w], env=env, check=True, cwd=WORK, capture_output=True)
    return pd.read_pickle(w)


wm = lgb.Booster(model_file=os.path.join(HERE, "wide_model.txt"))
dm = lgb.Booster(model_file=os.path.join(HERE, "drift_model.txt"))
CATS = {"a_style", "b_style", "grade", "class", "pp", "venue"}


def prep(W):
    W = W[(W.odds >= 1.5) & (W.odds <= 50)].copy()
    W["same"] = ((W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0)).astype(float)
    W["pp"] = W.a_pos.astype(int).astype(str) + W.b_pos.astype(int).astype(str)
    W["fin"] = W.race_type.astype(str).str.contains("決勝|準決").astype(int)
    W["lpw"] = np.log(W.pw.clip(1e-4, 0.999) / (1 - W.pw.clip(1e-4, 0.999)))
    W["lodds"] = np.log(W.odds); W["mkt_gap"] = np.log(W.odds * W.pw)
    for f in wm.feature_name():
        if f in CATS: W[f] = W[f].astype("category")
        elif W[f].dtype == bool or W[f].dtype == object: W[f] = W[f].astype(float)
    W["pm"] = 1 / (1 + np.exp(-(wm.predict(W[wm.feature_name()], raw_score=True) + W.lpw)))
    W["ev"] = W.pm * W.odds
    return W


def main():
    db = download()
    import sqlite3
    end = sqlite3.connect(db).execute("SELECT MAX(date) FROM races WHERE race_id IN (SELECT race_id FROM results)").fetchone()[0]
    if not end or end < START:
        print("まだ対象日なし"); return
    rows = []
    for ph, mins in MIN.items():
        W = build(db, ph, end)
        if not len(W): continue
        W = prep(W); W["ph"] = ph; W["mins"] = mins
        W["sameF"] = W.same; W["S"] = (W["class"].astype(str) == "S級").astype(float)
        W["pop_w"] = W.groupby("race_id").odds.rank()
        W["drift"] = dm.predict(W[DRIFT_FEATS].astype(float))
        W["ev_adj"] = W.pm * W.odds * np.exp(W.drift)
        rows.append(W)
    D = pd.concat(rows)
    L = [f"# 固定した機械の答え合わせ（{START}〜{end}・締切前の倍率で選択・各100円の事後計算）\n",
         "機械は 2026-11-08 に固定（この期間のデータは一度も学習に使っていない）。「下がり見込み」＝機械の見込み×締切前の倍率×予測した倍率の下がり。\n"]
    for ph in ("B1R", "T1", "T5", "T10"):
        X = D[D.ph == ph]
        if not len(X): continue
        L += [f"\n## {ph}（{X.race_id.nunique()}レース・{X.date.nunique()}日）\n", "| 選び方 | 点数 | 回収率 | 的中 |", "|---|---|---|---|"]
        for lab, m in [(f"下がり見込み≥{t}", X.ev_adj >= t) for t in (0.85, 0.9, 0.95, 1.0)] + [(f"締切前の割安≥{t}（比較）", X.ev >= t) for t in (1.1, 1.2)]:
            g = X[m]
            L.append(f"| {lab} | {len(g)} | {g.ret.mean():.0%} | {int((g.ret > 0).sum())}本 |" if len(g) else f"| {lab} | 0 | − | − |")
        g = X[X.ev_adj >= 0.95]
        if len(g):
            L.append("\n日ごと（下がり見込み≥0.95）：" + " ／ ".join(f"{d[4:6]}/{d[6:]} {len(x)}点 {x.ret.mean():.0%}" for d, x in g.groupby("date")))
    txt = "\n".join(L)
    os.makedirs(os.path.join(BASE, "reports"), exist_ok=True)
    open(os.path.join(BASE, "reports", "drift_live.md"), "w", encoding="utf-8").write(txt)
    print(txt)
    # 3連単の事前登録10個も続けて答え合わせ（reports/tri_live.md）
    subprocess.run([sys.executable, os.path.join(HERE, "tri_live.py")], check=False)


if __name__ == "__main__":
    main()
