"""第1回: 素のLLMに質問するスクリプト。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 質問を省略すると、講座に固有の質問をする
    uv run python -m app.ask --chat     # 会話履歴を保ったまま続けて質問する（宿題・実装）

ツールを持たない「素の」呼び出し。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse

from google import genai
from google.genai import errors, types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"

# 会話モードで送る履歴の上限（往復数）。古い発言から捨てて、入力トークンの増えすぎを防ぐ
MAX_TURNS = 10


def usage_line(response) -> str:
    """response.usage_metadata から入力・出力トークン数を1行にする（無いときは '-'）。"""
    u = getattr(response, "usage_metadata", None)
    n_in = getattr(u, "prompt_token_count", None) if u else None
    n_out = getattr(u, "candidates_token_count", None) if u else None
    return f"[tokens] 入力 {n_in if n_in is not None else '-'} / 出力 {n_out if n_out is not None else '-'}"


def ask(question: str, client=None) -> str:
    client = client or genai.Client(api_key=get_api_key())
    response = client.models.generate_content(model=MODEL, contents=question)
    print(usage_line(response))
    return response.text


class Conversation:
    """会話履歴を自分で持ち、毎回の generate_content に履歴ごと渡す。

    API は前の発言を覚えていない（ステートレス）ので、「覚えている」ように見せるには
    これまでの user / model の発言を毎回すべて送り直す必要がある。
    そのぶん入力トークンは往復ごとに増えるので、max_turns を超えた古い往復は捨てる。
    """

    def __init__(self, client=None, model: str = MODEL, max_turns: int = MAX_TURNS):
        self.client = client or genai.Client(api_key=get_api_key())
        self.model = model
        self.max_turns = max_turns
        self.history: list[types.Content] = []

    def send(self, text: str) -> str:
        contents = self.history + [types.Content(role="user", parts=[types.Part.from_text(text=text)])]
        response = self.client.models.generate_content(model=self.model, contents=contents)
        answer = response.text or ""
        # 成功したときだけ履歴に積む（失敗した質問を履歴に残すと、次の回答が崩れる）
        self.history = contents + [types.Content(role="model", parts=[types.Part.from_text(text=answer)])]
        self.history = self.history[-2 * self.max_turns:]
        self.last_usage = usage_line(response)
        return answer

    def reset(self) -> None:
        self.history = []


def chat_loop(conv: Conversation, read=input) -> None:
    """対話ループ。/reset で履歴を消し、/exit か空行で終了する。"""
    print("会話モード（/reset で履歴を消去、/exit または空行で終了）")
    while True:
        try:
            text = read("あなた> ").strip()
        except EOFError:
            break
        if text in ("", "/exit"):
            break
        if text == "/reset":
            conv.reset()
            print("（履歴を消去しました）")
            continue
        try:
            print(f"モデル> {conv.send(text)}")
            print(f"{conv.last_usage}  [履歴] {len(conv.history) // 2} 往復")
        except errors.APIError as e:
            print(api_error_message(e.code, e.message))


def main() -> None:
    parser = argparse.ArgumentParser(description="素のLLMに質問する")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--chat", action="store_true", help="会話履歴を保ったまま続けて質問する")
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    if args.chat:
        chat_loop(Conversation())
        return
    print(f"[質問] {args.question}\n")
    try:
        print(ask(args.question))
    except errors.APIError as e:
        print(api_error_message(e.code, e.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
