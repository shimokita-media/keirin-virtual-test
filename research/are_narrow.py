"""B・S・コメントなどで3連単の目を「最大限しぼる」：前半で条件を重ねて探し（ビームサーチ）、後半と2024年（未使用の別の期間）で再現するか確かめる。
探す＝2025/02〜2025/12/25、確かめ①＝2025/12/26〜2026/11/05、確かめ②＝2024年の表（2023/11〜2025/01）。表は300倍までの目。"""
import sqlite3, time, os, re, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; S = K + "out/are_work/"
pd.set_option("display.width", 250)
def entries_for(ids, path):
    if os.path.exists(path): return pd.read_pickle(path)
    c = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30); E = []
    for i in range(0, len(ids), 300):
        q = ids[i:i + 300]
        E.append(pd.read_sql(f"SELECT race_id, number AS num, comment, n_back, n_standing FROM entries WHERE absent=0 AND race_id IN ({','.join('?'*len(q))})", c, params=q)); time.sleep(0.3)
    c.close(); E = pd.concat(E); E.to_pickle(path); return E
def ccat(s):
    s = str(s or "")
    if re.search("単騎|１人|一人|1人|自分だけ", s): return "単騎"
    if re.search("自力|自分で|先行|主導権|前々|逃げ|カマシ|かまし", s): return "自力"
    if re.search("自在|位置|流れ|臨機|展開|様子|未定|決めて|考え", s): return "自在・未定"
    if re.search("君|さん|選手|番手|後ろ|付いて|マーク|続", s): return "追走"
    return "その他"
COLS = ["race_id", "combo", "odds", "ret", "date", "nlines", "entries_number", "grade"] + [f"r{k}_{c}" for k in range(3) for c in ["mk_rank", "pos", "single", "style"]]
def prep(path, epath):
    d = pd.read_pickle(path)[COLS]
    E = entries_for(sorted(d.race_id.unique()), epath)
    E["cc"] = E.comment.map(ccat)
    g = E.groupby("race_id")
    E["Brk"] = g.n_back.rank(ascending=False, method="min").clip(upper=4); E["Bb"] = pd.cut(E.n_back, [-1, 0, 4, 10, 999], labels=["0", "1-4", "5-10", "11+"]).astype(str)
    E["Sb"] = pd.cut(E.n_standing, [-1, 0, 3, 999], labels=["0", "1-3", "4+"]).astype(str)
    cb = d.combo.str.split("-", expand=True).astype(int)
    Ei = E.set_index(["race_id", "num"])
    for k in range(3):
        key = pd.MultiIndex.from_arrays([d.race_id, cb[k]])
        for c in ["cc", "Brk", "Bb", "Sb"]:
            d[f"r{k}_{c}"] = Ei[c].reindex(key).values
    fav = d.groupby("race_id").odds.transform("min")
    d["favb"] = pd.cut(fav, [0, 5, 10, 15, 1e9], labels=["〜5", "5〜10", "10〜15", "15+"]).astype(str)
    d["oddsb"] = pd.cut(d.odds, [0, 30, 60, 100, 200, 301], labels=["〜30", "30〜60", "60〜100", "100〜200", "200〜300"]).astype(str)
    for k in range(3):
        d[f"r{k}_mk"] = d[f"r{k}_mk_rank"].clip(upper=5); d[f"r{k}_posx"] = np.where(d[f"r{k}_single"] == True, "単騎", d[f"r{k}_pos"].clip(upper=2).astype(str))
    d["nl"] = d.nlines.clip(upper=5); d["n9"] = d.entries_number == 9
    return d
FEATS = ["favb", "oddsb", "nl", "n9", "grade"] + [f"r{k}_{c}" for k in range(3) for c in ["mk", "posx", "style", "cc", "Brk", "Bb", "Sb"]]
if not os.path.exists(S + "narrow_tr.pkl"):
    tr = prep(K + "out/angle_base.pkl", S + "ent_explore.pkl")[FEATS + ["race_id", "date", "ret", "odds"]]; tr.to_pickle(S + "narrow_tr.pkl")
    te = prep(K + "out/y2024full/cache.pkl", S + "ent_2024.pkl")[FEATS + ["race_id", "date", "ret", "odds"]]; te.to_pickle(S + "narrow_te.pkl")
tr = pd.read_pickle(S + "narrow_tr.pkl"); te = pd.read_pickle(S + "narrow_te.pkl")
for d in (tr, te):
    for f in FEATS: d[f] = d[f].astype(str)
srch = tr[tr.date < "20251226"]; val = tr[tr.date >= "20251226"]
print("探す", len(srch), "確かめ①", len(val), "確かめ②(2024)", len(te))
MIN = 300  # 探す期間で最低300点
codes = {f: srch[f].astype("category") for f in FEATS}
ret = srch.ret.values
evaluated = 0
def score(mask):
    n = mask.sum(); return (ret[mask].mean() if n >= MIN else -1), n
beam = [((), np.ones(len(srch), bool))]; found = []
for depth in range(1, 6):
    cand = []
    for conds, m in beam:
        used = {c[0] for c in conds}
        for f in FEATS:
            if f in used: continue
            col = srch[f].values
            for v in pd.unique(col[m]):
                mm = m & (col == v); evaluated += 1
                r, n = score(mm)
                if r > 0: cand.append((r, n, conds + ((f, v),), mm))
    cand.sort(key=lambda x: -x[0])
    beam = [(c[2], c[3]) for c in cand[:40]]
    found += cand[:40]
    print(f"深さ{depth}: 候補 {len(cand)}、最良 {cand[0][0]*100:.0f}%（{cand[0][1]}点）", flush=True)
print("試した条件の数", evaluated)
def apply(d, conds):
    m = np.ones(len(d), bool)
    for f, v in conds: m &= (d[f].values == v)
    return d[m]
rows = []
seen = set()
for r, n, conds, _ in sorted(found, key=lambda x: -x[0]):
    key = tuple(sorted(conds))
    if key in seen: continue
    seen.add(key)
    v = apply(val, conds); t = apply(te, conds)
    rows.append((" & ".join(f"{f}={x}" for f, x in conds), n, round(100 * r), len(v), round(100 * v.ret.mean()) if len(v) else None, len(t), round(100 * t.ret.mean()) if len(t) else None))
    if len(rows) >= 40: break
R = pd.DataFrame(rows, columns=["条件", "探す点数", "探す回収率", "確かめ①点数", "確かめ①回収率", "2024点数", "2024回収率"])
print(R.to_string())
print("\n上位40の平均：探す", R.探す回収率.mean().round(), "確かめ①", R["確かめ①回収率"].mean().round(), "2024", R["2024回収率"].mean().round())
print("確かめ①・2024 とも100%超え:", ((R["確かめ①回収率"] > 100) & (R["2024回収率"] > 100)).sum(), "/", len(R))
R.to_pickle(S + "narrow_res.pkl")
