"""合格した2つの手法を、本番の記録で毎日つける（2026-11-14 作成。仮想の記録だけで、実際の購入はしない）。
 ①ライン順×15倍以下・期待値1.2以上（E1。式・係数は research/lo_forward_t1.py と同じ＝lo_feats.py・lo_model_coef_4yr.json の固定）
 ②一番の目×割高な目を外す（7つの外し方は research/prereg_eval_y4_avoid.py と同じ）
それぞれ2通りで拾う： 「1分前」＝締切1分前の倍率で選ぶ（実際に買える形）／「確定」＝確定オッズで選ぶ（過去の検証と同じ形。買う時点では分からない）
 ※②の一番の目そのものは、どちらも1分前の表の一番の目（確定は「30倍以下」「一番人気3倍以下」だけ確定オッズで見る）
記録は reports/passed_forward_picks.csv に足すだけ（一度書いた行は書き換えない）。まとめは reports/passed_forward.md。
①の成績は、lo_forward_t1.py の決まり（E3 が500点たまるまで成績を出さない）に合わせて、まとめでは点数だけ出す。
入力：out/angle_base_t1.pkl（research/daily_forward.py が作る）、out/side_*_full.pkl、out/live_db/keirin.sqlite（確定オッズを日ごとに短く読むだけ）
使い方: python -I -X utf8 research/passed_forward.py"""
import os, json, sqlite3, datetime as dt, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
CSV = K + "reports/passed_forward_picks.csv"; MD = K + "reports/passed_forward.md"
N_E1 = "ライン順×15倍以下・期待値1.2以上"; N_AV = "一番の目×割高な目を外す"
HIDE = {N_E1}   # まとめで成績を伏せる手法
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
C = json.load(open(K + "research/lo_model_coef_4yr.json", encoding="utf-8")); assert C["cols"] == ["const"] + LO_COLS
T = pd.read_pickle(K + "out/angle_base_t1.pkl").reset_index(drop=True)
days = sorted(T.date.unique())
# 確定オッズ
con = sqlite3.connect("file:" + K + "out/live_db/keirin.sqlite?mode=ro", uri=True, timeout=30)
F = pd.concat([pd.read_sql("SELECT race_id, combo, odds AS odds_f, fetched_at FROM odds WHERE phase='POST' AND bet_type='3連単' AND race_id LIKE ?", con, params=("%" + dy,)) for dy in days])
con.close()
F = F.sort_values("fetched_at").drop_duplicates(["race_id", "combo"], keep="last").drop(columns="fetched_at")
T = T.merge(F, on=["race_id", "combo"], how="left"); T["odds_t1"] = T.odds
# ---- ① E1（lo_forward_t1.py と同じ） ----
T["hit"] = (T.ret > 0).astype(float)
Wn = T[T.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
R = T.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
R["lw"] = R.race_id.map(Wn).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan); R = R.set_index("race_id")
T["flow"] = T.race_id.map(R.flow); T["n_prev"] = T.race_id.map(R.n_prev)
def e1(d, oc):
    d = d[d[oc] <= 300].copy(); q = 1 / d[oc]; d["pn"] = q / q.groupby(d.race_id).transform("sum"); d["odds"] = d[oc]
    lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy()
    if not len(lo): return lo.assign(ev=[])
    lo["ratio"] = lo_ratio(C["coef"], lo); lo["ev"] = lo.ratio * lo.pn * lo.odds; return lo[lo.ev >= 1.2]
# ---- ② 割高な目を外す（prereg_eval_y4_avoid.py と同じ） ----
E = pd.read_pickle(K + "out/side_entries_full.pkl"); SR = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
E = E.merge(SR[["race_id", "date", "cup_id"]], on="race_id", how="left")
ab = set(E[E.absent == 1].race_id); EA = E[E.absent != 1].copy()
EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
EA["term"] = pd.to_numeric(EA.term, errors="coerce"); EA["ym"] = EA.date.str[:6]; EA["tgap"] = EA.groupby("ym").term.transform("max") - EA.term
EA["d"] = pd.to_datetime(EA.date)
cup = EA.groupby(["player_id", "cup_id"]).d.agg(["min", "max"]).reset_index().sort_values(["player_id", "min"])
cup["rest"] = (cup["min"] - cup.groupby("player_id")["max"].shift()).dt.days - 1
EA = EA.merge(cup[["player_id", "cup_id", "rest"]], on=["player_id", "cup_id"], how="left")
look = EA.drop_duplicates(["race_id", "number"]).set_index(["race_id", "number"])
def avoid(d, oc):
    d = d[d[oc].notna()].copy(); d["fav"] = d.groupby("race_id")[oc].transform("min")
    top = d[d.is_top & (d[oc] <= 30)].copy()
    if not len(top): return top
    for j, nm in ((0, "a"), (2, "c")):
        sub = look.reindex(list(zip(top.race_id, top.combo.str.split("-").str[j].astype(int))))
        top[f"{nm}_ptr"] = sub.ptr.to_numpy(); top[f"{nm}_rest"] = sub.rest.to_numpy(); top[f"{nm}_tgap"] = sub.tgap.to_numpy()
    rt = top.race_type.fillna("").astype(str)
    bad = (top.race_id.isin(ab) | (top.fav <= 3) | (top.a_ptr == 1) | (top.a_rest >= 21) | (top.c_tgap <= 1)
           | (rt.str.contains("決勝") & ~rt.str.contains("準") & (top.s01 == 1) & (top.s12 == 1))
           | (rt.str.contains("準決勝") & (top.r0_pos == 1) & (top.r1_pos == 0) & (top.s01 == 1)))
    return top[~bad]
now = dt.datetime.now().strftime("%Y-%m-%d %H:%M"); rows = []
for nm, fn in ((N_E1, e1), (N_AV, avoid)):
    for kind, oc in (("1分前", "odds_t1"), ("確定", "odds_f")):
        p = fn(T, oc)
        if not len(p): continue
        o = p[["date", "race_id", "venue", "race_no", "combo", "odds_t1", "odds_f", "ret"]].copy()
        o["ev"] = p.ev.round(3) if "ev" in p else np.nan
        o.insert(0, "kind", kind); o.insert(0, "method", nm); o["recorded_at"] = now; rows.append(o)
COLS = ["method", "kind", "date", "race_id", "venue", "race_no", "combo", "odds_t1", "odds_f", "ev", "ret", "recorded_at"]
new = pd.concat(rows)[COLS] if rows else pd.DataFrame(columns=COLS)
KEY = ["method", "kind", "race_id", "combo"]
if os.path.exists(CSV):
    old = pd.read_csv(CSV, dtype={"date": str, "race_id": str, "combo": str})
    seen = set(map(tuple, old[KEY].to_numpy())); add = new[[k not in seen for k in map(tuple, new[KEY].to_numpy())]]
    allp = pd.concat([old, add], ignore_index=True)
else:
    add = new; allp = new.copy()
allp = allp.sort_values(["date", "race_id", "method", "kind"]).reset_index(drop=True)
allp.to_csv(CSV, index=False, encoding="utf-8-sig")
# ---- まとめ ----
rng = np.random.default_rng(0)
def line(nm, kind):
    g = allp[(allp.method == nm) & (allp.kind == kind)]; n = len(g)
    if nm in HIDE: return f"| {nm} | {kind} | {n}点 | （伏せる） | （伏せる） | （伏せる） | — |"
    if n == 0: return f"| {nm} | {kind} | 0点 | — | — | — | — |"
    h = int((g.ret > 0).sum()); by = g.groupby("race_id").ret.agg(["sum", "size"])
    if len(by) >= 30:
        ii = rng.integers(0, len(by), (4000, len(by))); bs = by["sum"].to_numpy()[ii].sum(1) / by["size"].to_numpy()[ii].sum(1)
        rg = f"{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}"
    else: rg = "判定保留（30点未満）"
    return f"| {nm} | {kind} | {n}点 | {h}本 | {h / n:.0%} | **{g.ret.mean():.0%}** | {rg} |"
ad = sorted(allp.date.unique()) if len(allp) else days
L = [f"# 合格した2手法の本番記録（{days[0]}〜{days[-1]}・{len(days)}日・{T.race_id.nunique()}R）", "",
     f"更新 {now}。仮想の記録（実際の購入なし）・各100円・確定の払戻。今回足した行：{len(add)}。", "",
     "- 「1分前」＝締切1分前の倍率で選ぶ（実際に買える形）。「確定」＝確定オッズで選ぶ（過去の検証と同じ形・参考）",
     f"- 「{N_E1}」の成績は、ライン順の前向き確認の決まり（500点たまるまで成績を出さない）に合わせて伏せ、点数だけ出す", "",
     "## これまでの合計", "", "| 手法 | 選び方 | 点数 | 当たり | 的中率 | 回収率 | 95%の範囲 |", "|---|---|---|---|---|---|---|"]
for nm in (N_E1, N_AV):
    for kind in ("1分前", "確定"): L.append(line(nm, kind))
L += ["", "## 日ごと", "", f"| 日付 | レース数 | {N_E1}（1分前／確定）の点数 | {N_AV}・1分前 | {N_AV}・確定 |", "|---|---|---|---|---|"]
nr = T.groupby("date").race_id.nunique()
def cell(g): return "0点" if not len(g) else f"{len(g)}点・{int((g.ret > 0).sum())}本・{g.ret.mean():.0%}"
for dy in days:
    x = allp[allp.date == dy]; a = x[x.method == N_E1]; b = x[x.method == N_AV]
    L.append(f"| {dy[4:6]}/{dy[6:]} | {nr.get(dy, 0)} | {(a.kind == '1分前').sum()}点／{(a.kind == '確定').sum()}点 | {cell(b[b.kind == '1分前'])} | {cell(b[b.kind == '確定'])} |")
last = allp[(allp.date == days[-1]) & (allp.kind == "1分前")]
L += ["", f"## 最新の日（{days[-1][4:6]}/{days[-1][6:]}）に1分前で選んだ目", ""]
if len(last):
    L += ["| 手法 | 場・R | 目 | 1分前の倍率 | 確定の倍率 | 結果 |", "|---|---|---|---|---|---|"]
    for r in last.itertuples():
        res = "（伏せる）" if r.method in HIDE else ("当たり %.1f倍" % r.ret if r.ret > 0 else "外れ")
        L.append(f"| {r.method} | {r.venue} {int(r.race_no)}R | {r.combo} | {r.odds_t1:.1f} | {r.odds_f:.1f} | {res} |")
else: L.append("なし")
L += ["", "全部の行は reports/passed_forward_picks.csv（足すだけ・書き換えない）。"]
open(MD, "w", encoding="utf-8").write(NL.join(L) + NL)
print(f"done 日 {days[0]}〜{days[-1]} 新しい行 {len(add)} 合計 {len(allp)}")
