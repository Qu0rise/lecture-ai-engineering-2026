# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：同じ質問「AIE2026 の講座の宿題にある「3レベル」とは何ですか？」で比べた
  - `app.ask`（第1回）：「おそらく AI Engineer 2026 … の宿題における 3 レベル」と前置きしたうえで，難易度（Basic / Intermediate / Advanced），AI の活用度（AI 依存／協働／駆動），完了基準（Must / Better / 発展）の 3 通りの分類を一般論として並べた．講座のことは知らないのに，それらしい答えを長く書く
  - `app.agent`（第3回）：先に `search_glossary` を呼び，用語集の `homework-levels` のとおり「基礎・実装・発展の 3 段階で，どれか 1 つに取り組めば完了」と答え，最後に「関連する回：第1回」を付けた．`data/glossary.json` の定義と一致している．用語集にある範囲では，検索させるほうが短くて正しい
- `--trace` で見えたツール呼び出し（ツール名と引数）：
  - 「3レベル」の質問：`search_glossary({'query': '3レベル'})` が 1 回
  - 「LoRA と QLoRA の違いは？」：`search_glossary({'query': 'LoRA'})` と `search_glossary({'query': 'QLoRA'})` の 2 回．docstring の「query には調べたい用語を 1 つだけ入れる」のとおり，用語ごとに分けて検索した
  - 「第2回の内容から確認問題を1問出して」：`make_quiz({'lecture': 2})` が 1 回．返り値は `{"question": "「ランク（LoRAの r）」の意味は？", "answer": "…"}` で，回答は問題だけを出し，答えは「ぜひあなたの言葉で考えて…採点や解説をします」と伏せた（INSTRUCTIONS に足した「答えはすぐに見せない」が効いている）
- 1つの質問での LLM 呼び出し回数（`requests`）：どの質問も `requests=2`（ツール呼び出しを書く 1 回目と，結果を読んで答える 2 回目）．LoRA/QLoRA は `tool_calls=2` でも `requests=2` で，2 つの検索を 1 回の応答にまとめて依頼していた（講義で言うバッチコール）．入力トークンは 1,396〜1,874（ツールの説明と用語集の結果が毎回入る），費用は 1 問 0.0006〜0.0010 ドル（gemini-3.5-flash-lite）
- 追加したツールと、docstring に書いた説明：`make_quiz(lecture: int) -> str`．「指定した回（1始まりの整数）の用語から1つを選び、確認問題と答えを返す。『第2回の確認問題を出して』『復習用に1問出して』のように、ある回の復習問題を求められたときに使う。問題と答えが JSON で返るので、それをもとに出題し、答えは利用者が考えたあとに示す。」用語が無い回（0 や 99）は，出題できる回の一覧を文字列で返してエラーにしない．`--list-tools` で 4 つ目として表示され，`pytest -q` は 23 件すべて通った（6.3 秒）

## 宿題

- 取り組んだレベル：実装
- やったこと：
  - `app/tools.py` に `save_learning_log(title, content)` を追加．`learning_log/` に `YYYYMMDD_HHMMSS_<title>.md` を書き，保存したパスと文字数を返す．title はファイル名に使えない文字と `..` を落とし（`../../etc/passwd` → `etc_passwd`），content が空なら書かずに理由を返す．保存先 `LOG_DIR` はモジュール変数にして，テストでは一時フォルダに差し替える
  - `app/agent.py` で `agent.tool_plain(tools.save_learning_log, requires_approval=True)` と登録し，`Agent(..., output_type=[str, DeferredToolRequests])` にした．CLI 側に `run_with_approval()` を足した：1 回目の `run_sync` の `output` が `DeferredToolRequests` なら，`approvals` の各 `ToolCallPart` の `tool_name` と `args_as_dict()` を表示して `[y/N]` を聞き，`DeferredToolResults().approvals[tool_call_id]` に True/False を入れて，`message_history=result.all_messages()` と `deferred_tool_results=` を付けてもう一度 `run_sync` する．承認待ちが無くなるまで while で回す
  - INSTRUCTIONS に「学びの記録を残すよう頼まれたら save_learning_log を使う．頼まれていないのに保存しない」を足した
  - テスト（`tests/test_agent.py`，`TestModel(call_tools=["save_learning_log"])`）：①承認前は `output` が `DeferredToolRequests` で，`ToolReturnPart` が無く，ファイルも無い ②承認すると `保存しました` の `ToolReturnPart` が入り，ファイルが 1 つでき，モデルの応答が 2 回になる ③却下するとファイルは 0 件のまま文字列の回答で終わる．`tests/test_tools.py` に `make_quiz` と `save_learning_log` の単体テストを 4 件
- 結果（gemini-3.5-flash-lite，`--trace` 付き）：
  - 「今日の学びを記録して。要点は…」→ 実行が止まり，`[承認待ち] save_learning_log を実行しようとしています。引数: title: エージェントの基本構成とツールの重要性 / content: …` と出て `実行してよいですか？ [y/N]` になった．この時点で `learning_log/` にファイルは無い
  - `y` → ツールが実行され `learning_log/20261105_071243_エージェントの基本構成とツールの重要性.md`（123 文字）ができ，`[tool return] save_learning_log -> 保存しました: …` のあと「学びの内容を `learning_log/` に保存しました」と答えた．再開後の `[usage]` は `requests=1, tool_calls=1`（入力 823 トークン）で，これは 2 回目の run だけの数．1 回目の run（ツール呼び出しを書いた分）を足すと 1 問で LLM は 2 回
  - 「このメモを保存して：テスト用のメモ」→ `n` → `[tool return] save_learning_log -> The tool call was denied.` となり，「メモの保存が拒否されたため、保存を中止しました」と答えた．ファイルは増えていない（2 件のまま）
  - 想定外だった動き：最初の承認では `y` のあとに `モデルが混み合っています（503）` で止まった．ツール自体は承認直後に実行されていて `learning_log/20261105_071159_….md` はできていたのに，最終回答は返らなかった．同じ依頼をやり直すと 2 つ目のファイルができた
- 気づき・疑問：
  - 承認は「モデルがツールを呼ぶ前」ではなく「ハーネスが実行する前」に入る．モデルは普通に `save_learning_log(...)` を書き終えており，Pydantic AI はそれを実行せずに run を終えて `DeferredToolRequests` を返す．承認してから続きを走らせるとき，会話（`all_messages()`）をそのまま渡すので，モデルは「自分が呼んだツールの結果が返ってきた」ように見える．承認の有無はモデルには見えない
  - 503 の件は，講義の「冪等性がないツール」そのものだった．書き込み（ツール）は成功し，その後の LLM 呼び出しだけが失敗したので，利用者からは「失敗した」ように見えて，やり直すと二重に保存される．対策は，同じ依頼を同じファイル名に書く（title と内容のハッシュで名前を決める）か，再開時にその run で実行済みのツール結果を記録から返すこと．今回は保存先が自分のフォルダなので実害は無いが，メール送信や注文なら 2 回目は起きてはいけない
  - `requires_approval=True` にすると，承認のたびに LLM をもう 1 回呼ぶ．この演習では 1 問 2 回 → 3 回（うち 1 回は承認待ちで中断）になり，入力トークンもその分増える．止めやすさと費用のトレードオフで，講義の「毎回聞く（default）」「ルールで決める（allow / ask / deny）」のうち，取り消しにくい書き込みだけ `ask` にするのが現実的だと思った
  - テストでは `TestModel` が「ツールを呼ぶ」ふるまいを固定してくれるので，承認・却下の分岐を API なしで確かめられた．ただし，モデルが「頼まれていないのに保存する」かどうかはテストできない．これは INSTRUCTIONS と docstring の書き方で決まるので，`--trace` で実際の呼ばれ方を見るしかない
  - 疑問：却下したときモデルに渡る文は既定の `The tool call was denied.` で，理由が無い．`ToolDenied(message=...)` で「利用者が内容を確認してから保存したい」などを渡せば，モデルは次に何をすべきか判断しやすくなるはずで，CLI で却下理由を入力させる拡張を考えている
