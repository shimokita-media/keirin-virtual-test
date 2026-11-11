"""探す段階：ライン順（同じライン3人で 先頭→番手→3番手）×3着の選手の得点順位。一番の目の法則に頼らない形か（一番の目を除いても割安か）。
見た3期間だけ：y4（out/y4/cache.pkl）・2024年（out/y2024full/cache.pkl）・2025/2〜2026/11/5（out/tri_base.parquet＋side_*_full）。y5・y6 は見ない。
見込み p＝確定オッズ 1/odds をレースの中で合計1（300倍以下の中で）。各100円・確定の払戻。
使い方: python -I -X utf8 research/lineorder_weak3.py reports/lineorder_weak3.md"""
import sys, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
cols = ["race_id", "combo", "date", "odds", "ret", "s01", "s12", "r0_pos", "r1_pos", "r2_pos", "is_top", "venue", "entries_number"]
def load_cache(f):
    d = pd.read_pickle(f); return d[cols + ["r2_pt_rank", "r0_pt_rank", "G"]].copy()
def load_new():
    d = duckdb.sql(f"SELECT {', '.join(cols)} FROM '{K}out/tri_base.parquet'").df()
    E = pd.read_pickle(K + "out/side_entries_full.pkl"); R = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id").set_index("race_id")
    EA = E[E.absent != 1].copy(); EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
    look = EA.set_index(["race_id", "number"]).ptr; cb = d.combo.str.split("-", expand=True).astype(int)
    d["r2_pt_rank"] = look.reindex(list(zip(d.race_id, cb[2]))).to_numpy(); d["r0_pt_rank"] = look.reindex(list(zip(d.race_id, cb[0]))).to_numpy()
    d["G"] = d.race_id.map(R.grade).fillna("").astype(str).str.startswith("G").astype(int); return d
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
PER = {}
for nm, d in (("y4", load_cache(K + "out/y4/cache.pkl")), ("2024年", load_cache(K + "out/y2024full/cache.pkl")), ("2025/2〜", load_new())):
    q = 1 / d.odds; d["p"] = q / q.groupby(d.race_id).transform("sum"); d["hit"] = (d.ret > 0).astype(float)
    d = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2)].copy()  # ライン順だけ残す
    d["bank"] = np.select([d.venue.isin(S333), d.venue.isin(S500)], ["333m系", "500m"], "400m")
    d["w3"] = pd.cut(d.r2_pt_rank, [0, 4, 6, 99], labels=["3着1〜4位", "3着5〜6位", "3着7位以下"])
    d["band"] = pd.cut(d.odds, [0, 10, 20, 40, 100, 300], labels=["〜10倍", "10〜20倍", "20〜40倍", "40〜100倍", "100〜300倍"])
    PER[nm] = d
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
def cell(g): return f"{len(g):,}点・{g.hit.sum() / g.p.sum():.2f}・**{g.ret.mean():.0%}**" if len(g) >= 30 else f"{len(g)}点（少）"
def table(title, key_fn, keys):
    P(f"## {title}" + NL + "| 区分 | " + " | ".join(PER) + " |" + NL + "|---|" + "---|" * len(PER))
    for k in keys: P(f"| {k} | " + " | ".join(cell(key_fn(d, k)) for d in PER.values()) + " |")
    P("")
P("# 探す段階：ライン順×3着の得点順位（見た3期間。各セル：点数・当たり÷見込み・回収率）" + NL)
P("ライン順＝同じライン3人で先頭→番手→3番手。確定オッズ300倍以下・各100円。y5・y6 は見ていない。" + NL)
W = ["3着1〜4位", "3着5〜6位", "3着7位以下"]
table("ライン順 全部（一番の目を含む）", lambda d, k: d[d.w3 == k], W)
table("ライン順 × 一番の目を除く", lambda d, k: d[(d.w3 == k) & ~d.is_top], W)
table("一番の目を除く × 40倍以下", lambda d, k: d[(d.w3 == k) & ~d.is_top & (d.odds <= 40)], W)
table("一番の目を除く × 3着7位以下 × 倍率の帯", lambda d, k: d[(d.w3 == "3着7位以下") & ~d.is_top & (d.band == k)], ["〜10倍", "10〜20倍", "20〜40倍", "40〜100倍", "100〜300倍"])
table("一番の目を除く × 3着7位以下 × バンク", lambda d, k: d[(d.w3 == "3着7位以下") & ~d.is_top & (d.bank == k)], ["400m", "333m系", "500m"])
table("一番の目を除く × 3着7位以下 × 車立て", lambda d, k: d[(d.w3 == "3着7位以下") & ~d.is_top & ((d.entries_number >= 9) == (k == "9車"))], ["9車", "7車以下"])
table("一番の目を除く × 3着7位以下 × グレード", lambda d, k: d[(d.w3 == "3着7位以下") & ~d.is_top & ((d.G == 1) == (k == "G戦"))], ["G戦", "F戦"])
table("一番の目を除く × 3着7位以下 × 1着の得点順位", lambda d, k: d[(d.w3 == "3着7位以下") & ~d.is_top & {"1着1位": d.r0_pt_rank == 1, "1着2〜3位": d.r0_pt_rank.between(2, 3), "1着4位以下": d.r0_pt_rank >= 4}[k]], ["1着1位", "1着2〜3位", "1着4位以下"])
print("done")
