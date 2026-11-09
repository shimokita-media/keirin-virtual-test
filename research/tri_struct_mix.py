"""3連単枠・一番の目 × 形と出走表の機械（tri_struct_v1cand）の期待値で絞る。未使用 25/10/12〜26/1/14。期待値のしきい値は止めどころ(26/7〜8)でも同じ表を出して確認"""
import numpy as np, pandas as pd, lightgbm as lgb
K = "C:/Users/take0/.claude/keirin/"; SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
src = open(K + "research/sd_study.py", encoding="utf-8").read()
exec(src.split("B_in = pd.read_pickle")[0])  # prep と picks
m = lgb.Booster(model_file=K + "research/tri_struct_v1cand.txt"); F = m.feature_name()
def score(D):
    for i in range(3): D[f"r{i}_sty"] = D[f"r{i}_style"].map({"逃": 0, "両": 1, "追": 2}).astype(float)
    D["pm"] = 1 / (1 + np.exp(-(m.predict(D[F].astype(np.float32), raw_score=True) + D.lp))); D["ev"] = D.pm * D.odds; return D
VA = pd.read_pickle(SP + "tri3_all.pkl"); VA = score(prep(VA[VA.date.between("20260701", "20260831")]))
OS = score(prep(pd.concat([pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh6", "fresh7")]))); OS = OS[OS.date <= "20260114"]
rng = np.random.default_rng(0)
def st(g):
    if not len(g): return "0点"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); i = rng.integers(0, len(by), (1000, len(by))); b = by["sum"].to_numpy()[i].sum(1) / by["size"].to_numpy()[i].sum(1)
    return f"{g.ret.mean():.0%}［{np.percentile(b,2.5):.0%}〜{np.percentile(b,97.5):.0%}］（{len(g)}点・当たり{int((g.ret>0).sum())}）"
for nm, D in (("止めどころ 26/7〜8", VA), ("未使用① 25/10/12〜11/21", OS[OS.date <= "20251121"]), ("未使用② 25/11/22〜26/1/14", OS[OS.date > "20251121"])):
    B, top = picks(D); key = ["race_id", "combo"]
    B = B.merge(D[key + ["ev", "pm", "p"]], on=key); top = top.merge(D[key + ["ev", "pm", "p"]], on=key)
    print(f"\n## {nm}\n- 3連単枠 全部: {st(B)}\n- 一番の目 全部: {st(top)}")
    for t in (0.8, 0.85, 0.9, 1.0):
        print(f"- 期待値≥{t}: 3連単枠 {st(B[B.ev >= t])} ／ 一番の目 {st(top[top.ev >= t])}")
    b2 = B.sort_values("ev").groupby("race_id").tail(1)
    print(f"- 3連単枠の中で機械の期待値が一番の目に入れ替え: {st(b2)} ／ そのうち期待値≥0.9: {st(b2[b2.ev >= 0.9])}")
