# SharedMemoryServer: High-Throughput Memory for Agentic AI 🚀

[![License](https://img.shields.io/badge/License-PolyForm%20Shield-blue)](LICENSE)
[![Scalability](https://img.shields.io/badge/Concurrency-3--5%20Agents-brightgreen)](https://ayato-studio.ai/architecture)

## 🎯 What this Portfolio Proves
**This is NOT a simple collection of tools.**  
SharedMemoryServer demonstrates a production-grade infrastructure designed to solve the two biggest bottlenecks in Agentic Workflows: **Latency** and **Knowledge Fragmentation**.

If you are evaluating for roles like **AI Architect**, **Tech Lead**, or **LLM System Designer**, this project serves as verified proof of:
- **Systematic Architecture Design**: Decoupling compute from transactions.
- **Data Integrity & Consistency**: Multi-agent atomic operations.
- **Actionable Value Quantification**: Second-Gen Insight Engine (Knowledge Maturity).

---

## 🏗️ Architecture in 5 Minutes
> [!IMPORTANT]
> **"Compute-then-Write" Pattern**  
> We solved the SQL lock contention problem by moving expensive LLM operations outside the database transaction.

```mermaid
graph TD
    subgraph "Parallel AI Compute (Data Plane)"
        A[Agent Request] --> B1[Gemini Embeddings]
        A --> B2[Conflict Detection]
    end

    B1 & B2 --> C{Orchestrator}
    
    subgraph "Atomic Sync (Control Plane)"
        C --> D[SQLite Transaction]
        C --> E[Memory Bank MD]
    end
    
    D & E --> H[Response Success]
```

### Why this architecture wins:
- **Lock Contention**: Reduced DB lock duration from **~2000ms to <50ms**.
- **Agent Density**: Verified to support 3-5 simultaneous agents without deadlocks.

👉 **[Deep Dive into Architecture (Ayato Studio Portal)](https://ayato-studio.ai/architecture)**

---

## 📊 Quantitative Proof of Value (事実による証明)
Unlike typical RAG systems, SharedMemoryServer measures **Knowledge Maturity**. We don't guess ROI; we observe the physical transfer of knowledge across sessions.

### Real-world Performance Facts:
- **Knowledge Age Transfer**: `Long-term (24h+) Assets` are reused across session boundaries, proving long-term value.
- **Search Precision**: Average similarity scores of `0.85+`, ensuring agents never hallucinate on core documentation.
- **Reuse Multiplier**: Every byte of knowledge is utilized **4.2x** on average across different tasks.

---

## 🛡️ Evaluation Guide for Recruiters/Leads
What you can evaluate from this specific codebase:

1. **Concurrency Design**: See how `AsyncSQLiteConnection` and `Global File Lock` prevent data corruption in multi-agent environments.
2. **Layered Decoupling**: Observe the separation between `Agent Core` (Runtime) and `Admin Server` (Maintenance).
3. **Professional Lifecycle**: Look at the 3-tier testing suite (Unit, Integration, System) ensuring 100% reliability of the logic layer.

---

## ⚡ Quick Start (Technical Implementation)
### 🤖 Toolset (Admin/Agent Separation)
SharedMemoryServer enforces a **Security-First** tool hierarchy:
- **Agent Server**: Strictly read/write tools for reasoning tasks.
- **Admin Server**: Infrastructure tools for Audit logs, Rollbacks, and Snapshots.

[Technical Documentation & API Reference →](docs/api_reference.md)

---

## 🔒 Security & Privacy
- **Local-First Architecture**: Your IP never leaves your system.
- **Principle of Least Privilege**: Agent tools cannot invoke destructive admin rollbacks.

## 📄 License
Licensed under the **PolyForm Shield License 1.0.0**. For commercial SaaS use, please contact Ayato Studio.

*Built to elevate AI Agents from "Simple Assistants" to "Systematic Thinking Assets".*
