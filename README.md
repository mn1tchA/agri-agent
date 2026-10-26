# 🌾 Agri-Agent Swarm v2.2

![Status](https://img.shields.io/badge/Status-Production%20Ready-success) ![Python](https://img.shields.io/badge/Python-3.11+-blue) ![React](https://img.shields.io/badge/React-19-cyan) ![LangGraph](https://img.shields.io/badge/AI-LangGraph%20Swarm-purple) ![MCP](https://img.shields.io/badge/Protocol-MCP-orange) ![Version](https://img.shields.io/badge/Version-2.2-orange)

**Agri-Agent Swarm** is an enterprise-grade, Multi-Agent Autonomous Agricultural system built to democratize precision agriculture in water-stressed regions. It deploys a **LangGraph Swarm** of specialized AI agents — meteorologist, botanist, financial director — orchestrated with **parallel execution**, **critical anomaly detection**, **Vector RAG Memory**, **real FAO satellite data**, and **MCP hardware actuation** to make financially optimized, physically-grounded irrigation decisions.

---

## 🌊 The Crisis This Solves

Algeria is among the world's most acutely water-stressed nations:

| Year | Per-Capita Water Availability |
|------|------------------------------|
| 1962 | 1,500 m³/person/year |
| 2000 | 720 m³/person/year |
| **2050 (projected)** | **220 m³/person/year** |

Agriculture is the **single largest consumer** of this collapsing resource — accounting for over 70% of all water withdrawn nationally. Traditional farming, relying on human intuition and manual observation, is fundamentally incapable of managing water efficiency at scale under these pressures.

This system is directly inspired by the **Gardens of Babylon** project in **Mascara, Algeria** — a landmark vertical farming initiative that proved water-efficient, AI-assisted cultivation is achievable even in the most arid Mediterranean climates. Agri-Agent Swarm translates that vision into a fully autonomous, API-driven agentic pipeline, making these capabilities accessible beyond well-funded institutions.

**The financial case**: Water costs for a 10,000 m² Algerian wheat farm under standard irrigation routinely exceed 15,000 DZD per cycle. A 20% reduction in unnecessary irrigation events — achievable with this system's real-time AI decision-making — represents a measurable, compounding return on every run.

---

## ✨ Features

- **Parallel Multi-Agent Orchestration**: Meteorologist and Botanist agents run concurrently (fan-out/fan-in), cutting pipeline latency by ~50%
- **Critical Anomaly Detection**: `anomaly_check_node` inspects live sensor readings for extreme heat (>45°C), sensor flooding (>92%), sensor failure (<1%), and critical salinity (>8 dS/m) — routing directly to human review without wasting LLM API calls
- **Multi-Tenancy & Farm Isolation**: Complete `User` and `Farm` data models with role-based access control (`admin`, `operator`, `viewer`), farm selection, and scoped audit trails
- **MCP Hardware Actuation & SQLite Persistence**: `actuator_node` calls an **MCP-compliant** FastMCP server (`irrigate_valve`, `emergency_stop`, `get_valve_status`, `list_recent_valves`) backed by SQLite so physical valve commands survive restarts
- **Alembic Versioned Migrations**: Automated, version-controlled database schema management with SQLite batch support
- **Automated Scheduled Farm Surveillance**: Built-in APScheduler daemon performing periodic background health and anomaly checks across all registered farms
- **Multi-Channel Alerting**: Instant dispatch of critical sensor and agronomic alerts to in-app notification center, webhooks, and email
- **Full Observability Stack**: Prometheus metrics at `/metrics`, OpenTelemetry distributed tracing, and LangSmith diagnostics
- **FAO Satellite Water Productivity**: Live **ET₀ evapotranspiration** data from Open-Meteo (FAO-56 Penman-Monteith method — the same scientific basis as the FAO WaPOR platform used for regional water productivity monitoring across Algeria and North Africa)
- **Long-Term RAG Memory**: ChromaDB + Gemini Embeddings with **crop-type filtering** for targeted historical retrieval
- **SSE Streaming**: Real-time agent thoughts streamed to the React frontend via Server-Sent Events
- **Enterprise Frontend**: React 19, TypeScript, Zustand state management (`useAuthStore`, `useFarmStore`), and React Router with protected routes (`/login`, `/dashboard`, `/analytics`, `/farms`)
- **Rigorous Test Coverage**: 77 unit and integration tests with strict `>= 70%` automated coverage gates

---

## 🏗️ Architecture

```
                    ┌─────────────────────┐
                    │  IoT / Open-Meteo   │  ← temp, soil moisture, ET₀ (WaPOR proxy),
                    │  FAO ET₀ (WaPOR)    │    3-day precipitation forecast
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │  data_aggregation   │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │   anomaly_check     │  ← heat >45°C, flood >92%, failure <1%, salinity >8
                    └────────┬────────────┘
              ┌──────────────┤
        anomaly│             │normal (fan-out)
              ▼              ▼              ▼
    human_approval    meteorologist    botanist   + RAG Memory (ChromaDB + WaPOR context)
        gate               │              │
          │                └──────┬───────┘
          │              ┌────────▼────────┐
          │              │   financial     │  (consensus + cost function)
          │              └────────┬────────┘
          │              "wait"   │   "irrigate"
          │              ───END   │
          └──────────────►────────┘
                    ┌────────▼────────────┐
                    │  human_approval     │  ← HITL interrupt (both irrigate + anomaly)
                    └────────┬────────────┘
                    ┌────────▼────────────┐
                    │      actuator       │  ← MCP irrigate_valve / emergency_stop tool
                    └────────┬────────────┘
                             ▼
                    ┌─────────────────────┐
                    │ SQLite Persistence │  ← Valve commands & alerts survive restarts
                    └─────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | FastAPI, LangGraph 1.2, LangChain, SQLModel/SQLite, ChromaDB |
| **LLM Inference** | Groq (`qwen/qwen3.8-27b`) with structured output / Google Gemini 2.5 Flash |
| **Migrations** | Alembic (batch mode for SQLite) |
| **Frontend** | React 19, Vite, TypeScript, Zustand, React Router 7, TailwindCSS v4, Recharts, Lucide Icons |
| **Observability** | Prometheus client (`/metrics`), OpenTelemetry SDK, LangSmith diagnostics |
| **Automation** | APScheduler (AsyncIOScheduler) |
| **Hardware** | FastMCP server (`irrigate_valve`, `emergency_stop`, `get_valve_status`, `list_recent_valves`) |
| **Satellite Data** | Open-Meteo FAO ET₀ (Penman-Monteith) — WaPOR-equivalent water productivity index |
| **DevOps & QA** | GitHub Actions CI/CD, Docker Compose, Pytest, Pytest-Cov (>=70% gate), Pydantic-Settings |

---

## 🚀 Quick Start

### 1. Configure Environment

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Key environment variables:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_free_groq_api_key
GROQ_MODEL=qwen/qwen3.8-27b
GOOGLE_API_KEY=your_gemini_api_key_here
JWT_SECRET_KEY=generate_a_random_32_byte_hex_key
ADMIN_PASSWORD=your_secure_password
```

### 2. Run Database Migrations

Apply the versioned Alembic migrations:
```bash
alembic upgrade head
```

### 3. Run Locally (Dev Mode)

**Terminal 1 — Backend:**
```bash
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd agri-dashboard
npm install
npm run dev
```

**Default Test Credentials:**
- **Operator / Admin**: `admin` / `changeme` (or configured `ADMIN_PASSWORD`)
- **Viewer**: `viewer` / `viewer123`

### 4. Run with Docker Compose

```bash
docker compose up --build
```

- **Dashboard**: http://localhost:5173
- **API Documentation**: http://localhost:8000/docs
- **Prometheus Metrics**: http://localhost:8000/metrics

---

## 📡 API Endpoints (v1)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/auth/token` | OAuth2 JWT login (username/password) | Public |
| `GET` | `/health` | Health check & system status | Public |
| `GET` | `/metrics` | Prometheus metrics scrape endpoint | Public |
| `GET` | `/api/v1/farms` | List authorized farms for current user | Viewer/Operator |
| `POST` | `/api/v1/farms` | Create a new farm record | Operator/Admin |
| `POST` | `/api/v1/analyze` | Start multi-agent analysis (SSE stream) | Operator/Admin |
| `POST` | `/api/v1/actuate` | Approve/reject irrigation or resolve anomaly | Operator/Admin |
| `GET` | `/api/v1/history` | Multi-tenant decision audit trail | Viewer/Operator |
| `GET` | `/api/v1/stats` | KPI aggregate statistics | Viewer/Operator |
| `GET` | `/api/v1/valves` | Persistent MCP valve actuation log | Viewer/Operator |
| `POST` | `/api/v1/valves/emergency-stop` | Emergency stop all valves | Operator/Admin |
| `GET` | `/api/v1/alerts` | Critical anomaly & agronomic alert logs | Viewer/Operator |
| `POST` | `/api/v1/alerts/{id}/ack` | Acknowledge an alert | Operator/Admin |
| `POST` | `/api/v1/scheduler/run-now` | Trigger on-demand background farm scan | Operator/Admin |
| `GET` | `/api/v1/observability/langsmith` | LangSmith LLM cost tracking status | Operator/Admin |

*(Legacy `/api/*` endpoints are preserved for full backward compatibility).*

---

## 🔌 MCP Tools

The `mcp_server.py` exposes FastMCP tools backed by persistent SQLite storage:

| Tool | Description |
|------|-------------|
| `irrigate_valve` | Dispatch water volume to field valve; logs command to SQLite |
| `get_valve_status` | Retrieve execution state and telemetry for a valve command |
| `emergency_stop` | Immediately close all active valves in the system |
| `list_recent_valves` | Query recent valve actions for a specific farm |

---

## 💡 Key Architecture Decisions

### Why LangGraph?
LangGraph's directed acyclic graph model is the only framework that natively supports **stateful durable execution** and **interrupt-based HITL** checkpoints via SQLite persistence — essential for physical-world actuation where the graph must survive across HTTP requests.

### Why MCP for Actuation?
The Model Context Protocol (MCP) is the emerging **open standard** for agent-to-tool interfacing. Using FastMCP ensures the hardware layer is framework-agnostic and callable by any future MCP-compatible orchestrator — not locked to LangGraph or any specific LLM provider.

### Why Anomaly Detection Before Agents?
Running LLM agents during a hardware emergency (e.g., sensor failure) wastes API tokens, introduces latency, and risks a hallucinated "irrigate" decision that could destroy crops. The `anomaly_check_node` gate prevents this with deterministic rule-based logic at zero LLM cost.

### Why FAO ET₀ Instead of Hardcoded Values?
The WaPOR platform (Water Productivity through Open access of Remotely sensed data) is the FAO's official satellite data source for regional water productivity monitoring across Algeria and North Africa. Open-Meteo's ET₀ uses the identical FAO-56 Penman-Monteith computation — providing live, location-specific water productivity data without requiring a WaPOR API key, while preserving full scientific equivalence.

### Token Economics
- **Parallel execution** halves wall-clock latency vs. sequential agents
- **Anomaly bypass** eliminates ~3 Gemini API calls during hardware emergencies
- **Structured output** (`llm.with_structured_output(PydanticModel)`) eliminates JSON parsing failures and retry loops
- **Tenacity retry** (3 attempts, exponential backoff) handles free-tier rate limits gracefully

---

## 📸 Frontend Pages & Navigation

Navigate to `http://localhost:5173`:
- **/login**: Glassmorphic authentication with 1-click Quick Login presets (`admin` / `viewer`).
- **/dashboard**: Farm selector, live telemetry config, animated agent swarm timeline, agent report cards, and Human-in-the-Loop approval gate.
- **/analytics**: High-level KPIs, historical irrigation chart, outcome feedback submission, and persistent MCP valve actuation audit ledger with Emergency STOP.
- **/farms**: Multi-farm management cards, "Add Farm" modal, and on-demand background anomaly scan trigger.

---

## 🧪 Testing & Quality Gates

The test suite enforces a strict `>= 70%` code coverage threshold:

```bash
pip install -r requirements.txt
pytest
```

Current test suite status:
- **77 passed** across unit, integration, security, and MCP tests
- **70.32% overall code coverage**
- Fully automated CI/CD pipeline in `.github/workflows/ci.yml` verifying linting, pytest, coverage gates, and frontend production builds.

---

*Built with modern AI Engineering principles — LangGraph, MCP, RAG, HITL, parallel agent execution, and real satellite data. Designed for the crisis that matters: water scarcity in the agricultural heartlands of Algeria and the Mediterranean.*
