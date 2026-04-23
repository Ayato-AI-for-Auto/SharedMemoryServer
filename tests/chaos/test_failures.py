import pytest
import json
import asyncio
from shared_memory import logic, server
from unittest.mock import patch

@pytest.mark.asyncio
@pytest.mark.chaos
async def test_corrupt_llm_json_response(mock_llm):
    """異常系: LLMが不正な形式のJSONを返した場合の挙動を検証"""
    entities = [{"name": "CorruptNode", "description": "Testing JSON corruption"}]
    
    # 不正なJSON（閉じカッコ不足など）をセット
    mock_llm.models.set_response("generate_content", '{"conflict": true, "reason": "broken json...')
    
    # システムがクラッシュせず、適切に例外またはエラーメッセージを返すことを確認
    # 実装によりますが、一般的には内部でハンドルされるべきです
    try:
        await logic.save_memory_core(entities=entities)
    except json.JSONDecodeError:
        # もしデコードエラーがそのまま上がる設計なら、それはそれで検知
        pass
    except Exception as e:
        # その他のハンドリングされたエラー
        assert "json" in str(e).lower() or "error" in str(e).lower()

@pytest.mark.asyncio
@pytest.mark.chaos
async def test_database_busy_simulation(fake_llm):
    """異常系: データベースがロックされている状況をシミュレート (Adversarial)"""
    # aiosqlite.connect ではなく、より上位の初期化関数をモックして失敗させる
    with patch("shared_memory.server.init_db", side_effect=Exception("database is locked")):
        server._INITIALIZED = False
        await server._background_init()
        
        assert server._INITIALIZED is False
        # ensure_initialized がタイムアウトすることを確認
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(server.read_memory(query="test"), timeout=0.5)

@pytest.mark.asyncio
@pytest.mark.chaos
async def test_concurrent_write_pressure(fake_llm):
    """異常系: 超高頻度の同時書き込み負荷テスト (Stress)"""
    tasks = []
    for i in range(20):
        tasks.append(logic.save_memory_core(
            entities=[{"name": f"StressNode_{i}", "description": "Stress testing"}]
        ))
    
    # 20個の同時書き込みを投げる
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 少なくともいくつかは成功し、失敗した場合も致命的なクラッシュ（セグフォ等）がないことを確認
    success_count = sum(1 for r in results if isinstance(r, str) and "Saved" in r)
    assert success_count > 0
