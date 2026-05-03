from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, format="{message}")

print("Testing logger.opt(exception=True).error(f-string)...")
try:
    e = "{'error': 500}"
    logger.opt(exception=True).error(f"Error: {e}")
    print("Success")
except KeyError as ex:
    print(f"Failed: {ex}")
