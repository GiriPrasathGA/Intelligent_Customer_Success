"""
novaTech AI Customer Support — Pydantic Data Models

Request/Response schemas for all API endpoints.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field


# ── Authentication ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    phone: Optional[str] = None
    address: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserPublic"


class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    stream: bool = True


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    agent_used: Optional[str] = None
    sources: list[dict[str, Any]] = []
    suggested_questions: list[str] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    escalated: bool = False


class ConversationSummary(BaseModel):
    id: str
    title: str
    last_message: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[ChatMessage]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── TTS ───────────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str = Field(..., max_length=5000)
    voice: str = "nova"
    speed: float = Field(1.0, ge=0.5, le=2.0)


# ── Mock API Schemas ──────────────────────────────────────────────────────────

class Product(BaseModel):
    id: str
    name: str
    category: str
    price: float
    original_price: Optional[float] = None
    discount_percent: Optional[int] = None
    availability: str  # "in_stock" | "out_of_stock" | "limited"
    rating: float
    review_count: int
    description: str
    specifications: dict[str, Any] = {}
    warranty_months: int = 12


class Order(BaseModel):
    id: str
    customer_id: int
    status: str
    items: list[dict[str, Any]]
    total_amount: float
    shipping_address: str
    tracking_number: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TrackOrderRequest(BaseModel):
    order_id: str
    email: Optional[str] = None


class ReturnRequest(BaseModel):
    order_id: str
    item_id: str
    reason: str
    description: Optional[str] = None


class RefundRequest(BaseModel):
    order_id: str
    amount: Optional[float] = None
    reason: str


class SupportTicket(BaseModel):
    subject: str
    description: str
    category: str
    priority: str = "medium"
    order_id: Optional[str] = None


class FAQItem(BaseModel):
    id: int
    question: str
    answer: str
    category: str
    helpful_count: int = 0
