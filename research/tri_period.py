"""3連単枠・一番の目を2025年/2026年の期間別に（最終オッズ・L級除く・選び方は top1.py / tri_rule と同じ）"""
import numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
A = pd.concat([pd.read_pickle(SP + "tri3_all.pkl"), pd.read_pickle(SP + "tri3_new.pkl")] +
              [pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh", "fresh2", "fresh3", "fresh4", "fresh5", "fresh6", "fresh7")])
A = A.drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
T = prep(A); T = T[T["class"] != "L級"].copy()
s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12
order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
nine, d2 = T.entries_number >= 9, T.day_index >= 2
R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
T["nr"] = sum(r.astype(int) for r in R)
allr = T.groupby("date").race_id.nunique()
X = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
B = X.groupby("race_id").head(6).copy(); top = X.groupby("race_id").head(1).copy()
rng = np.random.default_rng(0)

def ci(g):
    if len(g) < 30: return "−"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); i = rng.integers(0, len(by), (1000, len(by)))
    b = by["sum"].to_numpy()[i].sum(1) / by["size"].to_numpy()[i].sum(1)
    return f"{np.percentile(b, 2.5):.0%}〜{np.percentile(b, 97.5):.0%}"

def cell(g):
    if not len(g): return "−", "−", "−"
    return f"**{g.ret.mean():.0%}**", f"{len(g)}点・{int((g.ret > 0).sum())}本", ci(g)

def table(keyf, keys, title):
    print(f"\n### {title}\n")
    print("| 期間 | 日数 | 3連単全部 | 3連単枠 | 点数・当たり | 95%の範囲 | 一番の目 | 点数・当たり | 95%の範囲 |")
    print("|---|---|---|---|---|---|---|---|---|")
    kT, kB, kt = keyf(T.date), keyf(B.date), keyf(top.date)
    for k in keys:
        a, b, c = T[kT == k], B[kB == k], top[kt == k]
        if not len(a): continue
        print(f"| {k} | {a.date.nunique()} | {a.ret.mean():.0%} | " + " | ".join(cell(b)) + " | " + " | ".join(cell(c)) + " |")

yr = lambda d: np.where(d < "20260101", "2025年（2/1〜12/31）", "2026年（1/1〜11/5）")
table(yr, ["2025年（2/1〜12/31）", "2026年（1/1〜11/5）"], "年別")
blk = lambda d: np.select([d.between("20250201", "20250529"), d.between("20250530", "20251011"), d.between("20251012", "20260114"),
                           d.between("20260115", "20260615"), d.between("20260616", "20260831")],
                          ["①探した期間 25/2〜5", "②未使用①〜⑥ 25/5/30〜10/11", "③本当の答え合わせ 25/10/12〜26/1/14", "④探した期間 26/1/15〜6/15", "⑤探した期間 26/6/16〜8/31"],
                          "⑥直近 26/9〜11/5")
table(blk, ["①探した期間 25/2〜5", "②未使用①〜⑥ 25/5/30〜10/11", "③本当の答え合わせ 25/10/12〜26/1/14", "④探した期間 26/1/15〜6/15", "⑤探した期間 26/6/16〜8/31", "⑥直近 26/9〜11/5"], "使い方別の期間")
mo = lambda d: d.str[:4] + "/" + d.str[4:6]
table(mo, sorted(T.date.str[:6].map(lambda s: s[:4] + "/" + s[4:]).unique()), "月別")
