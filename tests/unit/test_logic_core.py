import pytest

from shared_memory import logic


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_minimal(fake_llm):
    """単体テスト: 最低限のエンティティ保存を検証 (No MagicMock)"""
    # init_db is handled by fixture setup_teardown_db in conftest.py

    entities = [
        {"name": "TestEntity", "entity_type": "concept", "description": "A unit test entity"}
    ]
    result = await logic.save_memory_core(entities=entities, agent_id="test_agent")

    assert "Saved" in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_read_memory_core_empty(fake_llm):
    """単体テスト: 空のDBでの読み取りを検証"""
    result = await logic.read_memory_core(query="Nothing")
    assert result["graph"]["entities"] == []
    assert result["graph"]["relations"] == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_invalid_input(fake_llm):
    """単体テスト: 不正な入力形式での動作を検証 (Adversarial)"""
    # entities がリストではない場合
    with pytest.raises((TypeError, AttributeError)):
        await logic.save_memory_core(entities="not a list")
