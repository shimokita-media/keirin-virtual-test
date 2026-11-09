"""切り口（構造の違う⑦・先行版）：選手どうしの相性。同じラインの「先頭→番手」の組が、市場の見込み以上に2人そろって3着以内に来るか、それが続くか。
3年分の前に、今ある2025/2〜の約21か月で持続性だけ先に見る（組ごとのレース数が少ないので傾向まで）。"""
import sys, json
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
from scipy.stats import spearmanr
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
q = 1.0 / T.odds; T["pm"] = q / q.groupby(T.race_id).transform("sum")
a, b, c = combo_parts(T)
RA = pd.read_pickle(K + "out/side_races.pkl")[["race_id", "date", "line_json"]]
E = pd.read_pickle(K + "out/side_entries.pkl"); E = E[E.absent == 0]
pid = dict(zip(zip(E.race_id, E.number), E.player_id))
S = pd.read_pickle(K + "out/side_results.pkl"); S["rank"] = pd.to_numeric(S["rank"], errors="coerce")
top3 = S[S["rank"] <= 3].groupby("race_id").number.apply(set).to_dict()
rows = []
for rid, lj in zip(RA.race_id, RA.line_json):
    try: lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(lj or "[]")]
    except Exception: continue
    for ln in lines:
        if len(ln) >= 2: rows.append((rid, ln[0], ln[1]))
PR = pd.DataFrame(rows, columns=["race_id", "lead", "sec"])
PR = PR[PR.race_id.isin(set(T.race_id)) & PR.race_id.isin(set(top3))]
# 市場の見込み：2人とも3着以内＝2人を含む目の見込みの合計
sets = T[["race_id"]].assign(a=a, b=b, c=c, pm=T.pm)
key = {}
for x, y in ((0, 1), (0, 2), (1, 2)):
    s1 = sets[["race_id", "abc"[x], "abc"[y], "pm"]].copy(); s1.columns = ["race_id", "u", "v", "pm"]
    s1["lo"] = s1[["u", "v"]].min(axis=1); s1["hi"] = s1[["u", "v"]].max(axis=1)
    key[(x, y)] = s1.groupby(["race_id", "lo", "hi"]).pm.sum()
pboth = pd.concat(key.values()).groupby(level=[0, 1, 2]).sum()
PR["lo"] = PR[["lead", "sec"]].min(axis=1); PR["hi"] = PR[["lead", "sec"]].max(axis=1)
PR["p"] = pboth.reindex(pd.MultiIndex.from_frame(PR[["race_id", "lo", "hi"]])).to_numpy()
PR["act"] = [float(l in top3[r] and s in top3[r]) for r, l, s in zip(PR.race_id, PR.lead, PR.sec)]
PR["pl"] = [pid.get((r, n)) for r, n in zip(PR.race_id, PR.lead)]; PR["ps"] = [pid.get((r, n)) for r, n in zip(PR.race_id, PR.sec)]
PR["date"] = PR.race_id.map(RA.set_index("race_id").date); PR["per"] = per(PR.date); PR["hold"] = np.where(PR.per == "探す", "探す", "確認")
PR = PR.dropna(subset=["p", "pl", "ps"])
base = PR.groupby("hold").apply(lambda d: d.act.sum() / d.p.sum())
P("# 切り口：選手どうしの相性（先頭→番手の組）\n")
P(f"先頭→番手の組 {len(PR):,}件。2人とも3着以内の 実際÷見込み：探す {base['探す']:.3f}／確認（③⑥） {base['確認']:.3f}\n")
G = PR.groupby(["pl", "ps", "hold"]).agg(n=("act", "size"), a=("act", "sum"), e=("p", "sum")).reset_index()
X = G.pivot_table(index=["pl", "ps"], columns="hold", values=["n", "a", "e"]).dropna()
for k in ("探す", "確認"): X[("r", k)] = (X[("a", k)] / X[("e", k)]) / base[k]
for nmin, hmin in ((3, 2), (5, 2), (8, 3)):
    Y = X[(X[("n", "探す")] >= nmin) & (X[("n", "確認")] >= hmin)]
    if len(Y) >= 20:
        rho, p = spearmanr(Y[("r", "探す")], Y[("r", "確認")]); P(f"- 探す{nmin}回以上・確認{hmin}回以上の組 {len(Y):,}組：順位相関 **{rho:.3f}**（p={p:.3g}）")
    else: P(f"- 探す{nmin}回以上・確認{hmin}回以上の組 {len(Y)}組（少なすぎ）")
Y = X[(X[("n", "探す")] >= 3) & (X[("n", "確認")] >= 2)].copy()
if len(Y) >= 50:
    Y["qq"] = pd.qcut(Y[("r", "探す")].rank(method="first"), 5, labels=["相性悪い20%", "20〜40", "40〜60", "60〜80", "相性良い20%"])
    P("\n| 探す期間の相性 | 組数 | 確認（③⑥）実際÷見込み（組をまとめて） |\n|---|---|---|")
    for k, x in Y.groupby("qq", observed=True):
        P(f"| {k} | {len(x)} | {(x[('a','確認')].sum() / x[('e','確認')].sum()) / base['確認']:.3f}（{int(x[('n','確認')].sum())}件） |")
# 組を何回走ったか（経験）で
cnt = PR.sort_values("date").groupby(["pl", "ps"]).cumcount()
PR["prev"] = cnt
P("\n## これまでに同じ組で走った回数（その日より前、2025/2〜で数える）\n\n| 回数 | 探す | ③⑥ |\n|---|---|---|")
for lab, m in (("初めて", PR.prev == 0), ("1〜2回目", PR.prev.between(1, 2)), ("3〜5回目", PR.prev.between(3, 5)), ("6回以上", PR.prev >= 6)):
    P(f"| {lab} | " + " | ".join(f"{PR[m & (PR.hold == k)].act.sum() / PR[m & (PR.hold == k)].p.sum() / base[k]:.3f}（{(m & (PR.hold == k)).sum():,}）" for k in ("探す", "確認")) + " |")
print("done")
