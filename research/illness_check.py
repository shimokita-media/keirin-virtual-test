"""探す段階：インタビューで病気の言葉（インフル・発熱・風邪・体調を崩す など）を言った選手は、市場の見込みより来ないか（ユーザーの質問から。2026-11-11）。
材料と打ち消しの判定は research/interview_eval.py と同じ（前検日インタビュー＋同じ開催の前の日までのレース後インタビュー＝そのレースの前に分かる情報。言葉のすぐ後ろ20文字に「ことなく」「治っ」などがあれば数えない）。
市場の見込み：確定の3連単（300倍以下）の確率 p（1/倍率をレースの中で合計1）から、その選手を含む組の合計＝3着以内の見込み q、1着の組の合計＝1着の見込み q1。
データ：interviews・result_interviews はローカルDBを小分けに読み取り専用で（取り込み中なので）。3連単は out/tri_base.parquet（2025/12/1〜2026/11/5）、選手・レースは side_*_full。
使い方: python -I -X utf8 research/illness_check.py reports/illness_check.md"""
import sys, json, re, time, sqlite3, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
ILL = ["インフル", "発熱", "熱が", "熱っぽ", "熱を出", "コロナ", "風邪", "体調を崩", "体調崩", "体調不良", "咳", "喉", "胃腸", "腹痛", "下痢", "嘔吐", "点滴", "寝込"]
NEGATORS = ["問題な", "問題無", "問題は無", "問題はな", "問題もな", "問題も無", "大丈夫", "心配な", "心配は無", "心配はな", "ではな", "じゃな", "ではありません",
            "ことはな", "事はな", "ことなく", "事なく", "わけではな", "訳ではな", "治っ", "治り", "治ま", "影響はな", "影響な", "気にならな",
            "はない", "もない", "は無い", "も無い", "はありません", "もありません", "はなかった", "もなかった"]
END = re.compile(r"[。！!？?\n]")
def hit(txt, w):
    i = txt.find(w)
    while i >= 0:
        j = i + len(w); m = END.search(txt, j); seg = txt[j: min(m.start() if m else len(txt), j + 20)]
        if not any(n in seg for n in NEGATORS) or any(u in seg for u in ("とは言え", "とはいえ", "とも言え", "わけじゃな", "訳じゃな", "とは言いきれ", "とは言い切れ")): return True
        i = txt.find(w, i + 1)
    return False
def answers(qa):
    try: return " ".join(t.get("answer", "") for t in json.loads(qa))
    except Exception: return ""
def read_chunked(sql_tail, cols):
    con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
    mx = con.execute(f"SELECT MAX(rowid) FROM {sql_tail.split()[0]}").fetchone()[0] or 0
    out = []
    for lo in range(0, mx + 1, 3000):
        out += con.execute(f"SELECT {cols} FROM {sql_tail} {'AND' if 'WHERE' in sql_tail else 'WHERE'} rowid > ? AND rowid <= ?", (lo, lo + 3000)).fetchall()
        time.sleep(0.3)
    con.close(); return out
IV = pd.DataFrame(read_chunked("interviews WHERE kind='前検'", "cup_id, player_id, qa_json"), columns=["cup_id", "player_id", "qa_json"])
RI = pd.DataFrame(read_chunked("result_interviews", "race_id, player_id, qa_json"), columns=["race_id", "player_id", "qa_json"])
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")[["race_id", "date", "cup_id", "day_index"]]
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0][["race_id", "number", "player_id"]].drop_duplicates(["race_id", "number"])
R = pd.read_pickle(K + "out/side_results_full.pkl"); R["rank"] = pd.to_numeric(R["rank"], errors="coerce")
top3 = set(zip(R[R["rank"] <= 3].race_id, R[R["rank"] <= 3].number)); win = set(zip(R[R["rank"] == 1].race_id, R[R["rank"] == 1].number))
T = duckdb.sql(f"SELECT race_id, combo, date, odds, ret FROM '{K}out/tri_base.parquet' WHERE date >= '20251201'").df()
q_ = 1 / T.odds; T["p"] = q_ / q_.groupby(T.race_id).transform("sum")
E = E.merge(RA, on="race_id"); E = E[E.date.between("20251201", "20261105")]
IV["txt"] = IV.qa_json.map(answers)
E = E.merge(IV[["cup_id", "player_id", "txt"]].rename(columns={"txt": "t_pre"}), on=["cup_id", "player_id"], how="left")
RI = RI.merge(RA, on="race_id"); RI["txt"] = RI.qa_json.map(answers)
prev = E[["race_id", "cup_id", "day_index", "player_id"]].merge(RI[["cup_id", "player_id", "day_index", "txt"]].rename(columns={"day_index": "d_iv"}), on=["cup_id", "player_id"])
prev = prev[prev.d_iv < prev.day_index].groupby(["race_id", "player_id"]).txt.agg(" ".join).rename("t_post").reset_index()
E = E.merge(prev, on=["race_id", "player_id"], how="left")
E["txt"] = E.t_pre.fillna("") + " " + E.t_post.fillna("")
E["has"] = E.txt.str.strip() != ""
E["ill_words"] = E.txt.map(lambda s: [w for w in ILL if hit(s, w)])
E["ill"] = E.ill_words.str.len() > 0
X = T.assign(n=T.combo.str.split("-")).explode("n"); X["number"] = X.n.astype(int)
q3 = X.groupby(["race_id", "number"]).p.sum().rename("q3").reset_index()
T["first"] = T.combo.str.split("-").str[0].astype(int)
q1 = T.groupby(["race_id", "first"]).p.sum().rename("q1").reset_index().rename(columns={"first": "number"})
E = E.merge(q3, on=["race_id", "number"]).merge(q1, on=["race_id", "number"], how="left"); E["q1"] = E.q1.fillna(0)
E["y3"] = [int((r, n) in top3) for r, n in zip(E.race_id, E.number)]; E["y1"] = [int((r, n) in win) for r, n in zip(E.race_id, E.number)]
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 探す段階：インタビューで病気の言葉を言った選手（2025/12〜2026/11/5、確定オッズ）" + NL)
P(f"選手×レース {len(E):,}（インタビューあり {E.has.sum():,}、うち病気の言葉 {E.ill.sum():,}・{E[E.ill].player_id.nunique()}人）・レース {E.race_id.nunique():,}" + NL)
cnt = pd.Series([w for ws in E[E.ill].ill_words for w in ws]).value_counts()
P("言葉ごとの件数（選手×レース）：" + "、".join(f"{k} {v}" for k, v in cnt.items()) + NL)
def row(nm, g):
    if len(g) == 0: return f"| {nm} | 0 | − | − | − | − |"
    a3, e3, a1, e1 = g.y3.sum(), g.q3.sum(), g.y1.sum(), g.q1.sum()
    d = (g.y3 - g.q3).to_numpy(); t = d.mean() / (d.std() / np.sqrt(len(d))) if len(d) > 1 and d.std() > 0 else np.nan
    return f"| {nm} | {len(g):,} | {int(a3)}（見込み {e3:.1f}） | **{a3 / e3:.2f}**（t {t:+.2f}） | {int(a1)}（見込み {e1:.1f}） | **{a1 / e1 if e1 else float('nan'):.2f}** |"
P("## 3着以内・1着：実際÷市場の見込み" + NL + "| 選手 | 人×レース | 3着以内 | 実際÷見込み | 1着 | 実際÷見込み |" + NL + "|---|---|---|---|---|---|")
H = E[E.has]
for nm, g in (("病気の言葉あり", H[H.ill]), ("　前検日インタビューで", H[H.ill & H.t_pre.fillna("").map(lambda s: any(hit(s, w) for w in ILL))]),
              ("　開催1日目のレース", H[H.ill & (H.day_index == 1)]), ("　2日目以降のレース", H[H.ill & (H.day_index >= 2)]),
              ("　インフル・発熱・熱・コロナだけ", H[H.ill_words.map(lambda ws: any(w in ws for w in ("インフル", "発熱", "熱が", "熱っぽ", "熱を出", "コロナ")))]),
              ("インタビューあり・病気の言葉なし", H[~H.ill])):
    P(row(nm, g))
P(NL + "## その選手を含む3連単（300倍以下・各100円）" + NL)
ill_set = set(zip(H[H.ill].race_id, H[H.ill].number)); has_r = set(H.race_id)
cb = T.combo.str.split("-", expand=True).astype(int); T["inc"] = [any((r, int(x)) in ill_set for x in row_) for r, row_ in zip(T.race_id, cb.to_numpy())]
T["ill1"] = [(r, int(a)) in ill_set for r, a in zip(T.race_id, cb[0])]
TT = T[T.race_id.isin(set(H[H.ill].race_id))]
P(f"病気の言葉の選手がいるレース {TT.race_id.nunique():,}R：含む組 {TT.inc.sum():,}点・{TT[TT.inc].ret.mean():.0%}／含まない組 {(~TT.inc).sum():,}点・{TT[~TT.inc].ret.mean():.0%}／その選手が1着の組 {TT.ill1.sum():,}点・{TT[TT.ill1].ret.mean():.0%}")
P(NL + f"参考：3連単全部（同じ期間）{T.ret.mean():.0%}")
print("done", E.ill.sum())
