# 🌾 Agri-Agent Swarm v2.0

![Status](https://img.shields.io/badge/Status-Production%20Ready-success) ![Python](https://img.shields.io/badge/Python-3.11+-blue) ![React](https://img.shields.io/badge/React-19-cyan) ![LangGraph](https://img.shields.io/badge/AI-LangGraph%20Swarm-purple) ![MCP](https://img.shields.io/badge/Protocol-MCP-orange) ![Version](https://img.shields.io/badge/Version-2.0-orange)

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
- **MCP Hardware Actuation**: `actuator_node` calls an **MCP-compliant** FastMCP server (`irrigate_valve`, `emergency_stop`, `get_valve_status` tools) — implementing the Model Context Protocol standard for agent-to-hardware interfacing
- **FAO Satellite Water Productivity**: Live **ET₀ evapotranspiration** data from Open-Meteo (FAO-56 Penman-Monteith method — the same scientific basis as the FAO WaPOR platform used for regional water productivity monitoring across Algeria and North Africa)
- **Any-Location Support**: Configure latitude/longitude for any farm worldwide — live weather fetched automatically from Open-Meteo
- **Configurable Sensors**: Set water salinity, plant growth stage, farm area, and moisture threshold per run
- **Long-Term RAG Memory**: ChromaDB + Gemini Embeddings with **crop-type filtering** for targeted historical retrieval
- **SSE Streaming**: Real-time agent thoughts streamed to the React frontend via Server-Sent Events
- **Live Agent Timeline**: Visual pipeline progress bar animating as each agent completes
- **Human-in-the-Loop (HITL)**: LangGraph interrupt breakpoints pause execution for human authorization — for both irrigation approval AND anomaly review
- **Full Decision Audit Trail**: Every agent analysis stored in SQLite for compliance and review
- **Rich Analytics Dashboard**: KPI summary, area/trend charts, decision pie chart, expandable audit table
- **Outcome Feedback Loop**: Rate decisions (👍/👎) to reinforce AI learning via ChromaDB
- **Health Checks**: `/health` endpoint for Docker/load balancer integration
- **Centralized Config**: `pydantic-settings` for typed, environment-driven configuration
- **Structured Logging**: JSON-structured logs replacing all `print()` statements
- **Docker Ready**: Fully containerized with `docker-compose` and health-check dependencies

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
                    └─────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | FastAPI, LangGraph 1.2, LangChain, SQLite, ChromaDB, Google Gemini 2.5 Flash |
| **Frontend** | React 19, Vite, TypeScript, TailwindCSS v4, Recharts, Lucide Icons |
| **AI** | Gemini 2.5 Flash (structured output), Gemini Embeddings, LangGraph Swarm, ChromaDB RAG |
| **Hardware** | FastMCP server (`irrigate_valve`, `emergency_stop`, `get_valve_status` tools) |
| **Satellite Data** | Open-Meteo FAO ET₀ (Penman-Monteith) — WaPOR-equivalent water productivity index |
| **DevOps** | Docker, Docker Compose (with health checks), pydantic-settings |

---

## 🚀 Quick Start

### 1. Configure Environment

```env
# .env (in project root)
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional overrides:
# DEFAULT_LATITUDE=35.6911   # Default: Oran, Algeria
# DEFAULT_LONGITUDE=-0.6328
# CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
# GEMINI_MODEL=gemini-2.5-flash
```

### 2. Run with Docker

```bash
docker compose up --build
```

- **Dashboard**: http://localhost:5173
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 3. Run Locally (Dev Mode)

**Terminal 1 — Backend:**
```bash
pip install -r requirements.txt
uvicorn api:app --reload
```

**Terminal 2 — Frontend:**
```bash
cd agri-dashboard
npm install
npm run dev
```

**Optional — Standalone MCP Server** (for IDE/agent integration via stdio):
```bash
python mcp_server.py
```

### 4. Migrate Existing Database (one-time, v1.0 → v2.0)

```bash
python migrate_db.py
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/analyze` | Start analysis (SSE stream) |
| `POST` | `/api/actuate` | Approve/reject irrigation or resolve anomaly |
| `GET` | `/api/history` | Full decision audit log |
| `GET` | `/api/stats` | Aggregate statistics |
| `POST` | `/api/feedback` | Submit outcome rating |

---

## 🔌 MCP Tools

The `mcp_server.py` exposes three MCP-compliant tools callable by any MCP-compatible agent or IDE:

| Tool | Description |
|------|-------------|
| `irrigate_valve` | Dispatch water volume to field valve controller with full audit trail |
| `get_valve_status` | Query hardware state of a previously issued irrigation command |
| `emergency_stop` | Immediately close all active irrigation valves (anomaly response) |

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

## 📸 Screenshots

Run the app locally and navigate to `http://localhost:5173` to see the live dashboard.
Key screens:
- **Farm Config Panel** — configure crop type, GPS coordinates, salinity, and area before each run
- **Agent Timeline** — animated pipeline showing Sensor Array → Meteorologist+Botanist → Financial Director → HITL Gate → Actuator
- **Analysis Results** — three agent report cards with confidence scores and RAG memory citations
- **Human Approval Gate** — shows water volume, cost, crop risk, and nutrient mix recommendation before actuation
- **Anomaly Alert** — emergency STOP / Override panel for critical sensor readings
- **Mayor's Ledger** — full analytics dashboard with trend charts, pie chart, and expandable decision audit table

---

## 🧪 Testing

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

The test suite covers:
- **Anomaly detection** — all 4 thresholds + boundary conditions (8 tests)
- **Graph routing** — `route_decision` and `route_after_anomaly_check` (5 tests)
- **Financial constants** — agronomic sanity checks, cap enforcement
- **API validation** — lat/lon range, field length, salinity range, feedback rating (10 tests)
- **Database** — aggregate stats key shape

---

*Built with modern AI Engineering principles — LangGraph, MCP, RAG, HITL, parallel agent execution, and real satellite data. Designed for the crisis that matters: water scarcity in the agricultural heartlands of Algeria and the Mediterranean.*
