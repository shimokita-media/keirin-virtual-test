"""最新のレースのインタビューの記録と分析（本番DBの写し＋ローカルDBのインタビュー）。
言葉の表は ★事前登録I と同じ。事前登録I の確認期間⑥（〜11/8）の結果は見ないため、「当たり外れ」は 11/9 以降だけ集計する。
使い方: python -I -X utf8 research/interview_latest.py 出力.md [文の期間の開始 終了] [結果を見る開始日]
  例: ... reports/interview_latest.md 20261107 20261109 20261109"""
import sys, json, re, sqlite3, collections, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
outp = sys.argv[1]; d0, d1 = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("20261107", "20261109")
dres = sys.argv[4] if len(sys.argv) > 4 else "20261109"
OUT = open(K + outp if not outp.startswith(("C:", "/")) else outp, "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
src = open(K + "research/interview_eval.py", encoding="utf-8").read()
exec(src[src.index("NEG = ["): src.index("con = sqlite3")])  # NEG・POS・answers・score を同じものにする
L = sqlite3.connect("file:" + K + "out/live_db/keirin.sqlite?mode=ro", uri=True)
RA = pd.read_sql("SELECT race_id, date, venue, race_no, cup_id, day_index, race_type, grade FROM races WHERE date BETWEEN ? AND ?", L, params=(d0, d1))
E = pd.read_sql("SELECT e.race_id, e.number, e.player_id, e.name, e.absent FROM entries e JOIN races r USING(race_id) WHERE r.date BETWEEN ? AND ?", L, params=(d0, d1))
RS = pd.read_sql("SELECT r.race_id, r.rank, r.number FROM results r JOIN races a USING(race_id) WHERE a.date BETWEEN ? AND ?", L, params=(d0, d1))
O = pd.read_sql("""SELECT o.race_id, o.combo, o.odds, o.fetched_at FROM odds o JOIN races a USING(race_id)
                   WHERE a.date BETWEEN ? AND ? AND o.phase='POST' AND o.bet_type='3連単' AND o.source='winticket'""", L, params=(d0, d1))
L.close()
C = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
IV = pd.read_sql("SELECT cup_id, player_id, qa_json FROM interviews WHERE kind='前検'", C)
RI = pd.read_sql("SELECT race_id, player_id, qa_json FROM result_interviews WHERE substr(race_id, 5) BETWEEN ? AND ?", C, params=(str(int(d0) - 5), d1))
C.close()
E = E[E.absent == 0].merge(RA, on="race_id")
IV["t_pre"] = IV.qa_json.map(answers); RI["txt"] = RI.qa_json.map(answers)
RI = RI.merge(pd.concat([RA, pd.DataFrame()])[["race_id", "cup_id", "day_index"]], on="race_id", how="inner")
E = E.merge(IV[["cup_id", "player_id", "t_pre"]], on=["cup_id", "player_id"], how="left")
pv = E[["race_id", "cup_id", "day_index", "player_id"]].merge(RI[["cup_id", "player_id", "day_index", "txt"]].rename(columns={"day_index": "d_iv"}), on=["cup_id", "player_id"])
pv = pv[pv.d_iv < pv.day_index].groupby(["race_id", "player_id"]).txt.agg(" ".join).rename("t_post").reset_index()
E = E.merge(pv, on=["race_id", "player_id"], how="left")
E["txt"] = (E.t_pre.fillna("") + " " + E.t_post.fillna("")).str.strip()
E[["neg", "pos"]] = pd.DataFrame(E.txt.map(score).tolist(), index=E.index)
E["NEG"] = (E.neg >= 1) & (E.neg > E.pos); E["POS"] = (E.pos >= 1) & (E.pos > E.neg)
# 市場の3着以内の見込み（最終の3連単、全部の組）
O = O.sort_values("fetched_at").drop_duplicates(["race_id", "combo"], keep="last"); O = O[O.odds > 0]
O["p"] = 1 / O.odds; O["p"] = O.p / O.groupby("race_id").p.transform("sum")
X = O.assign(n=O.combo.str.split("-")).explode("n"); X["number"] = X.n.astype(int)
E = E.merge(X.groupby(["race_id", "number"]).p.sum().rename("q").reset_index(), on=["race_id", "number"], how="left")
t3 = set(zip(RS[RS["rank"] <= 3].race_id, RS[RS["rank"] <= 3].number)); w1 = set(zip(RS[RS["rank"] == 1].race_id, RS[RS["rank"] == 1].number))
E["y"] = [int((r, n) in t3) for r, n in zip(E.race_id, E.number)]
P(f"# 最新のレースのインタビュー（{d0}〜{d1}）" + NL)
P("## 記録の量" + NL + "| 日 | レース | 選手 | 前検日インタビューあり | 前の日のレース後インタビューあり | NEG（不調の言葉が多い） | POS（好調の言葉が多い） |" + NL + "|---|---|---|---|---|---|---|")
for d, g in E.groupby("date"):
    P(f"| {d} | {g.race_id.nunique()} | {len(g)} | {g.t_pre.notna().sum()} | {g.t_post.notna().sum()} | {g.NEG.sum()} | {g.POS.sum()} |")
cnt = collections.Counter(w for t in E.txt for w in NEG + POS if w in t)
P(NL + "よく出た言葉：" + "、".join(f"{w}{'（不調）' if w in NEG else '（好調）'} {n}" for w, n in cnt.most_common(15)))
R = E[(E.date >= dres) & E.q.notna() & E.race_id.isin(set(RS.race_id))]
P(NL + f"## 当たり外れ（{dres} 以降だけ。〜11/8 は事前登録I の確認期間なので見ない）" + NL)
P("| 選手の区分 | 人数 | 3着以内（実際） | 見込み（最終オッズ） | 実際÷見込み |" + NL + "|---|---|---|---|---|")
for lab, m in (("NEG", R.NEG), ("POS", R.POS), ("どちらでもない・インタビューなし", ~R.NEG & ~R.POS)):
    g = R[m]
    if len(g): P(f"| {lab} | {len(g)} | {g.y.sum()} | {g.q.sum():.1f} | {g.y.sum() / g.q.sum():.2f} |")
P(NL + "**少ない人数なので、傾向の参考にもならない（判定は事前登録I で、過去分がそろってから）**" + NL)
P("### NEG の選手（言葉・見込み・結果）" + NL + "| レース | 選手 | 当たった言葉 | 見込み | 結果 | 話（抜粋） |" + NL + "|---|---|---|---|---|---|")
for _, x in R[R.NEG].sort_values("q", ascending=False).head(25).iterrows():
    ws = "・".join(w for w in NEG if w in x.txt)
    rk = RS[(RS.race_id == x.race_id) & (RS.number == x.number)]["rank"]
    P(f"| {x.venue}{x.race_no}R | {x['name']}（{x.number}） | {ws} | {x.q:.0%} | {int(rk.iloc[0]) if len(rk) else '-'}着 | {re.sub(r'[|]', ' ', x.txt)[:60]} |")
print("done", len(E), len(R))
# 回収率：3連単（最終オッズ・全組・各100円）で、NEG／POS の選手を含む組と含まない組
PO = O.merge(RA[["race_id", "date"]], on="race_id"); PO = PO[(PO.date >= dres) & PO.race_id.isin(set(RS.race_id))]
win = {}
for rid, g in RS[RS["rank"] <= 3].sort_values("rank").groupby("race_id"):
    if len(g) >= 3: win[rid] = "-".join(map(str, g.number.head(3)))
PO["ret"] = [o if win.get(r) == c else 0.0 for r, c, o in zip(PO.race_id, PO.combo, PO.odds)]
negs = set(zip(E[E.NEG].race_id, E[E.NEG].number)); poss = set(zip(E[E.POS].race_id, E[E.POS].number))
nums = PO.combo.str.split("-").map(lambda v: [int(x) for x in v])
PO["has_neg"] = [any((r, n) in negs for n in ns) for r, ns in zip(PO.race_id, nums)]
PO["has_pos"] = [any((r, n) in poss for n in ns) for r, ns in zip(PO.race_id, nums)]
PO["neg1"] = [(r, ns[0]) in negs for r, ns in zip(PO.race_id, nums)]; PO["pos1"] = [(r, ns[0]) in poss for r, ns in zip(PO.race_id, nums)]
iv_r = set(E[E.txt != ""].race_id); Q = PO[PO.race_id.isin(iv_r)]
P(NL + f"## コメントで回収率は変わるか（3連単・最終オッズ・全組を各100円、{dres} 以降、インタビューのあるレース {Q.race_id.nunique()}R）" + NL)
P("| 組の区分 | 点数 | 当たり | 回収率 | 30倍以下に絞ると |" + NL + "|---|---|---|---|---|")
for lab, m in (("NEG の選手を含む", Q.has_neg), ("NEG の選手を含まない", ~Q.has_neg), ("NEG の選手が1着の組", Q.neg1),
               ("POS の選手を含む", Q.has_pos), ("POS の選手が1着の組", Q.pos1), ("全部", Q.has_neg | ~Q.has_neg)):
    g = Q[m]; g30 = g[g.odds <= 30]
    if len(g): P(f"| {lab} | {len(g):,} | {(g.ret > 0).sum()} | {g.ret.mean():.0%} | {g30.ret.mean():.0%}（{len(g30)}点） |")
P(NL + "当たりが数本なので、回収率は1本の当たりで大きく動く（参考の記録）。")
