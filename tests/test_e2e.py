import pytest
from shared_memory.server import (
    save_memory,
    read_memory,
    get_audit_history,
    synthesize_entity,
    create_snapshot,
    repair_memory,
)
from shared_memory.database import init_db


@pytest.fixture(autouse=True)
def setup_db(mock_gemini):
    init_db()


@pytest.mark.asyncio
async def test_full_save_read_flow(mock_gemini):
    # 1. Save Memory (Complex)
    res = await save_memory(
        entities=[
            {"name": "Project Omega", "description": "Top secret"},
            {"name": "CEO", "description": "The boss"},
        ],
        relations=[
            {"source": "Project Omega", "target": "CEO", "relation_type": "managed_by"}
        ],
        observations=[{"entity_name": "Project Omega", "content": "Started in 2024"}],
        bank_files={"omega_manual.md": "# Omega Manual"},
    )
    print(f"DEBUG: res='{res}'")
    assert "Saved 2 entities" in res
    assert "Saved 1 relations" in res
    assert "Saved 1 observations" in res
    assert "Updated 1 bank files" in res

    # 2. Read Memory (Keyword)
    data = await read_memory(query="Omega")
    assert any(e["name"] == "Project Omega" for e in data["graph"]["entities"])
    assert "omega_manual.md" in data["bank"]

    # 3. Audit History
    history = await get_audit_history(limit=5)
    assert len(history) >= 4  # Entity, Relation, Obs, BankFile

    # 4. Synthesis
    synth = await synthesize_entity("Project Omega")
    assert "conflict" in synth or "Project Omega" in synth

    # 5. Snapshot
    snap_res = await create_snapshot("Final State")
    assert "Snapshot 'Final State' created" in snap_res

    # 6. Repair
    repair_res = await repair_memory()
    assert "Restored" in repair_res
