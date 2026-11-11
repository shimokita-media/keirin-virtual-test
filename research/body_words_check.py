"""探す段階：インタビューで体の不調（病気・腰・骨折・落車・痛み）を言った選手は、市場の見込みより来ないか（ユーザーの質問「インフルとか」「ヘルニアとか腰がとかもな」から。2026-11-11）。
research/illness_check.py の一般化。材料・打ち消し・見込みの作り方は illness_check.py（＝interview_eval.py）と同じ。言葉の種類ごとに出す。
データ：インタビューは引数の pickle（無ければローカルDBを小分けに読み取り専用で）、3連単は out/tri_base.parquet（2025/12/1〜2026/11/5）、選手・レースは side_*_full。
使い方: python -I -X utf8 research/body_words_check.py reports/body_words_check.md [前検の.pkl レース後の.pkl]"""
import sys, os, json, re, time, sqlite3, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
CATS = {
    "病気：インフル・発熱・熱・コロナ": ["インフル", "発熱", "熱が", "熱っぽ", "熱を出", "コロナ"],
    "病気：風邪・体調を崩す・胃腸など": ["風邪", "体調を崩", "体調崩", "体調不良", "咳", "喉", "胃腸", "腹痛", "下痢", "嘔吐", "点滴", "寝込"],
    "腰：ヘルニア・腰痛・腰": ["ヘルニア", "腰痛", "腰"],
    "骨折・大きなケガ：骨折・鎖骨・肋骨・手術・縫う": ["骨折", "鎖骨", "肋骨", "手術", "縫っ", "縫う"],
    "落車・打撲・すり傷": ["落車", "打撲", "擦過", "すり傷", "擦り傷"],
    "その他の痛み：膝・肩・足首・手首・痛み・ケガ": ["膝", "肩", "足首", "手首", "痛み", "痛い", "ケガ", "怪我"],
}
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
def read_chunked(tbl, cols, where=""):
    con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
    mx = con.execute(f"SELECT MAX(rowid) FROM {tbl}").fetchone()[0] or 0; out = []
    for lo in range(0, mx + 1, 3000):
        out += con.execute(f"SELECT {cols} FROM {tbl} WHERE rowid > ? AND rowid <= ? {where}", (lo, lo + 3000)).fetchall(); time.sleep(0.3)
    con.close(); return out
if len(sys.argv) >= 4 and os.path.exists(sys.argv[2]):
    IV, RI = pd.read_pickle(sys.argv[2]), pd.read_pickle(sys.argv[3])
else:
    IV = pd.DataFrame(read_chunked("interviews", "cup_id, player_id, qa_json", "AND kind='前検'"), columns=["cup_id", "player_id", "qa_json"])
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
E = E[E.txt.str.strip() != ""].copy()
for c, ws in CATS.items(): E[c] = E.txt.map(lambda s, ws=ws: any(hit(s, w) for w in ws))
E["any"] = E[list(CATS)].any(axis=1)
X = T.assign(n=T.combo.str.split("-")).explode("n"); X["number"] = X.n.astype(int)
q3 = X.groupby(["race_id", "number"]).p.sum().rename("q3").reset_index()
T["first"] = T.combo.str.split("-").str[0].astype(int)
q1 = T.groupby(["race_id", "first"]).p.sum().rename("q1").reset_index().rename(columns={"first": "number"})
E = E.merge(q3, on=["race_id", "number"]).merge(q1, on=["race_id", "number"], how="left"); E["q1"] = E.q1.fillna(0)
E["y3"] = [int((r, n) in top3) for r, n in zip(E.race_id, E.number)]; E["y1"] = [int((r, n) in win) for r, n in zip(E.race_id, E.number)]
cb = T.combo.str.split("-", expand=True).astype(int); T["a"] = cb[0]
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 探す段階：インタビューで体の不調を言った選手（2025/12〜2026/11/5、確定オッズ）" + NL)
P(f"インタビューのある選手×レース {len(E):,}・レース {E.race_id.nunique():,}。打ち消し（「腰は問題ない」「痛みは治りました」など）は数えない。1人が複数の種類に入ることがある" + NL)
P("| 種類 | 人×レース | 3着以内 実際÷見込み | t | 1着 実際÷見込み | その選手が1着の3連単 | 同じレースの他の組 |" + NL + "|---|---|---|---|---|---|---|")
base = E[~E["any"]]
for c in list(CATS) + ["any"]:
    g = E[E[c]]
    if len(g) < 2: P(f"| {c} | {len(g)} | − | − | − | − | − |"); continue
    d = (g.y3 - g.q3).to_numpy(); t = d.mean() / (d.std() / np.sqrt(len(d)))
    s = set(zip(g.race_id, g.number)); TT = T[T.race_id.isin(set(g.race_id))]
    m1 = np.array([(r, a) in s for r, a in zip(TT.race_id, TT.a)])
    P(f"| {'どれか1つでも' if c == 'any' else c} | {len(g):,}（{g.player_id.nunique()}人） | **{g.y3.sum() / g.q3.sum():.2f}** | {t:+.2f} | **{g.y1.sum() / g.q1.sum():.2f}** | {TT[m1].ret.mean():.0%}（{m1.sum():,}点） | {TT[~m1].ret.mean():.0%} |")
P(f"| 比べる：どれも言っていない | {len(base):,} | {base.y3.sum() / base.q3.sum():.2f} | − | {base.y1.sum() / base.q1.sum():.2f} | − | − |")
P(NL + f"参考：3連単全部（同じ期間）{T.ret.mean():.0%}。見込みは300倍以下の組だけで作るので、全体の「実際÷見込み」は1より少し上に出る（比べる行と比べて読む）")
print("done")
