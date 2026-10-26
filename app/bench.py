"""第1回 宿題（発展）: 応答時間とトークン数をモデル・質問ごとに計測する。

使い方:
    uv run python -m app.bench                       # 既定の3モデル x 2問 x 3回
    uv run python -m app.bench --models gemini-3.5-flash-lite --runs 5
    uv run python -m app.bench --out lectures/01/bench.csv

1回ごとに 応答時間[s]・入力/出力/思考トークン数・レート制限(429)の有無 を記録し、
最後にモデル x 質問ごとの中央値を表にする。429 が返ったら待ってから同じ呼び出しをやり直し、
待った時間も記録する（無料枠の制限がどれくらい効くかを見るため）。
"""

import argparse
import csv
import statistics
import time

from google import genai
from google.genai import errors

from app.config import get_api_key

MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
QUESTIONS = {
    "general": "LoRAとは何ですか？3文以内で答えてください。",
    "course": "AIE2026の講座の宿題にある「3レベル」とは何ですか？",
}
FIELDS = ["model", "question", "run", "seconds", "input_tokens", "output_tokens", "thinking_tokens", "retries_429", "waited_s", "chars", "error"]


def measure(client, model: str, question: str, max_retries: int = 3, wait_s: float = 30.0, clock=time.perf_counter, sleep=time.sleep) -> dict:
    """1回呼び出して計測する。429 は wait_s 待って最大 max_retries 回やり直す（待ち時間は応答時間に含めない）。"""
    retries, waited = 0, 0.0
    while True:
        t0 = clock()
        try:
            r = client.models.generate_content(model=model, contents=question)
        except errors.APIError as e:
            if e.code == 429 and retries < max_retries:
                retries += 1
                sleep(wait_s)
                waited += wait_s
                continue
            return dict(seconds=None, input_tokens=None, output_tokens=None, thinking_tokens=None,
                        retries_429=retries, waited_s=waited, chars=0, error=f"{e.code}")
        dt = clock() - t0
        u = r.usage_metadata
        return dict(seconds=round(dt, 3), input_tokens=getattr(u, "prompt_token_count", None),
                    output_tokens=getattr(u, "candidates_token_count", None),
                    thinking_tokens=getattr(u, "thoughts_token_count", None),
                    retries_429=retries, waited_s=waited, chars=len(r.text or ""), error="")


def summarize(rows: list[dict]) -> list[str]:
    """モデル x 質問ごとに中央値を Markdown の表にする。"""
    out = ["| model | question | n | 応答時間 中央値[s] | 入力 | 出力 | 思考 | 429 |", "|---|---|---|---|---|---|---|---|"]
    keys = sorted({(r["model"], r["question"]) for r in rows})
    for m, q in keys:
        ok = [r for r in rows if r["model"] == m and r["question"] == q and not r["error"]]
        med = lambda k: statistics.median([r[k] for r in ok if r[k] is not None]) if any(r[k] is not None for r in ok) else "-"  # noqa: E731
        n429 = sum(r["retries_429"] for r in rows if r["model"] == m and r["question"] == q)
        out.append(f"| {m} | {q} | {len(ok)} | {med('seconds')} | {med('input_tokens')} | {med('output_tokens')} | {med('thinking_tokens')} | {n429} |")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="応答時間とトークン数を計測する")
    p.add_argument("--models", nargs="+", default=MODELS)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--interval", type=float, default=4.0, help="呼び出しの間隔[s]（無料枠の1分あたりの上限に当たりにくくする）")
    p.add_argument("--out", default="lectures/01/bench.csv")
    a = p.parse_args()

    client = genai.Client(api_key=get_api_key())
    rows = []
    for model in a.models:
        for qname, q in QUESTIONS.items():
            for i in range(a.runs):
                r = dict(model=model, question=qname, run=i + 1, **measure(client, model, q))
                rows.append(r)
                print(r, flush=True)
                time.sleep(a.interval)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print("\n".join(summarize(rows)))
    print(f"\n-> {a.out}")


if __name__ == "__main__":
    main()
