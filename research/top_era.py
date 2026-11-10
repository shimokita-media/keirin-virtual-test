"""一番の目の 2024年（〜2025/1）と 2025/2〜 の違いを分ける（新しい条件は探さない）。
①構成の違い：倍率の帯・車立て・グレード・バンクごとに、両方の時期の 当たり÷見込み と回収率を並べ、2024年の構成で 2025年以降を重みづけし直す（標準化）
②大きな当たりへの偏り：払戻の大きい順に上位5本・10本を外した回収率
③どの法則で選ばれた目か（法則の数）
データ：〜2025/1 は out/y2024full/cache.pkl、2025/2〜 は out/tri_base.parquet。確定オッズ・各100円。
使い方: python -I -X utf8 research/top_era.py reports/top_era.md"""
import sys, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
cols = ["race_id", "date", "odds", "ret", "venue", "entries_number"]
A = pd.read_pickle(K + "out/y2024full/cache.pkl")
A = A.loc[A.is_top, cols + ["G"]]
B = duckdb.sql(f"SELECT {', '.join(cols)} FROM '{K}out/tri_base.parquet' WHERE is_top AND date > '20250131'").df()
GB = pd.read_pickle(K + "out/angle_base_full.pkl", ) if False else None  # G は parquet にないので race から作る
R = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id").set_index("race_id")
B["G"] = B.race_id.map(R.grade).fillna("").astype(str).str.startswith("G").astype(int)
A["era"], B["era"] = "2024年（〜2025/1）", "2025/2〜"
T = pd.concat([A, B]).reset_index(drop=True)
T["q"] = 1 / T.odds
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
T["bank"] = np.select([T.venue.isin(S333), T.venue.isin(S500)], ["333m系", "500m"], "400m")
T["band"] = pd.cut(T.odds, [0, 8, 12, 20, 40, 1000], labels=["〜8倍", "8〜12倍", "12〜20倍", "20〜40倍", "40倍〜"])
T["cars"] = np.where(T.entries_number >= 9, "9車", "7車以下")
T["gr"] = np.where(T.G == 1, "G戦", "F戦")
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 一番の目：2024年と2025年以降の違いを分ける（確定オッズ・各100円・新しい条件は探していない）" + NL)
for key, nm in (("band", "倍率の帯"), ("cars", "車立て"), ("gr", "グレード"), ("bank", "バンク")):
    P(f"## {nm}ごと" + NL + "| " + nm + " | 時期 | 点数 | 割合 | 当たり | 回収率 | 当たり÷見込み |" + NL + "|---|---|---|---|---|---|---|")
    for k, g in T.groupby(key, observed=True):
        for e, x in g.groupby("era"):
            share = len(x) / (T.era == e).sum()
            P(f"| {k} | {e} | {len(x)} | {share:.0%} | {int((x.ret > 0).sum())} | **{x.ret.mean():.0%}** | {(x.ret > 0).sum() / x.q.sum():.2f} |")
    P("")
# 標準化：2025年以降を、2024年の倍率の帯の割合で重みづけ
a, b = T[T.era.str.startswith("2024")], T[T.era == "2025/2〜"]
wa = a.band.value_counts(normalize=True); rb = b.groupby("band", observed=True).ret.mean()
P(f"## 標準化" + NL + f"- 2025/2〜 の回収率 {b.ret.mean():.0%} を、2024年の倍率の帯の割合で重みづけし直すと **{(wa * rb).sum():.0%}**（2024年は {a.ret.mean():.0%}）" + NL)
P("## 大きな当たりを外すと" + NL + "| 時期 | 全部 | 上位5本を外す | 上位10本を外す | 当たりの本数 |" + NL + "|---|---|---|---|---|")
for e, x in T.groupby("era"):
    r = x.ret.sort_values(ascending=False).to_numpy(); n = len(r)
    P(f"| {e} | {r.mean():.0%} | {r[5:].sum() / n:.0%} | {r[10:].sum() / n:.0%} | {int((r > 0).sum())} |")
print("done")
