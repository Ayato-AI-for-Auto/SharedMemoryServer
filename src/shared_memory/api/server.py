import argparse
import asyncio
import logging
import os
import signal
import sys

from loguru import logger


# Intercept standard logging with Loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# Configure Loguru for premium look
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>",
    level="INFO",
)

# ruff: noqa: E402

# --- EXTREME GUARD: FD ISOLATION ---
_REAL_STDOUT_FD = os.dup(sys.stdout.fileno())
# Redirect OS-level FD 1 (stdout) to FD 2 (stderr)
# This ensures even C-level printf() calls go to stderr.
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())


class ProtectedStdout:
    """
    A wrapper for sys.stdout that protects the real MCP communication pipe.
    Everything written via sys.stdout.write (Python-level) goes to stderr.
    Only the .buffer attribute provides access to the real, isolated stdout FD.
    """

    def __init__(self, real_fd):
        import io

        # Create a clean, unbuffered binary stream for MCP
        self.buffer = io.FileIO(real_fd, mode="wb")

    def write(self, data):
        # Redirect all Python-level print() to stderr
        sys.stderr.write(data)

    def flush(self):
        sys.stderr.flush()
        try:
            self.buffer.flush()
        except Exception:
            pass

    def fileno(self):
        # IMPORTANT: Return the OS-level fileno of the underlying buffer
        # This is needed by libraries that expect a real file descriptor
        return self.buffer.fileno()

    def isatty(self):
        # Always return False for the guarded channel to avoid ANSI clutter
        # and compatibility issues with libraries like Uvicorn
        return False


# Replace sys.stdout with our guard
sys.stdout = ProtectedStdout(_REAL_STDOUT_FD)

logger.info("--- SERVER SCRIPT STARTING (Extreme Guard Mode) ---")
logger.info("OS-level stdout (FD 1) has been redirected to stderr (FD 2)")
logger.info("MCP communication will use an isolated FD.")

from typing import Any

from fastmcp import FastMCP

# Delayed imports to catch potential errors in submodules
logger.info("Importing core submodules (logic, thought_logic, database)...")
try:
    from shared_memory.core import logic, thought_logic
    from shared_memory.infra.database import close_all_connections, init_db

    logger.info("Core submodules imported successfully")
except Exception as e:
    logger.error(f"CRITICAL: Failed to import submodules: {e}", exc_info=True)
    # Re-raise to ensure the process fails visibly
    raise e

# Create MCP server instance
import threading
import time


_LAST_ACTIVITY_TIME = time.time()


def update_activity():
    """Updates the last activity timestamp to prevent auto-shutdown."""
    global _LAST_ACTIVITY_TIME
    _LAST_ACTIVITY_TIME = time.time()


def _inactivity_thread(timeout_seconds: int):
    """Thread that monitors inactivity and shuts down the server if exceeded."""
    if timeout_seconds <= 0:
        logger.info("Inactivity monitor disabled.")
        return

    logger.info(
        f"Inactivity monitor started. Timeout: {timeout_seconds}s ({timeout_seconds / 60:.1f}m)"
    )
    while True:
        time.sleep(min(30, timeout_seconds // 2 if timeout_seconds > 0 else 30))
        elapsed = time.time() - _LAST_ACTIVITY_TIME
        if elapsed > timeout_seconds:
            logger.warning(
                f"INACTIVITY LIMIT REACHED: Server idle for {elapsed:.0f}s. "
                "Triggering graceful shutdown..."
            )
            # Send SIGTERM to ourselves to trigger graceful shutdown in main()
            # This works on both Windows and Linux to trigger our signal handlers.
            os.kill(os.getpid(), signal.SIGTERM)
            break


# Global initialization state
_INITIALIZED_EVENT: asyncio.Event | None = None
_INIT_ERROR = None
_INIT_STARTED = False


def trigger_init():
    """Starts the background initialization task if not already started."""
    global _INIT_STARTED
    if _INIT_STARTED:
        return
    _INIT_STARTED = True
    from shared_memory.common.tasks import create_background_task

    create_background_task(_background_init(), name="startup_init")


async def _background_init():
    """Heavy lifting initialization with detailed logging and step-specific error handling."""
    global _INIT_ERROR, _INIT_STARTED, _INITIALIZED_EVENT
    if _INITIALIZED_EVENT is None:
        _INITIALIZED_EVENT = asyncio.Event()

    if _INITIALIZED_EVENT.is_set():
        return

    _INIT_STARTED = True
    logger.info("================================================================")
    logger.info("   [SYSTEM INITIALIZATION] Starting background setup...")
    logger.info("================================================================")

    try:
        # Step 1: Knowledge Database
        logger.info("STEP 1/2: Initializing Knowledge Database (SQLite)...")
        try:
            await init_db()
            logger.info("STEP 1/2: [SUCCESS] Knowledge DB is ready.")
        except Exception as e:
            logger.error(f"STEP 1/2: [FAILED] Could not init Knowledge DB: {e}")
            raise

        # Step 2: Thoughts Database
        logger.info("STEP 2/2: Initializing Thoughts Database (SQLite)...")
        try:
            await thought_logic.init_thoughts_db()
            logger.info("STEP 2/2: [SUCCESS] Thoughts DB is ready.")
        except Exception as e:
            logger.error(f"STEP 2/2: [FAILED] Could not init Thoughts DB: {e}")
            raise

        logger.info("================================================================")
        logger.info("   [SYSTEM READY] All initialization steps completed.")
        logger.info("================================================================")
    except Exception as e:
        _INIT_ERROR = e
        logger.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logger.error(f"   [FATAL ERROR] Initialization failed: {e}")
        logger.error("   The server will continue to run but tools may fail.")
        logger.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    finally:
        _INITIALIZED_EVENT.set()


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(server):
    """
    Handles server startup and shutdown.
    Ensures handshake is fast by moving DB init to background.
    """
    logger.info("Server lifespan STARTING. Triggering background initialization...")

    # Initialize the event in the current loop
    global _INITIALIZED_EVENT
    if _INITIALIZED_EVENT is None:
        _INITIALIZED_EVENT = asyncio.Event()

    # Start init in background if not already started
    trigger_init()

    yield

    # CLEANUP: Close persistent singleton connections on shutdown
    logger.info("Server lifespan SHUTTING DOWN. Closing all database connections...")

    await wait_for_background_tasks(timeout=5.0)
    try:
        from shared_memory.infra.database import close_all_connections
        await close_all_connections()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Create MCP server instance
mcp = FastMCP("SharedMemoryServer", lifespan=lifespan)


def trigger_inactivity_watcher(timeout: int):
    """
    Starts the inactivity monitor thread.
    """
    if timeout <= 0:
        return

    monitor_thread = threading.Thread(
        target=_inactivity_thread, args=(timeout,), name="InactivityMonitor", daemon=True
    )
    monitor_thread.start()


_INIT_LOCK = asyncio.Lock()

async def ensure_initialized():
    """Ensures the server is fully ready before tool execution."""
    update_activity()
    global _INITIALIZED_EVENT
    if _INITIALIZED_EVENT is None:
        _INITIALIZED_EVENT = asyncio.Event()

    if not _INITIALIZED_EVENT.is_set():
        async with _INIT_LOCK:
            if not _INITIALIZED_EVENT.is_set():
                logger.info("Tool called but initialization is still in progress. Waiting...")
                if not _INIT_STARTED:
                    logger.warning("Startup initialization was NOT triggered. Running fallback...")
                    trigger_init()
                    await _INITIALIZED_EVENT.wait()
                else:
                    # Wait for the background task to finish
                    await _INITIALIZED_EVENT.wait()
                    logger.info("Initialization complete. Resuming tool execution.")

    if _INIT_ERROR:
        from shared_memory.common.exceptions import DatabaseError

        raise DatabaseError(f"Server failed to initialize: {_INIT_ERROR}")


async def wait_for_background_tasks(timeout: float = 5.0):
    """Wait for all currently tracked background tasks to complete."""
    from shared_memory.common.tasks import wait_for_background_tasks as _wait

    await _wait(timeout=timeout)



# ==========================================
# CORE AGENT TOOLS (Standard Interface)
# ==========================================


async def _run_save_memory_background(entities, relations, observations, bank_files, agent_id):
    """Internal helper to run save_memory_core in background and log results/errors."""
    try:
        result = await logic.save_memory_core(
            entities, relations, observations, bank_files, agent_id
        )
        logger.info(f"Background save_memory COMPLETE for agent {agent_id}: {result}")
    except Exception as e:
        logger.error(f"Background save_memory FAILED for agent {agent_id}: {e}", exc_info=True)


from typing import Any, Optional


@mcp.tool()
async def save_memory(
    entities: Optional[list[dict]] = None,
    relations: Optional[list[dict]] = None,
    observations: Optional[list[dict]] = None,
    bank_files: Optional[dict[str, str]] = None,
    agent_id: str = "default_agent",
) -> str:
    """
    Saves multiple pieces of knowledge in one transaction (Asynchronous).
    Returns immediately while processing happens in the background.

    - entities: List of entities with 'name' (required), 'entity_type', 'description'.
    - relations: Knowledge Graph Triples. Each dict MUST have:
        'subject' (source), 'object' (target), 'predicate' (type).
    - observations: List of factual statements linked to an entity.
        Format: {"entity_name": "Name", "content": "Fact"}
    - bank_files: Markdown documentation mapping filename to content.
    """
    # Defensive normalization: Ensure we have objects to work with
    entities = entities or []
    relations = relations or []
    observations = observations or []
    bank_files = bank_files or {}

    await ensure_initialized()

    # Fire and forget
    from shared_memory.common.tasks import create_background_task

    create_background_task(
        _run_save_memory_background(entities, relations, observations, bank_files, agent_id),
        name=f"save_memory_{agent_id}",
    )

    count_info = []
    if entities:
        count_info.append(f"{len(entities)} entities")
    if relations:
        count_info.append(f"{len(relations)} relations")
    if observations:
        count_info.append(f"{len(observations)} observations")
    if bank_files:
        count_info.append(f"{len(bank_files)} files")

    msg = (
        f"Saved (initiated in background) for: "
        f"{', '.join(count_info) if count_info else 'nothing'}."
    )
    logger.info(msg)
    return msg


@mcp.tool()
async def read_memory(query: str = ""):
    """
    Retrieves knowledge from the graph and memory bank.
    Uses hybrid search (Semantic + Keyword) if a query is provided.
    """
    await ensure_initialized()
    return await logic.read_memory_core(query)


@mcp.tool()
async def get_graph_data(query: str = "") -> dict[str, Any] | str:
    """
    Retrieves knowledge from the graph database.
    Optionally filters graph data based on a query.
    """
    await ensure_initialized()
    try:
        return await logic.graph.get_graph_data(query)
    except Exception as e:
        return f"Database Error: Failed to retrieve graph data. {e}"


@mcp.tool()
async def synthesize_entity(entity_name: str):
    """Aggregates all known info about an entity into a master summary."""
    await ensure_initialized()
    return await logic.synthesize_entity(entity_name)


@mcp.tool()
async def manage_knowledge_activation(ids: Any, status: str):
    """
    Manages the activation state of knowledge items (entities, bank files, etc.).
    - ids: List of IDs or a single ID string.
    - status: 'active' (default/searchable), 'inactive' (hidden), or 'archived' (legacy).
    Use this to toggle knowledge OFF/ON without destructive deletion.
    """
    # Normalize: allow single ID as string
    if isinstance(ids, str):
        ids = [ids]

    await ensure_initialized()
    return await logic.manage_knowledge_activation_core(ids, status)


@mcp.tool()
async def list_inactive_knowledge():
    """
    Lists all knowledge assets that are currently inactive or archived.
    Useful for reviewing what information has been sidelined or for potential reactivation.
    """
    await ensure_initialized()
    return await logic.list_inactive_knowledge_core()


# ==========================================
# THOUGHT & REASONING TOOLS
# ==========================================


@mcp.tool()
async def sequential_thinking(
    thought: str,
    thought_number: Any,
    total_thoughts: Any,
    next_thought_needed: Any,
    is_revision: bool = False,
    revises_thought: Any = 0,
    branch_from_thought: Any = 0,
    branch_id: str = "",
    session_id: str = "default_session",
):
    """
    A detailed tool for dynamic and reflective problem-solving through thoughts.
    Each thought can build on, question, or revise previous insights as
    understanding deepens.
    Automatically surfaces related past memories and thoughts to enrich the
    reasoning process.

    COMMIT ADVISORY: After completing a significant reasoning milestone or
    making fundamental design decisions, you should promptly COMMIT your
    code changes to ensure traceability. Summarize your reasoning in the
    commit message.
    """
    # Defensive normalization: Convert strings to ints/bools if AI sends them wrong
    try:
        thought_number = int(thought_number)
        total_thoughts = int(total_thoughts)
        revises_thought = int(revises_thought) if revises_thought else 0
        branch_from_thought = int(branch_from_thought) if branch_from_thought else 0

        if isinstance(next_thought_needed, str):
            next_thought_needed = next_thought_needed.lower() == "true"
    except (ValueError, TypeError) as e:
        logger.warning(f"Lenient parsing corrected a type mismatch in thinking args: {e}")

    await ensure_initialized()
    return await thought_logic.process_thought_core(
        thought,
        thought_number,
        total_thoughts,
        next_thought_needed,
        is_revision,
        revises_thought,
        branch_from_thought,
        branch_id,
        session_id,
    )


@mcp.tool()
async def get_insights(format: str = "markdown"):
    """
    SharedMemoryServerの導入効果（価値）を定量化したレポートを取得します。
    - format: 'markdown' (人間向けレポート) または 'json' (プログラム用データ)
    ビジネス上のROIやトークン削減量、知識の再利用率を確認するために使用します。
    """
    await ensure_initialized()
    from shared_memory.ops.insights import InsightEngine

    metrics = await InsightEngine.get_summary_metrics()
    if format == "json":
        return metrics
    return InsightEngine.generate_report_markdown(metrics)


@mcp.tool()
async def check_integrity():
    """
    Performs a comprehensive integrity check of the LogicHive system,
    including DB status, Vector store synchronization, and Environment pools.
    """
    await ensure_initialized()
    from shared_memory.ops.health import get_comprehensive_diagnostics

    return await get_comprehensive_diagnostics()


@mcp.tool()
async def ping() -> str:
    return "pong"


def main():
    """Entry point for the MCP server with enhanced stability and SSE support."""
    parser = argparse.ArgumentParser(description="SharedMemoryServer MCP")
    parser.add_argument("--sse", action="store_true", help="Run with SSE transport")
    parser.add_argument("--port", type=int, default=8377, help="Port for SSE server")
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help=(
            "Auto-shutdown after N seconds of inactivity (default: 1800s / 30m). "
            "Set to 0 to disable."
        ),
    )
    args = parser.parse_args()
    # Determine transport
    use_sse = args.sse or os.environ.get("MCP_TRANSPORT") == "sse"

    # Attach timeout to mcp instance for reference
    mcp._inactivity_timeout = args.timeout

    # Start the inactivity watchers
    trigger_inactivity_watcher(args.timeout)

    if not use_sse:
        logger.info("SharedMemoryServer: Starting in STDIO mode (Using Protected Channel)")
        # Note: sys.stdout is already our ProtectedStdout wrapper.
        # FastMCP will automatically use sys.stdout.buffer for UTF-8 wrapping.
    else:
        logger.info(f"SharedMemoryServer: Starting in SSE mode on port {args.port}")

    # Enable internal logging for debugging startup issues via standard logging
    # (These will be intercepted by our Loguru InterceptHandler)
    logging.getLogger("mcp").setLevel(logging.INFO)
    logging.getLogger("fastmcp").setLevel(logging.INFO)
    logger.info("Internal loggers (mcp, fastmcp) configured to INFO level")

    # Handle signals for graceful shutdown (especially on Windows)
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        # Since we are in a sync handler, we can't easily await close_all_connections
        # But we can try to schedule it or just exit if mcp.run handles it.
        # FastMCP usually handles signals, but we want to be explicit.
        sys.exit(0)

    if sys.platform == "win32":
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGBREAK, signal_handler)
    else:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    try:
        if use_sse:
            logger.info(f"Launching SharedMemoryServer in SSE mode on port {args.port}...")
            mcp.run(transport="sse", port=args.port)
        else:
            logger.info("Launching FastMCP in STDIO mode...")
            mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"CRITICAL: Server crashed: {e}", exc_info=True)
        # Flush logs before exit
        for h in logging.root.handlers:
            h.flush()
        raise e


if __name__ == "__main__":
    main()
