"""機械の期待値1.0以上（ライン順×確定オッズ15倍以下・係数 lo_model_coef_4yr.json 固定）から、レースの条件で絞ったら年ごとにどうなるか。
ユーザー依頼（2026-11-20）「期待値1.0以上を全部から条件で絞った場合」「過去もみたい」。
注意：9年とも E1 の確かめで見た年（新しい年はもう残っていない）。ここで良く見えたものは「本番の記録で確かめる候補」にしかならない。
係数を学んだ4年（y4・y5・2024年・2025/2〜）と、学んでいない5年（y6〜y10）を分けて出す。
条件は先に決めた一覧（下の CONDS）だけ。g_tf・g_ex など確定オッズ由来の列は使わない（期待値と倍率は判断時の倍率で置き換わる前提）。
使い方：python -X utf8 research/ev1_drill.py reports/ev1_drill.md"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
out = sys.argv[1] if len(sys.argv) > 1 else K + "reports/ev1_drill.md"
A = pd.read_pickle(K + "out/lo15_9yr.pkl")
SR = {"y4": "y4", "y5": "y5", "y6": "y6", "y7": "y7", "y8": "y8", "y9": "y9", "y10": "y10", "2024年": "y2024full", "2025/2〜": "full"}
R = pd.concat([pd.read_pickle(K + f"out/side_races_{v}.pkl") for v in set(SR.values())], ignore_index=True).drop_duplicates("race_id")
A = A.merge(R[["race_id", "venue", "grade", "class", "entries_number", "race_type", "day_index", "race_no", "line_json", "start_at"]], on="race_id", how="left")
print("条件がつかない行", A.venue.isna().sum())
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
A["bank"] = np.where(A.venue.isin(S333), "333m系", np.where(A.venue.isin(S500), "500m", "400m"))
A["hour"] = pd.to_datetime(A.start_at, unit="s", utc=True).dt.tz_convert("Asia/Tokyo").dt.hour
def nl(s):
    try: return len(json.loads(s))
    except Exception: return np.nan
A["nlines"] = A.line_json.map(nl)
TRAIN = {"y4", "y5", "2024年", "2025/2〜"}; YRS = ["y10", "y9", "y8", "y7", "y6", "y5", "y4", "2024年", "2025/2〜"]
E = A[A.ev >= 1.0].copy()

CONDS = {
    "全部（期待値1.0以上）": lambda d: d.ev >= 1.0,
    "期待値 1.0〜1.1": lambda d: d.ev < 1.1, "期待値 1.1〜1.2": lambda d: (d.ev >= 1.1) & (d.ev < 1.2), "期待値 1.2以上（E1）": lambda d: d.ev >= 1.2,
    "倍率 〜5倍": lambda d: d.odds <= 5, "倍率 5〜10倍": lambda d: (d.odds > 5) & (d.odds <= 10), "倍率 10〜15倍": lambda d: d.odds > 10,
    "9車": lambda d: d.entries_number == 9, "7車": lambda d: d.entries_number == 7,
    "ライン2本": lambda d: d.nlines == 2, "ライン3本": lambda d: d.nlines == 3, "ライン4本以上": lambda d: d.nlines >= 4,
    "400m": lambda d: d.bank == "400m", "333m系": lambda d: d.bank == "333m系", "500m": lambda d: d.bank == "500m",
    "G戦（G3以上）": lambda d: d.grade.astype(str).str.contains("G"), "F1": lambda d: d.grade.astype(str) == "F1", "F2": lambda d: d.grade.astype(str) == "F2",
    "初日": lambda d: d.day_index == 1, "2日目以降": lambda d: d.day_index >= 2,
    "1〜6R": lambda d: d.race_no <= 6, "7R以降": lambda d: d.race_no >= 7,
    "朝・昼（〜15時）": lambda d: d.hour < 15, "ナイター（15〜21時）": lambda d: (d.hour >= 15) & (d.hour < 21), "ミッドナイト（21時〜）": lambda d: d.hour >= 21,
}
rng = np.random.default_rng(0)
def boot(g):
    x = g.groupby("race_id").ret.agg(["sum", "size"]);
    if len(x) < 5: return np.nan, np.nan
    ii = rng.integers(0, len(x), (2000, len(x))); b = x["sum"].to_numpy()[ii].sum(1) / x["size"].to_numpy()[ii].sum(1)
    return np.percentile(b, 2.5), np.percentile(b, 97.5)
rows = []
for k, f in CONDS.items():
    g = E[f(E).fillna(False)]
    yr = g.groupby("yr").ret.agg(["mean", "size"]).reindex(YRS)
    lo, hi = boot(g); new = g[~g.yr.isin(TRAIN)]; tr = g[g.yr.isin(TRAIN)]
    nlo, nhi = boot(new)
    rows.append(dict(条件=k, 点数=len(g), 一日=len(g) / (9 * 365), 回収率=g.ret.mean(), 範囲=f"{lo:.0%}〜{hi:.0%}",
                     学んだ4年=tr.ret.mean(), 学んでいない5年=new.ret.mean(), 五年の範囲=f"{nlo:.0%}〜{nhi:.0%}",
                     超年=int((yr["mean"] > 1).sum()), 一番悪い年=yr["mean"].min(),
                     年別=" / ".join("−" if pd.isna(m) else f"{m:.0%}" for m in yr["mean"])))
T = pd.DataFrame(rows)
L = ["# 機械の期待値1.0以上から条件で絞る（ライン順×15倍以下・9年）", "",
     "- 対象：同じライン3人の先頭→番手→3番手の3連単・確定オッズ15倍以下・機械の期待値（4年で学んだ係数で固定）1.0以上。確定オッズ・確定の払戻・各100円",
     "- **9年とも、E1 を確かめるときに見た年**。ここで良く見えても本物とは言えない。候補は「結果を見る前に条件を固定→本番の記録で確かめる」に回す",
     "- 係数を学んだ4年（y4・y5・2024年・2025/2〜）は機械に有利。学んでいない5年（y6〜y10）の方が当てになる",
     f"- 年別の並び：{' / '.join(YRS)}", "",
     "| 条件 | 点数 | 1日あたり | 9年 | 95%の範囲 | 学んだ4年 | 学んでいない5年 | 5年の95%の範囲 | 100%超の年 | 一番悪い年 | 年別 |",
     "|---|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['条件']} | {r['点数']:,} | {r['一日']:.1f} | **{r['回収率']:.0%}** | {r['範囲']} | {r['学んだ4年']:.0%} | **{r['学んでいない5年']:.0%}** | {r['五年の範囲']} | {r['超年']}/9 | {r['一番悪い年']:.0%} | {r['年別']} |")
# 2つ重ねたもの：単独で「学んでいない5年」100%超の条件どうし（期待値・倍率の帯は除く）だけ
base = [k for k in CONDS if not k.startswith(("全部", "期待値", "倍率"))]
good = [k for k in base if T.set_index("条件").loc[k, "学んでいない5年"] > 1.0]
L += ["", "## 2つ重ね（単独で学んでいない5年が100%超の条件どうし。重ねるほど偶然が増えるので参考）", "",
      "| 条件 | 点数 | 9年 | 学んでいない5年 | 100%超の年 | 一番悪い年 |", "|---|---|---|---|---|---|"]
pairs = []
for i, a in enumerate(good):
    for b in good[i + 1:]:
        g = E[(CONDS[a](E) & CONDS[b](E)).fillna(False)]
        if len(g) < 300: continue
        yr = g.groupby("yr").ret.mean().reindex(YRS); new = g[~g.yr.isin(TRAIN)]
        pairs.append((a + "×" + b, len(g), g.ret.mean(), new.ret.mean(), int((yr > 1).sum()), yr.min()))
for p_ in sorted(pairs, key=lambda x: -x[3])[:15]:
    L.append(f"| {p_[0]} | {p_[1]:,} | {p_[2]:.0%} | {p_[3]:.0%} | {p_[4]}/9 | {p_[5]:.0%} |")
L += ["", f"- 試した数：単独 {len(CONDS)}・2つ重ね {len(pairs)}。これだけ試すと、偶然でも数個は良く見える"]
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
