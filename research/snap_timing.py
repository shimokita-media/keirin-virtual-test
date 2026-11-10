"""判断を締切に近づける価値（探す段階・**11/9 までのレースだけ**）。
1分前のスナップショット（T1）を実際に取った時刻は締切の何秒前か。締切に近い時刻に取った T1 ほど、
①そこから確定（POST）までの3連単の倍率の動きが小さいか（＝最後のお金がもう入っている）
②1分前の見込みの当てる力（当たり目の見込み）が強いか
を、T1 を取った時刻の帯ごとに比べる。本番DBのコピー out/live_db/keirin.sqlite。
使い方: python -I -X utf8 research/snap_timing.py reports/snap_timing.md"""
import sys, sqlite3, numpy as np, pandas as pd
NL = chr(10); LAST = "20261109"
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite?mode=ro", uri=True)
R = pd.read_sql("SELECT race_id, close_at FROM races", con)
O = pd.read_sql("SELECT race_id, combo, phase, odds, fetched_at FROM odds WHERE bet_type='3連単' AND phase IN ('T1','POST') AND odds > 0 ORDER BY fetched_at", con)
O = O[O.race_id.str[-8:].between("20261107", LAST)]
ft = O[O.phase == "T1"].groupby("race_id").fetched_at.max()
R = R.set_index("race_id")
def to_unix(s):  # "2026-11-08T08:43:50+09:00" → UNIX 秒
    t = pd.to_datetime(s, utc=True, errors="coerce", format="ISO8601")
    return (t - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
sec = (R.close_at.reindex(ft.index).astype(float) - to_unix(ft).astype(float))
W = O.pivot_table(index=["race_id", "combo"], columns="phase", values="odds", aggfunc="last").dropna().reset_index()
PY = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", con)
W = W[W.race_id.isin(set(PY.race_id))].merge(PY, on=["race_id", "combo"], how="left"); W["hit"] = W.payout.notna().astype(float)
W = W[W.T1 <= 200].copy(); q = 1 / W.T1; W["p1"] = q / q.groupby(W.race_id).transform("sum"); qp = 1 / W.POST; W["pp"] = qp / qp.groupby(W.race_id).transform("sum")
W["sec"] = W.race_id.map(sec)
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 判断を締切に近づける価値（11/9 までのレースだけ）" + NL)
s = sec.dropna()
P(f"T1 を取った時刻：締切の {s.min():.0f}〜{s.max():.0f} 秒前（中央値 {s.median():.0f} 秒）、{len(s)}R。close_at が日本時間を世界標準時として保存されている疑い（9時間＝32,400秒のずれ）があるので、32,400秒前後なら直す。" + NL)
if s.median() > 20000 or s.median() < -20000:
    off = 32400 if s.median() > 0 else -32400; W["sec"] = W.sec - off; s = s - off
    P(f"→ 9時間ずれていたので直した：{s.min():.0f}〜{s.max():.0f} 秒前（中央値 {s.median():.0f} 秒）" + NL)
W["band"] = pd.cut(W.sec, [-1e9, 50, 65, 80, 1e9], labels=["50秒以内", "50〜65秒", "65〜80秒", "80秒より前"])
P("| T1 を取った時刻 | レース | 点数 | 確定までの見込みの動き（絶対値の平均） | 当たり目：確定の見込み÷1分前の見込み | 当たり目の1分前の見込み（平均の log） |" + NL + "|---|---|---|---|---|---|")
for k, g in W.groupby("band", observed=True):
    h = g[g.hit > 0]
    P(f"| {k} | {g.race_id.nunique()} | {len(g):,} | {np.abs(np.log(g.pp / g.p1)).mean():.3f} | {np.exp(np.log(h.pp / h.p1).mean()):.2f} | {np.log(h.p1).mean():.2f} |")
P(NL + "- 「当たり目：確定÷1分前」が1より大きい＝当たった目は1分前から確定までにさらに買われた（最後のお金が当たりを知っていた）。締切に近いほどこれが1に近ければ、近づけるほど最後のお金を取り込める")
print("done", s.median())
