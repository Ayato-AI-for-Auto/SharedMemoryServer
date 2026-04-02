import sqlite3

import pytest

from shared_memory import database, search, thought_logic


@pytest.fixture
def test_db_setup(tmp_path):
    """
    実データ（に近い構造）を使用したテスト用DBのセットアップ。
    """
    db_path = str(tmp_path / "test_knowledge.db")
    thoughts_db_path = str(tmp_path / "test_thoughts.db")

    # 環境変数のモック
    with pytest.MonkeyPatch().context() as m:
        m.setenv("MEMORY_DB_PATH", db_path)
        m.setenv("THOUGHTS_DB_PATH", thoughts_db_path)

        # 初期化
        database.init_db()
        thought_logic.init_thoughts_db()

        # データの注入
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO entities (name, entity_type, description) VALUES ('Rust', 'Language', 'A systems programming language focusing on safety.')"
        )
        conn.execute(
            "INSERT INTO observations (entity_name, content) VALUES ('Rust', 'Rust prevents data races at compile time.')"
        )
        conn.execute(
            "INSERT INTO bank_files (filename, content) VALUES ('rust_guide.md', 'Rust uses Cargo for package management.')"
        )
        conn.commit()
        conn.close()

        t_conn = sqlite3.connect(thoughts_db_path)
        t_conn.execute(
            "INSERT INTO thought_history (session_id, thought_number, total_thoughts, thought, next_thought_needed) VALUES ('sess_old', 1, 1, 'I think Rust is great for CLI tools.', 0)"
        )
        t_conn.commit()
        t_conn.close()

        yield {"db_path": db_path, "thoughts_db_path": thoughts_db_path}


@pytest.mark.asyncio
async def test_perform_keyword_search_unit(test_db_setup):
    """
    [単体テスト] search.perform_keyword_search の挙動確認。
    """
    # Rustに関する検索
    results = await search.perform_keyword_search("Rust")

    # スコアの高い順に並んでいるか
    assert len(results) > 0
    # スコアが同じ場合、observationsが先に来る可能性があるためIDを重視
    top_ids = [r["id"] for r in results if r["score"] == results[0]["score"]]
    assert "Rust" in top_ids

    # 思考履歴からもヒットするか
    thought_hits = [r for r in results if r["source"] == "thought_history"]
    assert len(thought_hits) > 0
    assert "sess_old" in thought_hits[0]["id"]


@pytest.mark.asyncio
async def test_sequential_thinking_integration(test_db_setup):
    """
    [結合テスト] sequential_thinking (thought_logic) に知見が注入されているか。
    """
    result = await thought_logic.process_thought_core(
        thought="I want to build a tool in Rust.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="sess_new",
    )

    assert "related_knowledge" in result
    knowledge = result["related_knowledge"]

    # 関連知識が含まれているか
    ids = [item["id"] for item in knowledge]
    assert "Rust" in ids

    # 現在のセッション(sess_new)が除外されているか確認
    # (sess_new の情報はまだ1件目なので、他のセッション sess_old のみがヒットするはず)
    for item in knowledge:
        if item["source"] == "thought_history":
            assert "sess_new" not in item["id"]
            assert "sess_old" in item["id"]


@pytest.mark.asyncio
async def test_no_match_scenario(test_db_setup):
    """
    一致するものがない場合でも正常に空リストが返るか。
    """
    results = await search.perform_keyword_search("NonExistentTerm")
    assert results == []
