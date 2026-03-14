# SharedMemoryServer (Hybrid Memory MCP)

This MCP server provides a unified memory layer for AI agents, combining structured knowledge and project-specific context.

## Features

### 1. Knowledge Graph Memory (SQLite)
Maintains entities, relations, and observations in a persistent SQLite database.
- `add_entity`: Define important concepts/tools.
- `add_relation`: Map dependencies and connections.
- `add_observation`: Record specific findings or state changes.
- `query_graph`: Retrieve the complete context for a specific entity.

### 2. Memory Bank (Markdown)
Manages project context using the "Memory Bank" pattern (popularized by Cline/Roo Code).
- `read_context`: Retrieve project brief, active context, etc.
- `save_context`: Persist updated context back to markdown files.

## Environment Variables
- `MEMORY_DB_PATH`: Path to the SQLite database (default: `shared_memory.db`).
- `MEMORY_BANK_DIR`: Directory for memory bank markdown files (default: `memory_bank`).

## Installation & Setup

1. **Install Dependencies**:
   ```bash
   uv pip install -e .
   ```

2. **Automatic Registration**:
   Register this MCP server with your AI agents (Claude Desktop, Cursor, etc.) automatically:
   ```bash
   shared-memory-register
   ```
   *(Use `--dry-run` to preview the changes without writing to config files.)*

## Design Philosophy
- **Simple is Best**: Focused tools with clear inputs/outputs.
- **GIGO Prevention**: Structured SQLite schema for knowledge, standardized Markdown for bank.

## Privacy & Security (Important)
- **Local Storage**: All memory data (SQLite and Markdown) is stored locally on your machine.
- **Data Protection**: Ensure your `.gitignore` includes `*.db` to prevent accidental commits of sensitive knowledge to public repositories.

## License
Licensed under the **PolyForm Shield License 1.0.0**.

> [!NOTE]
> **ライセンスの要約**:
> *   **許可**: 個人利用、社内利用、改変、配布は自由です。
> *   **制限**: このソフトウェアをそのまま、あるいは改変して**競合するSaaSサービス（有料・無料問わず）として公開・提供すること**は制限されています。
>
> 詳細は [LICENSE](LICENSE) ファイルをご確認ください。
