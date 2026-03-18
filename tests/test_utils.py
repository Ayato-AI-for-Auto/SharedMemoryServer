from shared_memory.utils import mask_sensitive_data


def test_mask_api_keys():
    text = "My key is AIzaSyA1234567890BCDEF1234567890BCDEF12 and secret is sk-1234567890abcdef1234"
    masked = mask_sensitive_data(text)
    assert "AIzaSyA" not in masked
    assert "sk-1234567890abcdef" not in masked
    assert "[GOOGLE_API_KEY_MASKED]" in masked
    assert "[API_KEY_MASKED]" in masked


def test_mask_password():
    text = "login with password=supersecret"
    masked = mask_sensitive_data(text)
    assert "supersecret" not in masked
    assert "[PASSWORD_MASKED]" in masked


def test_no_mask_normal_text():
    text = "This is a normal sentence about AI."
    assert mask_sensitive_data(text) == text
