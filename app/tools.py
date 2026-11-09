"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import random
import re
from datetime import datetime
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAX_RESULTS = 3
# 第3回 宿題（実装）: 学習の記録の保存先。テストでは一時フォルダに差し替える
LOG_DIR = Path(__file__).resolve().parent.parent / "learning_log"


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定した回（1始まりの整数）の用語から1つを選び、確認問題と答えを返す。

    「第2回の確認問題を出して」「復習用に1問出して」のように、
    ある回の復習問題を求められたときに使う。問題と答えが
    {"question": "...", "answer": "..."} の JSON で返るので、
    それをもとに出題し、答えは利用者が考えたあとに示す。
    """
    candidates = [e for e in load_glossary() if e["lecture"] == lecture]
    if not candidates:
        available = sorted({e["lecture"] for e in load_glossary()})
        return (
            f"第{lecture}回の用語は用語集にありません。"
            f"出題できる回: {', '.join(str(n) for n in available)}"
        )
    entry = random.choice(candidates)
    return json.dumps(
        {"question": f"「{entry['term']}」の意味は？", "answer": entry["definition"]},
        ensure_ascii=False,
    )


def _safe_filename(title: str) -> str:
    """ファイル名に使えない文字を取り除く（パスの区切りや先頭のドットも許さない）。"""
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", title.strip()).strip("._")
    return name[:50] or "memo"


def save_learning_log(title: str, content: str) -> str:
    """学習の記録（気づき・疑問・要点）を learning_log/ フォルダに Markdown で保存する。

    「今日の学びを記録して」「このやり取りをメモに残して」のように、
    利用者が内容の保存を頼んだときにだけ使う。title は短い見出し、
    content は保存する本文（Markdown 可）。保存は取り消しにくい操作なので、
    このツールは実行前に利用者の承認を待つ。保存したファイルのパスを返す。
    """
    if not content.strip():
        return "保存する内容が空です。記録したい本文を content に入れてください。"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"{stamp}_{_safe_filename(title)}.md"
    body = f"# {title.strip() or '学習の記録'}\n\n{content.strip()}\n"
    path.write_text(body, encoding="utf-8")
    return f"保存しました: {path.relative_to(LOG_DIR.parent)}（{len(body)} 文字）"
