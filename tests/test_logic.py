import pytest
import math
from datetime import datetime, timedelta
from shared_memory.logic import calculate_importance, cosine_similarity

def test_calculate_importance_stability():
    now = datetime.now()
    past = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    score_low = calculate_importance(10, past, stability=0.1)
    score_high = calculate_importance(10, past, stability=10.0)
    assert score_high > score_low

def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    
    assert math.isclose(cosine_similarity(v1, v2), 1.0)
    assert math.isclose(cosine_similarity(v1, v3), 0.0)
