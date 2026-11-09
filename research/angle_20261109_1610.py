"""切り口（構造の違う①）：選手ごとの買われ方の癖。選手その人（player_id）が、いつも市場の見込みより3着以内に来る／来ないか。
1) 市場の見込み：3連単の最終倍率（300倍以下）を1/倍率で正規化 → その選手を含む目の合計＝「3着以内に来る見込み」
2) 探す期間で選手ごとに「実際の3着以内 ÷ 見込み」（30レース以上）。③と⑥でも同じ向きか（相関）
3) 探す期間で上位20%（過小評価されがち）の選手を含む目を、③⑥で買ったらどうか"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True)
q = 1.0 / T.odds; T["pm"] = q / q.groupby(T.race_id).transform("sum")
a, b, c = combo_parts(T)
L = pd.concat([pd.DataFrame({"race_id": T.race_id, "number": n, "pm": T.pm}) for n in (a, b, c)])
p3 = L.groupby(["race_id", "number"]).pm.sum().rename("p3").reset_index()
R = pd.read_sql("SELECT race_id, number, player_id, rank FROM results", con)
E = pd.read_sql("SELECT e.race_id, e.number, e.player_id FROM entries e JOIN races r USING(race_id) WHERE r.date >= '20250201' AND e.absent = 0", con)
D = p3.merge(E, on=["race_id", "number"], how="left").merge(R[["race_id", "number", "rank"]], on=["race_id", "number"], how="left")
D = D[D.race_id.isin(set(R.race_id))]
D["top3"] = (pd.to_numeric(D["rank"], errors="coerce") <= 3).astype(float)
D["date"] = D.race_id.map(T.drop_duplicates("race_id").set_index("race_id").date); D["per"] = per(D.date)
P("# 切り口：選手ごとの買われ方の癖（選手その人の固定効果）\n")
P(f"選手×レース {len(D):,}行。全体の 実際÷見込み：探す {D[D.per=='探す'].top3.sum()/D[D.per=='探す'].p3.sum():.3f}（見込みは300倍以下の目だけで作るので本命寄りに少しずれる）\n")
g = D.groupby(["player_id", "per"]).agg(n=("top3", "size"), act=("top3", "sum"), exp=("p3", "sum")).reset_index()
W = g.pivot(index="player_id", columns="per", values=["n", "act", "exp"]).fillna(0)
base = {k: D[D.per == k].top3.sum() / D[D.per == k].p3.sum() for k in ("探す", "③", "⑥")}
for k in ("探す", "③", "⑥"): W[("r", k)] = (W[("act", k)] / W[("exp", k)]) / base[k]
ok = (W[("n", "探す")] >= 30)
H = W[ok].copy()
H["hold_n"] = H[("n", "③")] + H[("n", "⑥")]
H["hold_r"] = ((H[("act", "③")] + H[("act", "⑥")]) / (H[("exp", "③")] + H[("exp", "⑥")])) / ((base["③"] + base["⑥"]) / 2)
H2 = H[H.hold_n >= 15]
P(f"探す期間で30レース以上の選手 {len(H):,}人、うち③⑥で15レース以上 {len(H2):,}人\n")
from scipy.stats import spearmanr
rho, pv = spearmanr(H2[("r", "探す")], H2.hold_r)
P(f"- 選手ごとの「実際÷見込み」の、探す期間と③⑥の順位相関：**{rho:.3f}**（p={pv:.3g}）。0なら癖は持続しない＝運\n")
H2 = H2.assign(qq=pd.qcut(H2[("r", "探す")], 5, labels=["下位20%（来ない）", "20〜40", "40〜60", "60〜80", "上位20%（よく来る）"]))
P("| 探す期間の癖 | 人数 | 探す 実際÷見込み | ③⑥ 実際÷見込み |\n|---|---|---|---|")
for k, x in H2.groupby("qq", observed=True):
    P(f"| {k} | {len(x)} | {(x[('act','探す')].sum()/x[('exp','探す')].sum())/base['探す']:.3f} | {((x[('act','③')].sum()+x[('act','⑥')].sum())/(x[('exp','③')].sum()+x[('exp','⑥')].sum()))/((base['③']+base['⑥'])/2):.3f} |")
# 買い方の確認：探す期間の上位20%／下位20%の選手を含む目
top_ids = set(H2[H2.qq == "上位20%（よく来る）"].index); bot_ids = set(H2[H2.qq == "下位20%（来ない）"].index)
pid = dict(zip(zip(E.race_id, E.number), E.player_id))
for i, n in enumerate((a, b, c)): T[f"pid{i}"] = [pid.get((r, x)) for r, x in zip(T.race_id, n)]
ntop = sum(T[f"pid{i}"].isin(top_ids).astype(int) for i in range(3)); nbot = sum(T[f"pid{i}"].isin(bot_ids).astype(int) for i in range(3))
OUT.close()
conds = {"よく来る選手を含む": ntop >= 1, "よく来る選手を2人以上含む": ntop >= 2, "来ない選手を含む": nbot >= 1, "来ない選手を含まない": nbot == 0,
         "1着がよく来る選手": T.pid0.isin(top_ids), "1着が来ない選手": T.pid0.isin(bot_ids), "よく来る選手を含み来ない選手を含まない": (ntop >= 1) & (nbot == 0)}
import shutil
tmp = sys.argv[1] + ".tmp"
cand, c2 = report(tmp, "（続き）癖のある選手を含む目の回収率", "※「探す」の回収率は、選手の選び方に同じ期間を使っているので良く見えて当然。判断は ③・⑥ で。", conds)
with open(sys.argv[1], "a", encoding="utf-8") as f, open(tmp, encoding="utf-8") as g2: f.write("\n" + g2.read())
import os; os.remove(tmp)
print("rho", rho, "候補", len(cand))
