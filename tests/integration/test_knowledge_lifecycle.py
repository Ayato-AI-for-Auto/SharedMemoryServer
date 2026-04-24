import json

import pytest

from shared_memory import logic


@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_knowledge_lifecycle(mock_llm):
    """
    結合テスト: 保存 -> 検索 -> 無効化 -> 再有効化のライフサイクル。
    MagicMockを使用して複雑なLLM応答をシミュレート。
    """
    # 1. 保存
    entities = [{"name": "LifecycleNode", "description": "Node for lifecycle testing"}]
    # mock_llm の応答をコンフリクトなしに設定
    mock_llm.models.set_response(
        "generate_content", json.dumps({"conflict": False, "reason": "OK"})
    )

    await logic.save_memory_core(entities=entities)

    # 2. 検索 (有効な状態)
    results = await logic.read_memory_core(query="LifecycleNode")
    assert any(e["name"] == "LifecycleNode" for e in results["graph"]["entities"])

    # 3. 無効化 (deactivate)
    await logic.manage_knowledge_activation_core(["LifecycleNode"], "inactive")

    # 4. 検索 (無効な状態ではヒットしない)
    results_inactive = await logic.read_memory_core(query="LifecycleNode")
    assert not any(e["name"] == "LifecycleNode" for e in results_inactive["graph"]["entities"])

    # 5. 無効化リストに含まれていることを確認
    inactive_list = await logic.list_inactive_knowledge_core()
    assert any(e["name"] == "LifecycleNode" for e in inactive_list["entities"])

    # 6. 再有効化 (reactivate)
    await logic.manage_knowledge_activation_core(["LifecycleNode"], "active")
    results_restored = await logic.read_memory_core(query="LifecycleNode")
    assert any(e["name"] == "LifecycleNode" for e in results_restored["graph"]["entities"])
