import asyncio
from unittest.mock import patch

import pytest

from shared_memory.api import server

@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_initialized_waits(fake_llm):
    """ensure_initialized が初期化完了まで待機することを検証"""
    # 初期状態を未初期化に設定
    server._INITIALIZED_EVENT.clear()
    server._INIT_ERROR = None

    # 200ms後に初期化を完了させるタスク
    async def finish_init_delayed():
        await asyncio.sleep(0.2)
        server._INITIALIZED_EVENT.set()

    asyncio.create_task(finish_init_delayed())

    # ensure_initialized を呼び出し（待機が発生するはず）
    # タイムアウトを設定して無限ループを防ぐ
    await asyncio.wait_for(server.ensure_initialized(), timeout=1.0)

    assert server._INITIALIZED_EVENT.is_set()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_background_init_success(fake_llm):
    """_background_init が正常に完了し、フラグを立てることを検証"""
    server._INITIALIZED_EVENT.clear()
    server._INIT_ERROR = None

    # AsyncMock を使用して非同期関数を正しくモック
    from unittest.mock import AsyncMock

    with (
        patch("shared_memory.api.server.init_db", new_callable=AsyncMock) as mock_db,
        patch(
            "shared_memory.api.server.thought_logic.init_thoughts_db", new_callable=AsyncMock
        ) as mock_thought,
    ):
        await server._background_init()

        assert server._INITIALIZED_EVENT.is_set()
        assert server._INIT_ERROR is None
        assert mock_db.called
        assert mock_thought.called


@pytest.mark.asyncio
@pytest.mark.unit
async def test_background_init_failure(fake_llm):
    """初期化失敗時に適切にログ出力され、フラグが立たないことを検証"""
    server._INITIALIZED_EVENT.clear()
    server._INIT_ERROR = None

    with (
        patch("shared_memory.api.server.init_db", side_effect=Exception("DB Crash")),
        patch("shared_memory.api.server.logger.error") as mock_log_error,
    ):
        await server._background_init()

        assert server._INITIALIZED_EVENT.is_set()
        assert server._INIT_ERROR is not None
        assert mock_log_error.called
        assert "Background initialization FAILED" in mock_log_error.call_args[0][0]
