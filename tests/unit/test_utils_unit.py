import os

import pytest

from shared_memory.utils import (
    GlobalLock,
    PathResolver,
    mask_sensitive_data,
    sanitize_filename,
)


def test_path_resolver_data_dir():
    """Unit test for PathResolver. Ensures data dir is determined."""
    data_dir = PathResolver.get_base_data_dir()
    assert data_dir is not None
    assert os.path.isdir(data_dir)

def test_sanitize_filename_unit():
    """Unit test for sanitize_filename. Verifies path traversal protection."""
    assert sanitize_filename("test.md") == "test.md"
    assert sanitize_filename("../../etc/passwd") == "passwd.md"
    assert sanitize_filename("my file!.txt") == "my_file_.md"

def test_mask_sensitive_data_unit():
    """Unit test for data masking."""
    api_key = "AIzaSyA12345678901234567890123456789012"
    masked = mask_sensitive_data(f"My key is {api_key}")
    assert api_key not in masked
    assert "[GOOGLE_API_KEY_MASKED]" in masked

@pytest.mark.asyncio
async def test_global_lock_unit():
    """Unit test for GlobalLock (Intra-process)."""
    async with GlobalLock("unit_test_lock"):
        # Should be able to acquire
        pass
    # After exit, lock should be free
    lock = GlobalLock("unit_test_lock")
    async with lock:
        assert lock.file_locked is True
