"""第2回 宿題（発展）: 用語集から SFT 用の Q&A データ（JSONL）を作る。

使い方:
    uv run python scripts/make_sft_dataset.py > glossary_sft.jsonl
    uv run python scripts/make_sft_dataset.py --aliases --negatives > glossary_sft.jsonl

できたファイルを Colab にアップロードし、LoRA 学習のデータとして使う。
質問の言い回しを増やす、別名でも質問を作る、検証用に一部を分ける、などを工夫してみよう。

--aliases   用語の別名（aliases）でも質問を作る（1 用語につき 2 つまで）
--negatives 用語集に無い語を聞かれたときに「用語集にありません」と答える例を加える
            （評価で使う「用語集にない語」とは重ならない語を使う）
"""

import argparse
import json
import sys
from pathlib import Path

GLOSSARY = Path(__file__).resolve().parent.parent / "data" / "glossary.json"
TEMPLATES = ["「{term}」とは何ですか？", "{term}について簡単に説明してください。"]
ALIAS_TEMPLATE = "「{term}」とは何ですか？"
MAX_ALIASES = 2

NOT_IN_GLOSSARY = "この用語は講座の用語集にありません。"
# 学習用の「用語集にない語」。評価に使う語（RLHF、知識蒸留、MoE など）とは重ねない
NEGATIVE_TERMS = [
    "Docker", "Kubernetes", "強化学習", "転移学習", "ビームサーチ",
    "ベクトルデータベース", "GAN", "Transformer", "CI/CD", "Jupyter Notebook",
]


def records(terms: list[dict], aliases: bool, negatives: bool):
    for t in terms:
        for template in TEMPLATES:
            yield template.format(term=t["term"]), t["definition"]
        if aliases:
            seen = {t["term"].casefold()}
            used = 0
            for a in t["aliases"]:
                # 「r」のような 1 文字の別名や、用語名と同じ表記は質問にしない
                if len(a) < 2 or a.casefold() in seen or used >= MAX_ALIASES:
                    continue
                seen.add(a.casefold())
                used += 1
                yield ALIAS_TEMPLATE.format(term=a), t["definition"]
    if negatives:
        for word in NEGATIVE_TERMS:
            for template in TEMPLATES:
                yield template.format(term=word), NOT_IN_GLOSSARY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aliases", action="store_true", help="別名でも質問を作る")
    parser.add_argument("--negatives", action="store_true", help="用語集に無い語への応答例を加える")
    args = parser.parse_args()

    terms = json.loads(GLOSSARY.read_text(encoding="utf-8"))["terms"]
    for question, answer in records(terms, args.aliases, args.negatives):
        record = {
            "messages": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        }
        sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
