from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, format="{message}")

print("Testing logger.exception with f-string containing braces...")
try:
    e = "{'error': 500}"
    logger.exception(f"Error occurred: {e}")
    print("Success: No args")
except KeyError as ex:
    print(f"Failed: {ex}")

print("\nTesting logger.error with f-string containing braces and exc_info=True...")
try:
    e = "{'error': 500}"
    logger.error(f"Error occurred: {e}", exc_info=True)
    print("Success: With exc_info=True")
except KeyError as ex:
    print(f"Failed: {ex}")
