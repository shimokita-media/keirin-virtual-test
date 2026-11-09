"""事前登録R・S・T・Y の中間報告（2024/2/1〜2024/7/8、取り込み済みの部分だけ）。正式な判定は全期間（2023/11/08〜2025/01/31）で行う。
条件は KNOWLEDGE.md の登録どおり（ここで変えない）。使い方: python -I -X utf8 research/prereg_interim_2024.py 出力.md"""
import sys, time, sqlite3, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
OUT = open(sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
T = prep(pd.read_pickle(K + "out/y2024a/tri.pkl")); T = T[(T["class"] != "L級") & (T.odds <= 300)].copy()
A = pd.read_pickle(K + "out/y2024a/ana.pkl").drop_duplicates("race_id").set_index("race_id")
T["race_type"] = T.race_id.map(A.race_type); T["venue"] = T.race_id.map(A.venue)
# 3連単枠・一番の目（tri_rule.py commit 18adc39 と同じ5法則・research/tri_period.py と同じ）
s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12
order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2); nine, d2 = T.entries_number >= 9, T.day_index >= 2
R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
T["nr"] = sum(r.astype(int) for r in R)
X = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
B = X.groupby("race_id").head(6); top = X.groupby("race_id").head(1)
# 欠場者のいるレース（DBは短く分けて読む：取り込み中のため）
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
ids = list(T.race_id.unique()); ab = set()
for i in range(0, len(ids), 300):
    ch = ids[i:i + 300]; ab |= {r for (r,) in con.execute(f"SELECT DISTINCT race_id FROM entries WHERE absent=1 AND race_id IN ({','.join('?' * len(ch))})", ch)}
    time.sleep(0.2)
rng = np.random.default_rng(0)
def stat(g):
    if len(g) < 2: return f"−（{len(g)}点）"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); ii = rng.integers(0, len(by), (2000, len(by)))
    bs = by["sum"].to_numpy()[ii].sum(1) / by["size"].to_numpy()[ii].sum(1)
    w = rng.dirichlet(np.ones(len(by)), 4000); post = (w @ by["sum"].to_numpy()) / (w @ by["size"].to_numpy())
    r = g.ret; t_ = (r.mean() - 1) / (r.std() / np.sqrt(len(r)))
    return (f"**{r.mean():.0%}**（{len(g)}点・当たり{int((r > 0).sum())}本）／95%の範囲 {np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}／"
            f"標準偏差 {r.std():.2f}・t={t_:+.2f}／P(>100%) {(post > 1).mean():.0%}（目減り5%後 {(post * 0.95 > 1).mean():.0%}）")
P("# 事前登録R・S・T・Y の中間報告（2024/2/1〜7/8・取り込み済みの部分）" + NL)
P(f"**これは正式な判定ではない**（登録した期間は 2023/11/08〜2025/01/31。2024/7/9〜2025/1 と 2023/11〜2024/1 は取り込み中）。条件は登録どおりで変えていない。" + NL)
P(f"{T.date.min()}〜{T.date.max()}・{T.date.nunique()}日・{T.race_id.nunique():,}レース。3連単を全部買うと {T.ret.mean():.1%}。" + NL)
first = lambda g: g[g.date <= "20240615"]; second = lambda g: g[g.date >= "20240616"]
rt = top.race_type.fillna("").astype(str)
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
Tm = T[(T.odds <= 10) & ((T.G == 1) | (T.entries_number >= 9)) & (T.r2_pt_rank >= 5)]
Y = top[~top.venue.isin(S333 | S500) & ~top.race_id.isin(ab)]
rows = [("R 3連単枠", B), ("R 一番の目", top), ("S 一番の目×準決勝", top[rt.str.contains("準決勝")]),
        ("（参考）一番の目×決勝", top[rt.str.contains("決勝") & ~rt.str.contains("準")]), ("T 10倍以下×(G戦か9車)×3着得点5位以下", Tm),
        ("Y 一番の目×400m×欠場なし", Y), ("（参考）一番の目×333m系", top[top.venue.isin(S333)]), ("（参考）一番の目×500m", top[top.venue.isin(S500)])]
P("| 登録 | 中間（2024/2/1〜7/8） | 前半（〜6/15） | 後半（6/16〜7/8） |" + NL + "|---|---|---|---|")
for nm, g in rows:
    P(f"| {nm} | {stat(g)} | {stat(first(g))} | {stat(second(g))} |")
P(NL + "## 月別（一番の目・3連単枠）" + NL + NL + "| 月 | 3連単全部 | 3連単枠 | 一番の目 |" + NL + "|---|---|---|---|")
for ym in sorted(T.date.str[:6].unique()):
    m = lambda g: g[g.date.str[:6] == ym]
    P(f"| {ym[:4]}/{ym[4:]} | {m(T).ret.mean():.0%} | {m(B).ret.mean():.0%}（{len(m(B))}点） | {m(top).ret.mean():.0%}（{len(m(top))}点） |")
P(NL + "合格基準（登録どおり・全期間で判定）：R＝95%の範囲の下限95%以上かつ前半・後半とも100%超／S＝150%以上・下限95%以上・当たり10本以上／T＝下限95%以上かつ前半・後半とも100%超／Y＝120%以上・下限100%以上・前半後半とも100%超")
print("done")
