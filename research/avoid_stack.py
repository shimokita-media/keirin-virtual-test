"""30倍以下の3連単から、過去に3期間とも割高だった目を外すと回収率はどうなるか（引き算）。新しい切り口は探さない：外す目は KNOWLEDGE.md・ANGLES.md に記録済みのものだけ。
データ：out/tri_base.parquet（確定オッズ300倍以下・L級除く・2025/2〜2026/11/5）＋ out/side_entries_full.pkl・side_races_full.pkl（写し。取り込み中のDBは読まない）。
期間：探す＝2025/2〜2026/8（③除く）、③＝2025/10/12〜2026/1/14、⑥＝2026/9/1〜。確定の払戻・各100円。
使い方: python -I -X utf8 research/avoid_stack.py reports/avoid_stack.md"""
import sys, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
T = duckdb.sql(f"SELECT race_id, combo, date, odds, ret, race_type, r0_pos, r1_pos, r2_pos, s01, s12, is_top FROM '{K}out/tri_base.parquet'").df()
T["fav"] = T.groupby("race_id").odds.transform("min")  # 300倍以下の中の一番人気＝そのレースの一番人気
E = pd.read_pickle(K + "out/side_entries_full.pkl"); R = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
E = E.merge(R[["race_id", "date", "cup_id"]], on="race_id", how="left")
ab = set(E[E.absent == 1].race_id)
EA = E[E.absent != 1].copy()
EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
# 新人＝その月の一番新しい期から2期以内（z_predict の tgap と同じ作り：tgap≦1）
EA["term"] = pd.to_numeric(EA.term, errors="coerce"); EA["ym"] = EA.date.str[:6]; EA["tgap"] = EA.groupby("ym").term.transform("max") - EA.term
# 休み明け＝前の開催の最終日から21日以上空いた（中何日の切り口と同じ）
EA["d"] = pd.to_datetime(EA.date)
cup = EA.groupby(["player_id", "cup_id"]).d.agg(["min", "max"]).reset_index().sort_values(["player_id", "min"])
cup["rest"] = (cup["min"] - cup.groupby("player_id")["max"].shift()).dt.days - 1
EA = EA.merge(cup[["player_id", "cup_id", "rest"]], on=["player_id", "cup_id"], how="left")
key = lambda df, j: list(zip(df.race_id, df.combo.str.split("-").str[j].astype(int)))
look = EA.set_index(["race_id", "number"])
for j, nm in ((0, "a"), (2, "c")):
    sub = look.reindex(key(T, j))
    T[f"{nm}_ptr"] = sub.ptr.to_numpy(); T[f"{nm}_rest"] = sub.rest.to_numpy(); T[f"{nm}_tgap"] = sub.tgap.to_numpy()
rt = T.race_type.fillna("").astype(str)
AV = [
    ("欠場があったレース", T.race_id.isin(ab)),
    ("本命がはっきり（一番人気3倍以下）", T.fav <= 3),
    ("得点1位を1着", T.a_ptr == 1),
    ("休み明け（中21日以上）を1着", T.a_rest >= 21),
    ("新人（2期以内）を3着", T.c_tgap <= 1),
    ("決勝のライン3人", rt.str.contains("決勝") & ~rt.str.contains("準") & (T.s01 == 1) & (T.s12 == 1)),
    ("準決勝の番手→先頭", rt.str.contains("準決勝") & (T.r0_pos == 1) & (T.r1_pos == 0) & (T.s01 == 1)),
]
def per(d): return np.select([d.between("20251012", "20260114"), d >= "20260901"], ["③", "⑥"], "探す")
T["per"] = per(T.date)
rng = np.random.default_rng(0)
def st(g):
    if len(g) < 2: return "−"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (1000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    return f"{g.ret.mean():.0%}（{len(g):,}点・{int((g.ret > 0).sum())}本・{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}）"
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
P("# 30倍以下の3連単から、割高な目を外す（引き算・確定オッズ）" + NL)
P(f"{T.date.min()}〜{T.date.max()}・{T.race_id.nunique():,}R。外す目は記録済みのものだけ（新しく探していない）。カッコは点数・当たり・レース単位ブートストラップの95%の範囲。" + NL)
for cap in (30, 50, 100):
    X = T[T.odds <= cap]; keep = pd.Series(True, index=X.index)
    P(f"## {cap}倍以下" + NL + "| 段階 | 探す | ③ | ⑥ |" + NL + "|---|---|---|---|")
    P(f"| 全部 | " + " | ".join(st(X[X.per == p]) for p in ("探す", "③", "⑥")) + " |")
    for nm, m in AV:
        mm = m.loc[X.index].fillna(False).astype(bool)
        P(f"| 　（この目だけ：{nm}） | " + " | ".join(st(X[mm & (X.per == p)]) for p in ("探す", "③", "⑥")) + " |")
        keep &= ~mm
        P(f"| ＋{nm}を外す | " + " | ".join(st(X[keep & (X.per == p)]) for p in ("探す", "③", "⑥")) + " |")
    P(NL + f"残った割合：{keep.mean():.0%}（{int(keep.sum()):,}点 / {len(X):,}点）" + NL)
    if cap == 30:
        P("### 参考：一番の目と重ねる（30倍以下・全部外した残り）" + NL)
        P("| | 探す | ③ | ⑥ |" + NL + "|---|---|---|---|")
        P("| 一番の目 | " + " | ".join(st(X[X.is_top & (X.per == p)]) for p in ("探す", "③", "⑥")) + " |")
        P("| 一番の目×外した残り | " + " | ".join(st(X[X.is_top & keep & (X.per == p)]) for p in ("探す", "③", "⑥")) + " |" + NL)
print("done")
