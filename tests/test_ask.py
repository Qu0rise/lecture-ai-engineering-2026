"""第1回 ask.py のテスト（LLMもAPIキーも使わない）。

generate_content に渡された contents を記録する偽のクライアントで、
会話履歴が毎回送られていること・上限で古い往復が捨てられることを確かめる。
"""

from types import SimpleNamespace

from app import ask


class FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append(contents)
        n = len(self.calls)
        return SimpleNamespace(text=f"回答{n}", usage_metadata=SimpleNamespace(prompt_token_count=10 * n, candidates_token_count=5))


def fake_client():
    return SimpleNamespace(models=FakeModels())


def texts(contents):
    return [(c.role, c.parts[0].text) for c in contents]


def test_history_is_sent_every_turn():
    client = fake_client()
    conv = ask.Conversation(client=client, model="dummy")
    assert conv.send("私の名前はタロウです") == "回答1"
    conv.send("私の名前は？")
    second = client.models.calls[1]
    assert texts(second) == [("user", "私の名前はタロウです"), ("model", "回答1"), ("user", "私の名前は？")]


def test_history_is_trimmed_to_max_turns():
    client = fake_client()
    conv = ask.Conversation(client=client, model="dummy", max_turns=2)
    for i in range(4):
        conv.send(f"質問{i}")
    assert len(conv.history) == 4
    assert texts(conv.history)[0] == ("user", "質問2")


def test_reset_and_exit_commands():
    client = fake_client()
    conv = ask.Conversation(client=client, model="dummy")
    inputs = iter(["こんにちは", "/reset", "続き", "/exit"])
    ask.chat_loop(conv, read=lambda _: next(inputs))
    assert len(client.models.calls) == 2
    assert texts(client.models.calls[1]) == [("user", "続き")]


def test_usage_line_handles_missing_metadata():
    assert ask.usage_line(SimpleNamespace(usage_metadata=None)) == "[tokens] 入力 - / 出力 -"
    r = SimpleNamespace(usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=34))
    assert ask.usage_line(r) == "[tokens] 入力 12 / 出力 34"
