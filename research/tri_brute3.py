"""期間を入れ替えて総当たり：4つの期間（25/2〜5、25/6〜9、26/2〜5、26/6〜8）すべてで100%超えのものだけ残す。偶然でどれくらい残るかも、結果をレース単位でシャッフルして比べる"""
exec(open("tri_brute2.py", encoding="utf-8").read().split('print(f"探す {T[SR]')[0])
blk = np.select([T.date.between("20250201", "20250531"), T.date.between("20250601", "20250931"), T.date.between("20260201", "20260531")], [0, 1, 2], 3)
def scan(ret, label):
    rows = []
    for (pn, pm), (bn, bm) in itertools.product(PAT.items(), BAND.items()):
        base = (pm & bm).to_numpy()
        if base.sum() < 400: continue
        keys = [("なし", None)] + [(c, COND[c].to_numpy()) for c in COND] + [(f"{a}×{b}", (COND[a] & COND[b]).to_numpy()) for a, b in itertools.combinations(COND, 2)]
        for kn, cm in keys:
            m = base if cm is None else base & cm
            if m.sum() < 400: continue
            rs, ns = [], []
            for b in range(4):
                mb = m & (blk == b); ns.append(mb.sum()); rs.append(ret[mb].mean() if mb.sum() else 0)
            if min(ns) < 60: continue
            h = (ret[m] > 0).sum()
            if h < 40: continue
            rows.append((pn, bn, kn, int(m.sum()), int(h), ret[m].mean(), *rs))
    R = pd.DataFrame(rows, columns=["形", "倍率", "条件", "点数", "当たり", "全体", "25前", "25後", "26前", "26後"])
    R["最低"] = R[["25前", "25後", "26前", "26後"]].min(axis=1)
    return R
ret0 = T.ret.to_numpy()
R = scan(ret0, "本物")
ok = R[(R["最低"] >= 1.0)].sort_values("最低", ascending=False)
print(f"調べた組み合わせ {len(R):,}（各期間60点以上・当たり40本以上）→ 4期間すべて100%超え {len(ok)}")
# 偶然の目安：レースごとに払戻の並びをシャッフル（同じレースの中で当たりの目をでたらめに入れ替える）
rng = np.random.default_rng(11); cnt = []
for t in range(3):
    g = T.groupby("race_id").ret
    sh = T.ret.copy()
    idx = T.groupby("race_id").cumcount()
    sh = g.transform(lambda v: v.sample(frac=1, random_state=int(rng.integers(1e9))).to_numpy())
    Rr = scan(sh.to_numpy(), "偽"); cnt.append(int((Rr["最低"] >= 1.0).sum()))
print(f"偶然（当たりをでたらめに入れ替え）で4期間すべて100%超えになる数: {cnt}")
f = lambda D: D.assign(**{c: (D[c] * 100).round().astype(int).astype(str) + "%" for c in ("全体", "25前", "25後", "26前", "26後", "最低")}).to_string(index=False)
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 32)
print(f(ok.groupby(["形", "倍率"]).head(2).head(30)))
ok.to_pickle("tri_brute3.pkl")
