import pytest
from unittest.mock import MagicMock, patch
from shared_memory.core import logic

@pytest.mark.asyncio
async def test_memory_saving_pipeline_integration():
    """
    Test the pipeline: normalize -> precompute -> save.
    Mocks are allowed here.
    """
    entities = ["IntegratedEntity"]
    observations = [{"content": "Integrated observation", "entity_name": "IntegratedEntity"}]
    
    # Mocking the AI components (allowed in integration tests)
    with patch("shared_memory.infra.embeddings.compute_embeddings_bulk") as mock_emb:
        mock_emb.return_value = [[0.1] * 768] * 2 # 1 entity + 1 observation (wait, observation check doesn't use embeddings directly in same way)
        # Actually save_memory_core:
        # 1.1 Preparing embedding inputs: entity_texts + bank_texts
        # Observations conflict check uses graph.check_conflict (LLM generation)
        
        with patch("shared_memory.core.graph.check_conflict") as mock_conflict:
            mock_conflict.return_value = [(False, "No conflict")]
            
            result = await logic.save_memory_core(
                entities=entities,
                observations=observations
            )
            
            assert "Saved 1 entities" in result
            assert "Saved 1 observations" in result
            assert "CONFLICTS DETECTED" not in result

@pytest.mark.asyncio
async def test_memory_saving_pipeline_with_conflict():
    """
    Test how the pipeline handles detected conflicts.
    """
    entities = ["ConflictEntity"]
    observations = [{"content": "Conflicting data", "entity_name": "ConflictEntity"}]
    
    with patch("shared_memory.infra.embeddings.compute_embeddings_bulk") as mock_emb:
        mock_emb.return_value = [[0.1] * 768]
        
        with patch("shared_memory.core.graph.check_conflict") as mock_conflict:
            # Simulate a conflict detected by AI
            mock_conflict.return_value = [(True, "Already exists in a different form")]
            
            result = await logic.save_memory_core(
                entities=entities,
                observations=observations
            )
            
            assert "Saved 1 entities" in result
            assert "Saved 0 observations" in result
            assert "CONFLICTS DETECTED" in result
            assert "Already exists in a different form" in result

@pytest.mark.asyncio
async def test_memory_saving_pipeline_partial_failure():
    """
    Test the pipeline when one part (e.g. embeddings) fails.
    """
    entities = ["FailEntity"]
    
    with patch("shared_memory.infra.embeddings.compute_embeddings_bulk") as mock_emb:
        mock_emb.side_effect = Exception("Embedding Service Unavailable")
        
        result = await logic.save_memory_core(entities=entities)
        
        assert "AI Error" in result
        assert "Embedding Service Unavailable" in result
