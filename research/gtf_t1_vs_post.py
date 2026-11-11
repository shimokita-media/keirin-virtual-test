"""L2 の弱点の確かめ：「3連複から見て割安（g_tf>0）」は確定オッズで作った。締切1分前（T1）の倍率で作った g_tf と、確定（POST）で作った g_tf は同じ判定になるか。
本番DBのコピー（out/live_db/keirin.sqlite）と、1分前の表 out/angle_base_t1.pkl（T1 の倍率で作った angle_base 形式）。**倍率どうしを比べるだけで、当たり・払戻は一切使わない**（11/10 以降の成績を見ないため）。
g_tf＝log(3連複の同じ3人の見込み) − log(3連単の同じ3人6通りの見込みの合計)。見込み＝1/倍率を券種・レースの中で合計1（3連単は300倍以下の中で、tri3_build と同じ）。
使い方: python -I -X utf8 research/gtf_t1_vs_post.py reports/gtf_t1_vs_post.md"""
import sys, sqlite3, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
T = pd.read_pickle(K + "out/angle_base_t1.pkl")
B = T[(T.s01 == 1) & (T.s12 == 1) & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2) & (T.r2_pt_rank >= 7) & (T.odds <= 15)][["race_id", "combo", "odds", "g_tf", "date"]].rename(columns={"odds": "odds_t1", "g_tf": "g_t1"})
con = sqlite3.connect("file:" + K + "out/live_db/keirin.sqlite?mode=ro", uri=True)
ids = tuple(B.race_id.unique()); q = ",".join("?" * len(ids))
O = pd.read_sql(f"SELECT race_id, bet_type, combo, odds, fetched_at FROM odds WHERE phase='POST' AND source='winticket' AND odds>0 AND bet_type IN ('3連単','3連複') AND race_id IN ({q})", con, params=ids)
O = O.sort_values("fetched_at").drop_duplicates(["race_id", "bet_type", "combo"], keep="last")
def norm(d):
    d = d.copy(); d["q"] = 1 / d.odds; d["q"] /= d.groupby("race_id").q.transform("sum"); return d
t = norm(O[O.bet_type == "3連単"]); t = t[t.odds <= 300].copy()
t["key"] = ["-".join(map(str, sorted(map(int, c.split("-"))))) for c in t.combo]
setp = t.groupby(["race_id", "key"]).q.sum().rename("set_p").reset_index()
tf = norm(O[O.bet_type == "3連複"]).rename(columns={"combo": "key", "q": "tf_q"})[["race_id", "key", "tf_q"]]
B["key"] = ["-".join(map(str, sorted(map(int, c.split("-"))))) for c in B.combo]
B = B.merge(setp, on=["race_id", "key"], how="left").merge(tf, on=["race_id", "key"], how="left").merge(t[["race_id", "combo", "odds"]].rename(columns={"odds": "odds_post"}), on=["race_id", "combo"], how="left")
lg = lambda p: np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))
B["g_post"] = lg(B.tf_q) - lg(B.set_p)
B = B.dropna(subset=["g_post", "g_t1", "odds_post"])
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 「3連複から見て割安」は締切1分前の倍率でも同じ判定になるか（倍率だけの比べ。成績は使っていない）" + NL)
P(f"本番の記録 {B.date.min()}〜{B.date.max()}・ライン順×3着7位以下×1分前15倍以下 {len(B)}点（{B.race_id.nunique()}R）" + NL)
for nm, x in (("1分前で10倍以下", B[B.odds_t1 <= 10]), ("1分前で15倍以下", B)):
    a, b = x.g_t1 > 0, x.g_post > 0
    P(f"## {nm}（{len(x)}点）" + NL)
    P(f"- 1分前に割安 {a.sum()}点（{a.mean():.0%}）／確定で割安 {b.sum()}点（{b.mean():.0%}）")
    P(f"- 判定が同じ {(a == b).mean():.0%}。1分前に割安のうち確定でも割安 {(a & b).sum() / max(a.sum(), 1):.0%}／確定で割安のうち1分前も割安 {(a & b).sum() / max(b.sum(), 1):.0%}")
    P(f"- g_tf の相関（1分前と確定）{np.corrcoef(x.g_t1, x.g_post)[0, 1]:.2f}。1分前→確定で g_tf の平均の変化 {(x.g_post - x.g_t1).mean():+.3f}")
    P(f"- 倍率：1分前の平均 {x.odds_t1.mean():.1f}倍 → 確定 {x.odds_post.mean():.1f}倍（確定÷1分前の中央値 {(x.odds_post / x.odds_t1).median():.2f}）。1分前に10倍以下のうち確定でも10倍以下 {((x.odds_t1 <= 10) & (x.odds_post <= 10)).sum() / max((x.odds_t1 <= 10).sum(), 1):.0%}" + NL)
print("done", len(B))
