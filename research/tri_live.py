"""3連単の事前登録10個（KNOWLEDGE「★事前登録G」）を、締切前の倍率（B1R/T1/T5）で選んで確定の払戻で答え合わせ（11/9以降・事後計算のみ）。
使い方: python research/tri_live.py → reports/tri_live.md。予想記録・通知には触らない。機械（9・10）は締切前でも作れる手がかりだけの簡易版 tri_model_f0.txt（11/8固定）"""
import os, subprocess, sys, sqlite3
import numpy as np, pandas as pd, lightgbm as lgb
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
WORK = os.path.join(BASE, "out", "eval_work"); START = os.environ.get("KSTART", "20261109")
lg = lambda v: np.log(np.clip(v, 1e-6, None))

def prep(T):
    T = T.copy()
    T["lp"] = np.log(T.p.clip(1e-6, 0.99) / (1 - T.p.clip(1e-6, 0.99))); T["lodds"] = lg(T.odds)
    T["g_ex"] = lg(T.ex_q) - lg(T.xy_p); T["g_tf"] = lg(T.tf_q) - lg(T.set_p); T["g_qn"] = lg(T.qn_q) - lg(T.xy_p); T["cond"] = lg(T.p) - lg(T.xy_p)
    for w in ("w12", "w13", "w23"): T["l" + w] = lg(T[w])
    for a, b in ((0, 1), (1, 2), (0, 2)): T[f"s{a}{b}"] = ((T[f"r{a}_line_idx"] == T[f"r{b}_line_idx"]) & (T[f"r{a}_line_idx"] >= 0)).astype(float)
    T["S"] = (T["class"] == "S級").astype(float); T["G"] = T.grade.astype(str).str.startswith("G").astype(float)
    return T

def rules(T, m):
    s01, s12, s02 = T.s01 == 1, T.s12 == 1, T.s02 == 1; p0, p1, p2 = T.r0_pos, T.r1_pos, T.r2_pos
    nine, d2 = T.entries_number >= 9, T.day_index >= 2; maru = T.r0_prediction_mark >= 3
    third = (p2 == 2) & s12; same3 = s01 & s12; order = same3 & (p0 == 0) & (p1 == 1) & (p2 == 2)
    R = {
     "1 9車・2日目以降・3着が同ライン3番手・60倍以下": third & (T.odds <= 60) & nine & d2,
     "2 9車・2日目以降・3着が同ライン3番手・30倍以下": third & (T.odds <= 30) & nine & d2,
     "3 9車・2日目以降・3人同じライン・30倍以下": same3 & (T.odds <= 30) & nine & d2,
     "4 9車・3人同じライン・3連複から割安・30倍以下": same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     "5 9車・3着が同ライン3番手・1着◎・30〜60倍": third & T.odds.between(30, 60) & nine & maru,
     "6 ライン順・1着◎・割安(3連複と2車単)・60倍以下": order & (T.odds <= 60) & maru & (T.g_tf > 0) & (T.g_ex > 0),
     "7 G戦9R以降・同ライン先頭→2番手・60〜100倍": s01 & (p0 == 0) & (p1 == 1) & T.odds.between(60, 100) & (T.race_no >= 9) & (T.G == 1),
     "8 G戦・1着が一番人気・3着が同ライン3番手・10倍以下": third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1),
    }
    out = {k: T[v][["race_id", "date", "combo", "odds", "ret"]] for k, v in R.items()}
    T = T.copy(); T["ev"] = 1 / (1 + np.exp(-(m.predict(T[m.feature_name()].astype(np.float32), raw_score=True) + T.lp))) * T.odds
    X = T[(T.odds <= 60) & (T.ev >= 1.1)].sort_values("ev").groupby("race_id").tail(1)
    out["9 機械(簡易)・60倍以下×1.1・1レース1点"] = X[["race_id", "date", "combo", "odds", "ret"]]
    sw = X.assign(combo=X.combo.str.split("-").map(lambda a: f"{a[0]}-{a[2]}-{a[1]}"))[["race_id", "date", "combo"]]
    sw = sw.merge(T[["race_id", "combo", "odds", "ret"]], on=["race_id", "combo"], how="left")
    sw["ret"] = sw.ret.fillna(0)  # 300倍超などで表に無い目は払戻0扱いにせず、確定の払戻を引く
    out["10 機械(簡易)・9の1点＋2着3着入替（2点）"] = pd.concat([out["9 機械(簡易)・60倍以下×1.1・1レース1点"], sw])
    Y = T[(T.odds <= 60) & (T.ev >= 1.0)].sort_values("ev").groupby("race_id").tail(1)
    out["（参考・後から追加）機械(簡易)・60倍以下×1.0・1レース1点"] = Y[["race_id", "date", "combo", "odds", "ret"]]
    return out

def main():
    from daily_eval import download
    db = download()
    c = sqlite3.connect(db)
    end = c.execute("SELECT MAX(date) FROM races WHERE race_id IN (SELECT race_id FROM results)").fetchone()[0]
    if not end or end < START: print("まだ対象日なし"); return
    pay = pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", c).drop_duplicates(["race_id", "combo"])
    m = lgb.Booster(model_file=os.path.join(HERE, "tri_model_f0.txt"))
    L = [f"# 3連単 事前登録10個の答え合わせ（{START}〜{end}・締切前の倍率で選択・各100円・確定の払戻）\n",
         "通知・予想記録とは別の事後計算。11/8までの検証は最終倍率の数字（KNOWLEDGE ★事前登録G）。\n"]
    for ph in ("B1R", "T1", "T5"):
        env = dict(os.environ, KDB=db, KPH=ph, PYTHONIOENCODING="utf-8")
        a, t = os.path.join(WORK, f"ana_{ph}.pkl"), os.path.join(WORK, f"tri_{ph}.pkl")
        subprocess.run([sys.executable, os.path.join(HERE, "ana_build.py"), START, end, a], env=env, check=True, cwd=WORK, capture_output=True)
        subprocess.run([sys.executable, os.path.join(HERE, "tri3_build.py"), a, t], env=env, check=True, cwd=WORK, capture_output=True)
        T = pd.read_pickle(t)
        if not len(T): continue
        T = prep(T); out = rules(T, m)
        L += [f"\n## {ph}（{T.race_id.nunique()}レース・{T.date.nunique()}日）\n", "| 買い方 | 点数 | レース | 当たり | 回収率 | 締切前→最終の倍率 |", "|---|---|---|---|---|---|"]
        for k, g in out.items():
            if not len(g): L.append(f"| {k} | 0 | 0 | − | − | − |"); continue
            g = g.drop(columns="ret").merge(pay, on=["race_id", "combo"], how="left"); g["ret"] = g.payout.fillna(0) / 100
            fin = g.ret[g.ret > 0] / g.odds[g.ret > 0]
            L.append(f"| {k} | {len(g)} | {g.race_id.nunique()} | {int((g.ret > 0).sum())}本 | {g.ret.mean():.0%} | {('当たりの倍率 中央' + format(np.median(fin) - 1, '+.0%')) if len(fin) else '−'} |")
    txt = "\n".join(L)
    open(os.path.join(BASE, "reports", "tri_live.md"), "w", encoding="utf-8").write(txt); print(txt)

if __name__ == "__main__":
    main()
