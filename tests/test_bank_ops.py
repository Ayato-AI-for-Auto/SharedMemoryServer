import unittest
import os
import shutil
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from shared_memory.server import initialize_bank, read_memory_bank, update_bank_file

class TestBankOps(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bank_dir = "test-memory-bank"
        os.environ["MEMORY_BANK_DIR"] = self.bank_dir
        await initialize_bank()

    async def asyncTearDown(self):
        if os.path.exists(self.bank_dir):
            shutil.rmtree(self.bank_dir)

    async def test_initialization(self):
        # Check if core files exist
        self.assertTrue(os.path.exists(os.path.join(self.bank_dir, "projectBrief.md")))
        self.assertTrue(os.path.exists(os.path.join(self.bank_dir, "activeContext.md")))

    async def test_read_write(self):
        await update_bank_file("activeContext.md", "# New Content")
        bank = await read_memory_bank()
        self.assertIn("# New Content", bank["activeContext.md"])

if __name__ == "__main__":
    unittest.main()
