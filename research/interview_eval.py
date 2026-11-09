"""★事前登録I（インタビューの言葉）の判定（KNOWLEDGE.md 2026-11-10 1:05 の登録どおり。結果を見てから言葉や基準を変えない）。
材料：interviews（前検日）と result_interviews（レース後。同じ開催の前の日までの分だけ＝そのレースの前に分かる情報）。
市場の見込み：最終の3連単（300倍以下）の確率 p を、その選手を含む組で足した「3着以内の見込み」q。
使い方: python -I -X utf8 research/interview_eval.py 出力.md [--judge]
  --judge なしは仕組みの確認（件数と探す期間だけ）。--judge で全期間と確認期間⑥の合否を出す（判定のときだけ使う）"""
import sys, json, sqlite3, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
outp = sys.argv[1]; JUDGE = "--judge" in sys.argv
OUT = open(K + outp if not outp.startswith(("C:", "/")) else outp, "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
NEG = ["腰", "痛", "ケガ", "怪我", "落車", "体調", "風邪", "疲れ", "疲労", "重い", "重かった", "悪い", "悪かった", "良くない", "よくない",
       "本調子", "不安", "迷走", "決まらない", "戻っていない", "戻ってない", "苦しい", "きつい", "一杯", "いっぱい", "脚がない", "嫌い", "苦手", "ダメ", "だめ"]
POS = ["良い", "良かった", "悪くない", "調子がいい", "状態はいい", "状態がいい", "感じはいい", "感触はいい", "軽い", "軽かった", "仕上が",
       "手応え", "好調", "自信", "得意", "好き", "相性"]
def answers(qa):
    try: return " ".join(t.get("answer", "") for t in json.loads(qa))
    except Exception: return ""
def score(txt):
    neg = sum(1 for w in NEG if w in txt); pos = sum(1 for w in POS if w in txt)
    # 「悪くない」「良くない」の重なりを直す（「悪くない」は悪いに数えない＝「悪い」は部分一致しないので不要。「良くない」は「良い」に一致しない）
    return neg, pos
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
IV = pd.read_sql("SELECT cup_id, player_id, qa_json FROM interviews WHERE kind='前検'", con)
RI = pd.read_sql("SELECT race_id, player_id, qa_json FROM result_interviews", con)
con.close()
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")[["race_id", "date", "cup_id", "day_index"]]
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0][["race_id", "number", "player_id"]].drop_duplicates(["race_id", "number"])
R = pd.read_pickle(K + "out/side_results_full.pkl"); top3 = set(zip(R[R["rank"] <= 3].race_id, R[R["rank"] <= 3].number))
T = pd.read_pickle(K + "out/angle_base_full.pkl")[["race_id", "combo", "date", "p", "odds", "ret"]]
T = T[T.date >= "20251201"]
E = E.merge(RA, on="race_id"); E = E[E.date.between("20251201", "20261108")]
# 前検日インタビュー
IV["txt"] = IV.qa_json.map(answers)
E = E.merge(IV[["cup_id", "player_id", "txt"]].rename(columns={"txt": "t_pre"}), on=["cup_id", "player_id"], how="left")
# レース後インタビュー：同じ開催の前の日までの分をつなげる
RI = RI.merge(RA, on="race_id"); RI["txt"] = RI.qa_json.map(answers)
prev = E[["race_id", "cup_id", "day_index", "player_id"]].merge(RI[["cup_id", "player_id", "day_index", "txt"]].rename(columns={"day_index": "d_iv"}), on=["cup_id", "player_id"])
prev = prev[prev.d_iv < prev.day_index].groupby(["race_id", "player_id"]).txt.agg(" ".join).rename("t_post").reset_index()
E = E.merge(prev, on=["race_id", "player_id"], how="left")
E["txt"] = E.t_pre.fillna("") + " " + E.t_post.fillna("")
E[["neg", "pos"]] = pd.DataFrame(E.txt.map(score).tolist(), index=E.index)
E["has"] = E.txt.str.strip() != ""
E["NEG"] = (E.neg >= 1) & (E.neg > E.pos)
# 市場の3着以内の見込み q
X = T.assign(n=T.combo.str.split("-")).explode("n"); X["number"] = X.n.astype(int)
q = X.groupby(["race_id", "number"]).p.sum().rename("q").reset_index()
s = T.groupby("race_id").p.sum().rename("ps")
E = E.merge(q, on=["race_id", "number"]); E["q"] = E.q / E.race_id.map(s)  # 300倍以下の組だけで足しているので、3着以内の合計が3になるようにそろえる（各組は3人に数えるので p の合計で割るだけで合計3。11/10 7:40 に「*3」の重複を直した＝基準は変えていない）
E["y"] = [int((r, n) in top3) for r, n in zip(E.race_id, E.number)]
E["res"] = E.y - E.q
def per(d):
    return np.where(d < "20260115", "③(12/1〜1/14)", np.where(d <= "20260831", "探す(1/15〜8/31)", "⑥確認(9/1〜11/8)"))
E["per"] = per(E.date)
P("# ★事前登録I：インタビューの言葉（" + ("判定" if JUDGE else "仕組みの確認") + "）" + NL)
P(f"選手×レース {len(E):,}（インタビューあり {E.has.sum():,}、うち NEG {E.NEG.sum():,}）・レース {E.race_id.nunique():,}・{E.date.min()}〜{E.date.max()}" + NL)
def h1(d):
    g = d.groupby("race_id").apply(lambda x: x.loc[x.NEG, "res"].sum() / max(x.NEG.sum(), 1) - x.loc[~x.NEG, "res"].mean() if x.NEG.any() and (~x.NEG).any() else np.nan).dropna()
    return len(g), d[d.NEG].y.mean() / max(d[d.NEG].q.mean(), 1e-9), d[~d.NEG].y.mean() / max(d[~d.NEG].q.mean(), 1e-9), g.mean(), g.mean() / (g.std() / np.sqrt(len(g))) if len(g) > 1 else np.nan
pers = ["探す(1/15〜8/31)"] + (["③(12/1〜1/14)", "⑥確認(9/1〜11/8)", "全部"] if JUDGE else [])  # ③と⑥は判定のときだけ見る
P("**H1** NEG の選手は市場の見込みより3着に入らない（同じレースの他の選手との 実際−見込み の差、レースごと）" + NL)
P("| 期間 | レース | NEG 実際÷見込み | 他 実際÷見込み | 差の平均 | t |" + NL + "|---|---|---|---|---|---|")
for pn in pers:
    d = E if pn == "全部" else E[E.per == pn]
    if not len(d) or not d.NEG.any(): P(f"| {pn} | 0 | | | | |"); continue
    n, a, b, m, t = h1(d); P(f"| {pn} | {n:,} | {a:.3f} | {b:.3f} | {m:+.4f} | {t:+.2f} |")
# H2：3連単（300倍以下）で NEG の選手を含む組と含まない組の回収率
negset = set(zip(E[E.NEG].race_id, E[E.NEG].number))
X2 = X[["race_id", "combo", "number", "date", "ret"]]
X2 = X2.assign(neg=[(r, n) in negset for r, n in zip(X2.race_id, X2.number)]).groupby(["race_id", "combo", "date", "ret"]).neg.any().reset_index()
X2 = X2[X2.race_id.isin(set(E[E.has].race_id))]
X2["per"] = per(X2.date)
P(NL + "**H2** 3連単（300倍以下、インタビューのあるレース）で、NEG の選手を含む組の回収率は含まない組より低い" + NL)
P("| 期間 | 含む組 点数 | 含む組 回収率 | 含まない組 回収率 | レースごとの差の t |" + NL + "|---|---|---|---|---|")
for pn in pers:
    d = X2 if pn == "全部" else X2[X2.per == pn]
    if not len(d) or not d.neg.any(): P(f"| {pn} | 0 | | | |"); continue
    g = d.groupby(["race_id", "neg"]).ret.mean().unstack().dropna(); df = g[True] - g[False]
    P(f"| {pn} | {d.neg.sum():,} | {d[d.neg].ret.mean():.0%} | {d[~d.neg].ret.mean():.0%} | {df.mean() / (df.std() / np.sqrt(len(df))) if len(df) > 1 else float('nan'):+.2f} |")
if not JUDGE:
    P(NL + "（確認期間⑥はまだ見ない。合否は --judge のときだけ）")
print("done", len(E))
