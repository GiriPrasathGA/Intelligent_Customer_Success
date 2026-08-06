"""
NovaCart AI Customer Support — Application Settings

App-level settings: CORS, logging, startup configuration.
"""

from pathlib import Path

from backend.config.config import settings

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    # Production origins would be added here
    settings.frontend_url,
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# ── Qdrant ────────────────────────────────────────────────────────────────────
QDRANT_COLLECTION_NAME = settings.qdrant_collection_name
EMBEDDING_DIMENSION = 1536          # Nexus text-embedding-3 dimension
QDRANT_DISTANCE_METRIC = "Cosine"

# ── RAG ───────────────────────────────────────────────────────────────────────
RAG_CHUNK_SIZE = 800
RAG_CHUNK_OVERLAP = 150
RAG_TOP_K = 5                       # number of chunks to retrieve
RAG_SCORE_THRESHOLD = 0.35          # minimum similarity score

# ── Knowledge Base ────────────────────────────────────────────────────────────
KNOWLEDGE_BASE_DIR = str(Path(__file__).resolve().parent.parent / "knowledge")

KNOWLEDGE_DOCUMENT_CATEGORIES = {
    "09 novatech account management guide.pdf": "account",
    "05 novatech product user manua.pdf": "products",
    "1_Product_catalog.pdf": "products",
    "07 novatech order provisioning delivery policy.pdf": "shipping",
    "08 novatech return refund policy.pdf": "returns",
    "06 novatech warranty service policy.pdf": "warranty",
    "02 novatech pricing subscription guide.pdf": "payments",
    "3_customer_support.pdf": "support",
    "4_troubleshooting_guide.pdf": "support",
    "10 novatech privacy security policy.pdf": "legal",
}

# ── Agent Routing ─────────────────────────────────────────────────────────────
AGENT_ROUTING_KEYWORDS = {
    "product_agent": [
        "product", "item", "specification", "spec", "feature", "availability",
        "stock", "compare", "comparison", "model", "brand", "color", "size",
        "weight", "dimension", "camera", "battery", "display", "processor",
    ],
    "order_agent": [
        "order", "track", "tracking", "shipping", "delivery", "dispatch",
        "cancel", "cancellation", "shipped", "arrived", "package", "courier",
        "estimated", "arrive", "when will",
    ],
    "billing_agent": [
        "payment", "pay", "invoice", "receipt", "refund", "coupon", "discount",
        "promo", "code", "charge", "billing", "transaction", "bank", "card",
        "upi", "wallet", "emi", "installment",
    ],
    "warranty_agent": [
        "warranty", "guarantee", "repair", "replacement", "broken", "defective",
        "damage", "claim", "service center", "fix",
    ],
    "account_agent": [
        "account", "login", "sign in", "password", "forgot", "reset", "profile",
        "email", "phone", "address", "update account", "register", "signup",
        "verification", "otp",
    ],
    "support_agent": [
        "not working", "issue", "problem", "error", "troubleshoot", "help",
        "setup", "configure", "connect", "install", "crash", "slow", "restart",
        "technical", "support",
    ],
    "human_agent": [
        "fraud", "scam", "legal", "lawyer", "complaint", "escalate", "manager",
        "human", "agent", "representative", "urgent", "serious",
    ],
}

# ── Chat ──────────────────────────────────────────────────────────────────────
MAX_CONVERSATION_HISTORY = 20       # messages to keep in memory
SUGGESTED_QUESTIONS_COUNT = 3

# Starter suggestions shown in empty chat
STARTER_SUGGESTIONS = [
    "Track my order",
    "Return a product",
    "Cancel my order",
    "Compare products",
    "Recommend a phone under ₹30,000",
]

# ── Open-Source Voice Settings ───────────────────────────────────────────────
WHISPER_MODEL_NAME = "base.en"       # Open-Source Whisper model size (tiny.en, base.en, small.en)
PIPER_VOICE_MODEL = "en_US-lessac-medium"  # Open-Source Piper voice model
VOICE_TEMP_DIR = "backend/voice/temp"
