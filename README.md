# NovaCart AI Customer Support — Project README
# ==================================================

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Edit `.env` with your Nexus API credentials:
```env
NEXUS_API_KEY=your_actual_api_key
NEXUS_BASE_URL=https://api.nexus.ai/v1
CHAT_MODEL=nexus-gpt-4o
EMBEDDING_MODEL=nexus-text-embedding-3
```

### 3. Start the Server
```bash
# From project root (not backend/)
python -m uvicorn backend.main:app --reload --port 8000
```

Or use the start script:
```bash
python start.py --install
```

### 4. Open the App
- **Frontend**: http://localhost:8000/
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## Project Structure
```
├── backend/
│   ├── config/         # Central config (edit models.py to change LLM)
│   ├── agents/         # 8 LangGraph specialist agents
│   ├── rag/            # LangChain RAG pipeline
│   ├── api/            # Mock REST API endpoints
│   ├── knowledge/      # 15 novaTech knowledge documents
│   ├── main.py         # FastAPI entry point
│   ├── graph.py        # LangGraph state machine
│   ├── auth.py         # JWT authentication
│   └── database.py     # SQLAlchemy async models
└── frontend/
    ├── index.html      # Chat interface
    ├── profile.html    # User Profile
    ├── css/            # Dark theme CSS
    └── js/             # Vanilla JS modules
```

## Changing the AI Model
Edit **only** `backend/config/config.py`:
```python
chat_model: str = "your-new-model"
embedding_model: str = "your-new-embedding-model"
```
No other file needs to change.

## Force Re-ingest Knowledge Base
```bash
curl -X POST http://localhost:8000/api/admin/reingest
```
