# 🤖 NovaCart AI — Intelligent Customer Success Copilot

> A production-grade, multi-agent AI Customer Support platform powered by **LangGraph**, **RAG (Retrieval-Augmented Generation)**, **FastAPI**, and a modern glassmorphic frontend.

---

## ✨ Overview

NovaCart AI is an **intelligent customer success copilot** that routes customer queries to specialized AI agents — each expert in a different domain (orders, products, billing, returns, warranty, and more). It uses a **LangGraph state machine** to orchestrate agents, a **Qdrant vector database** for RAG-powered knowledge retrieval, and a **premium dark-mode web interface** for seamless customer interactions.

### 🎯 Key Capabilities
- 🔀 **Intelligent Agent Routing** — Supervisor LLM routes queries to the most appropriate specialist agent
- 📦 **Order Tracking & Management** — Real-time order status, cancellations, delivery ETA
- 🛍️ **Product Recommendations** — AI-powered product comparison and discovery
- 💳 **Billing & Payments** — Invoice queries, payment issues, subscription management
- ↩️ **Returns & Refunds** — Policy-aware returns processing and refund initiation
- 🛡️ **Warranty & Support** — Warranty claim processing and technical troubleshooting
- 📄 **RAG Knowledge Base** — PDF knowledge documents ingested into Qdrant vector DB
- 🎙️ **Voice I/O** — Whisper STT + TTS voice input and audio response playback
- 🔐 **Auth & Guest Sessions** — JWT authentication with auto-guest session fallback
- 💬 **Conversation History** — Persistent conversation sessions per user

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- A valid **Nexus API key** (or compatible OpenAI-compatible LLM provider)

### 1. Clone the Repository
```bash
git clone https://github.com/GiriPrasathGA/Intelligent_Customer_Success.git
cd Intelligent_Customer_Success
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```env
NEXUS_API_KEY=your_actual_api_key
NEXUS_BASE_URL=https://api.nexus.ai/v1
MODEL_NAME=nexus-gpt-4o
EMBEDDING_MODEL=nexus-text-embedding-3
QDRANT_URL=http://localhost:6333
QDRANT_STORAGE_PATH=./qdrant_storage
DATABASE_URL=sqlite:///./app.db
TEMPERATURE=0.7
MAX_TOKENS=2048
PORT=8000
```

### 5. Start the Server
Using the quick-start script (recommended):
```bash
python start.py
```

For first-time setup (installs deps automatically):
```bash
python start.py --install
```

Or run directly with Uvicorn:
```bash
python -m uvicorn backend.main:app --reload --port 8000
```

### 6. Open the App
| URL | Description |
|-----|-------------|
| http://localhost:8000/ | **Chat Interface** (Main App) |
| http://localhost:8000/docs | **Swagger API Docs** |
| http://localhost:8000/health | **Health Check** |

---

## 🗂️ Project Structure

```
Intelligent_Customer_Success/
├── backend/
│   ├── agents/
│   │   ├── supervisor.py        # LLM-powered agent router
│   │   ├── order_agent.py       # Order tracking & management
│   │   ├── product_agent.py     # Product search & recommendations
│   │   ├── billing_agent.py     # Billing & payment queries
│   │   ├── warranty_agent.py    # Warranty claims & service
│   │   ├── support_agent.py     # General customer support
│   │   ├── account_agent.py     # Account & profile management
│   │   └── human_agent.py       # Human escalation handler
│   ├── rag/
│   │   ├── rag_pipeline.py      # RAG orchestration
│   │   ├── embeddings.py        # Embedding model wrapper
│   │   ├── qdrant_db.py         # Qdrant vector store client
│   │   ├── loader.py            # PDF/text document loader
│   │   ├── splitter.py          # Document chunking
│   │   └── retriever.py        # Semantic similarity retriever
│   ├── config/
│   │   ├── config.py            # Central LLM & embedding config
│   │   ├── models.py            # Pydantic data models
│   │   └── settings.py         # App-wide settings
│   ├── api/
│   │   └── mock_api.py          # Mock product/order REST endpoints
│   ├── knowledge/               # PDF knowledge documents (RAG source)
│   ├── voice/
│   │   ├── stt_whisper.py       # Whisper Speech-to-Text
│   │   └── tts_piper.py        # Text-to-Speech
│   ├── main.py                  # FastAPI app, WebSocket, REST routes
│   ├── graph.py                 # LangGraph state machine definition
│   ├── auth.py                  # JWT auth, guest sessions
│   └── database.py              # SQLAlchemy async ORM models
├── frontend/
│   ├── index.html               # Main chat workspace (3-pane layout)
│   ├── css/
│   │   ├── style.css            # Global design system & tokens
│   │   └── chat.css             # Chat workspace component styles
│   └── js/
│       ├── app.js               # Auth, API client, toast utilities
│       ├── chat.js              # Chat UI logic, WebSocket, TTS/STT
│       └── profile.js           # User profile management
├── start.py                     # Quick-start launcher script
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment variable template
```

---

## 🧠 Architecture

```
User Browser (WebSocket / HTTP)
       │
       ▼
 FastAPI (main.py)
       │
       ▼
 LangGraph Supervisor Agent
  ├── 📦 Order Agent
  ├── 🛍️ Product Agent
  ├── 💳 Billing Agent
  ├── ↩️  Support Agent
  ├── 🛡️ Warranty Agent
  ├── 👤 Account Agent
  └── 🆘 Human Escalation Agent
       │
       ▼
 RAG Pipeline (Qdrant Vector DB + PDF Knowledge Base)
       │
       ▼
 LLM (Nexus / OpenAI-compatible)
```

---

## 🤖 Agents

| Agent | Expertise |
|-------|-----------|
| **Supervisor** | Classifies intent and routes to specialist agents |
| **Order Agent** | Order status, tracking, cancellations, delivery ETA |
| **Product Agent** | Product search, comparison, recommendations, specs |
| **Billing Agent** | Invoices, payment failures, subscriptions, refunds |
| **Support Agent** | General FAQs, troubleshooting, policies |
| **Warranty Agent** | Warranty claims, service requests, repair status |
| **Account Agent** | Profile updates, password reset, address management |
| **Human Agent** | Escalation to live human support agents |

---

## 🗃️ Knowledge Base

Knowledge documents are stored as PDFs in `backend/knowledge/` and automatically ingested into Qdrant on first startup:

- 📋 Product Catalog
- 💰 Pricing & Subscription Guide
- 📖 Product User Manual
- 🛡️ Warranty & Service Policy
- 🚚 Order Provisioning & Delivery Policy
- ↩️ Return & Refund Policy
- 👤 Account Management Guide
- 🔒 Privacy & Security Policy
- 🆘 Customer Support Guide
- 🔧 Troubleshooting Guide

### Re-ingest Knowledge Base
```bash
curl -X POST http://localhost:8000/api/admin/reingest
```

---

## ⚙️ Configuration

### Change LLM / Embedding Model
Edit **only** `backend/config/config.py`:
```python
chat_model: str = "your-new-chat-model"
embedding_model: str = "your-new-embedding-model"
```
No other file needs to change.

---

## 🎨 Frontend UI

The frontend is a **premium glassmorphic AI Copilot workspace** with:
- 🌑 Ultra-dark obsidian theme with animated mesh gradient background
- 📱 3-pane layout: Left Nav Drawer + Central Chat Stage + Right History Drawer
- 💬 Streaming markdown-rendered AI responses with agent routing badges
- 🎙️ Voice mic with Whisper STT + TTS audio playback controls
- 📄 RAG Evidence Inspector Modal with confidence scores and PDF links
- ✨ Micro-animations, glassmorphism, neon glow effects

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, Uvicorn |
| **AI Orchestration** | LangGraph, LangChain |
| **LLM** | Nexus API (OpenAI-compatible) |
| **Vector DB** | Qdrant |
| **Embeddings** | Nexus Text Embedding |
| **Database** | SQLAlchemy + SQLite |
| **Auth** | JWT (python-jose) |
| **Voice** | OpenAI Whisper STT, Piper TTS |
| **Frontend** | Vanilla HTML, CSS, JavaScript |
| **Fonts** | Plus Jakarta Sans, Inter, JetBrains Mono |

---

## 📄 License

This project is licensed for educational and demonstration purposes.

---

*Built with ❤️ by the NovaCart AI Team*
