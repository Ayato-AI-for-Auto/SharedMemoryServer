# SharedMemoryServer (Hybrid Memory MCP)

This MCP server provides a unified memory layer for AI agents, combining structured knowledge and project-specific context.

## Unified Memory API (V2)

The server now features a consolidated 3-tool API for maximum simplicity and efficiency:

### 1. `save_memory`
**The Entrance for Writing**. Updates both Knowledge Graph (SQLite) and Memory Bank (Markdown) in one call.
- Handles entities, relations, observations, and file updates simultaneously.

### 2. `read_memory`
**The Entrance for Reading**. Unified search and retrieval across both Graph and Bank.
- Performs hybrid retrieval based on an optional keyword query and scope.

### 3. `delete_memory`
**The Entrance for Deletion**. Targeted removal of specific entities and their related context.

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
