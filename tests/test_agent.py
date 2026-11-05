"""エージェントの配線テスト。

TestModel は実際のLLMを呼ばない偽モデルで、登録されたツールを全部呼んでから
ダミーの回答を返す。APIキーも利用枠も使わずに、
「ツールが登録され、呼ばれ、結果がモデルに戻るか」を確かめられる。
"""

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app.agent import agent

BASE_TOOLS = {"search_glossary", "get_lecture_summary"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


def test_base_tools_are_registered_and_called():
    model = TestModel()
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered  # 演習でツールを足しても壊れないよう「含む」で判定

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    # 承認が必要なツール（requires_approval=True）は、実行されずに承認待ちになるので戻り値が無い
    waiting = len(result.output.approvals) if isinstance(result.output, DeferredToolRequests) else 0
    assert len(_parts(result, ToolReturnPart)) + waiting == len(_parts(result, ToolCallPart))
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


# ---- 第3回 宿題（実装）: 承認付きツール ----

from pydantic_ai.messages import ModelResponse

from app import tools
from app.agent import run_with_approval


def _run_with(decision: bool, tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LOG_DIR", tmp_path)
    model = TestModel(call_tools=["save_learning_log"], custom_output_text="記録しました")
    decisions = []

    def approve(call):
        decisions.append((call.tool_name, call.args_as_dict()))
        return decision

    with agent.override(model=model):
        result = run_with_approval(agent, "今日の学びを記録して", model, approve=approve)
    return result, decisions, list(tmp_path.glob("*.md"))


def test_save_is_paused_until_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LOG_DIR", tmp_path)
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        result = agent.run_sync("今日の学びを記録して")
    # 承認を聞く前は、ツールは呼ばれていても実行されていない（ファイルが無い）
    assert isinstance(result.output, DeferredToolRequests)
    assert [c.tool_name for c in result.output.approvals] == ["save_learning_log"]
    assert not list(tmp_path.glob("*.md"))
    assert not _parts(result, ToolReturnPart)


def test_approved_save_writes_file_and_resumes(tmp_path, monkeypatch):
    result, decisions, files = _run_with(True, tmp_path, monkeypatch)
    assert decisions and decisions[0][0] == "save_learning_log"
    assert len(files) == 1
    returns = _parts(result, ToolReturnPart)
    assert returns[-1].tool_name == "save_learning_log" and "保存しました" in str(returns[-1].content)
    assert isinstance(result.output, str)
    # 承認で run が2回になるので、モデルの応答も2回以上
    assert len([m for m in result.all_messages() if isinstance(m, ModelResponse)]) >= 2


def test_denied_save_writes_nothing(tmp_path, monkeypatch):
    result, _, files = _run_with(False, tmp_path, monkeypatch)
    assert files == []
    returns = _parts(result, ToolReturnPart)
    assert returns[-1].tool_name == "save_learning_log"
    assert isinstance(result.output, str)
