"""
novaTech AI Customer Support — Main FastAPI Application

Entry point for the backend server.
Includes: Auth, Chat (WebSocket + HTTP), Mock API, TTS, Profile
"""

from __future__ import annotations

import io
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from fastapi import (
    Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect,
    status, File, UploadFile
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import (
    get_current_user, get_current_user_optional,
    register_user, login_user, forgot_password, reset_password,
)
from backend.config.config import settings
from backend.config.models import (
    RegisterRequest, LoginRequest, ForgotPasswordRequest,
    ResetPasswordRequest, ChatRequest, ChatResponse,
    UpdateProfileRequest, UserPublic, TTSRequest,
    ConversationSummary, ConversationDetail, ChatMessage,
)
from backend.config.settings import CORS_ORIGINS, STARTER_SUGGESTIONS, MAX_CONVERSATION_HISTORY
from backend.database import (
    User, Conversation, Message, init_db, get_db, AsyncSessionLocal
)
from backend.graph import process_chat
from backend.rag.rag_pipeline import ingest_knowledge_base

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NovaCart AI Customer Support API",
    description="Production-ready AI chatbot backend for NovaCart e-commerce platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Open for local dev; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("Starting NovaCart AI Customer Support API...")

    # Create database tables
    await init_db()
    logger.info("Database initialized")

    # Ingest knowledge base into Qdrant
    logger.info("Ingesting knowledge base...")
    result = await ingest_knowledge_base(force_reingest=True)
    logger.info("Knowledge base status: %s", result.get("status"))

    logger.info("NovaCart AI Customer Support API is ready! 🚀")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down NovaCart AI Customer Support API...")


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": "NovaCart AI Customer Support",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/suggestions", tags=["Chat"])
async def get_starter_suggestions():
    """Return starter questions for the chat UI."""
    return {"suggestions": STARTER_SUGGESTIONS}


# ── Authentication Routes ─────────────────────────────────────────────────────

@app.post("/api/auth/guest", tags=["Authentication"])
async def api_guest_login(db: AsyncSession = Depends(get_db)):
    """Auto-create or find a guest user and return a valid token (no login required)."""
    from backend.auth import hash_password, create_access_token

    guest_email = "guest@novacart.ai"
    result = await db.execute(select(User).where(User.email == guest_email))
    guest = result.scalar_one_or_none()

    if not guest:
        guest = User(
            name="Guest User",
            email=guest_email,
            hashed_password=hash_password("guest-no-login"),
            is_active=True,
            is_verified=True,
        )
        db.add(guest)
        await db.flush()
        await db.refresh(guest)

    token = create_access_token(guest.id)
    return {
        "access_token": token,
        "expires_in": settings.jwt_expire_minutes * 60,
        "user": {
            "id": guest.id,
            "name": guest.name,
            "email": guest.email,
        },
    }


@app.post("/api/auth/register", tags=["Authentication"])
async def api_register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register_user(req, db)


@app.post("/api/auth/login", tags=["Authentication"])
async def api_login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login_user(req, db)


@app.post("/api/auth/forgot-password", tags=["Authentication"])
async def api_forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    return await forgot_password(req, db)


@app.post("/api/auth/reset-password", tags=["Authentication"])
async def api_reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    return await reset_password(req, db)


# ── Profile Routes ────────────────────────────────────────────────────────────

@app.get("/api/profile", tags=["Profile"])
async def get_profile(current_user: User = Depends(get_current_user)):
    return UserPublic.model_validate(current_user)


@app.patch("/api/profile", tags=["Profile"])
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = req.model_dump(exclude_none=True)
    if update_data:
        for key, value in update_data.items():
            setattr(current_user, key, value)
        current_user.updated_at = datetime.utcnow()
    return UserPublic.model_validate(current_user)


# ── Conversation Routes ───────────────────────────────────────────────────────

@app.get("/api/conversations", tags=["Chat"])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all conversation summaries for the user."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    conversations = result.scalars().all()

    summaries = []
    for conv in conversations:
        # Get last message
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = msg_result.scalar_one_or_none()

        # Count messages
        count_result = await db.execute(
            select(Message).where(Message.conversation_id == conv.id)
        )
        msg_count = len(count_result.scalars().all())

        summaries.append({
            "id": conv.id,
            "title": conv.title,
            "last_message": last_msg.content[:80] + "..." if last_msg and len(last_msg.content) > 80 else (last_msg.content if last_msg else ""),
            "message_count": msg_count,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        })

    return summaries


@app.get("/api/conversations/{conversation_id}", tags=["Chat"])
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full conversation with messages."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = msg_result.scalars().all()

    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "agent_used": m.agent_used,
                "sources": json.loads(m.sources) if m.sources else [],
                "escalated": m.escalated,
                "timestamp": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }


@app.delete("/api/conversations/{conversation_id}", tags=["Chat"])
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    return {"success": True}


# ── Chat Route (HTTP) ─────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and receive an AI response (non-streaming)."""
    # Get or create conversation
    conversation_id = req.conversation_id or str(uuid.uuid4())

    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            id=conversation_id,
            user_id=current_user.id,
            title=req.message[:50] + ("..." if len(req.message) > 50 else ""),
        )
        db.add(conversation)
        await db.flush()

    # Load conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(MAX_CONVERSATION_HISTORY)
    )
    history_messages = history_result.scalars().all()

    conversation_history = [
        {"role": m.role, "content": m.content}
        for m in history_messages
    ]

    # Save user message
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)

    # Process through LangGraph
    result = await process_chat(
        message=req.message,
        conversation_history=conversation_history,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    # Save assistant message
    ai_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=result["response"],
        agent_used=result.get("agent_used"),
        sources=json.dumps(result.get("sources", [])),
        escalated=result.get("escalated", False),
    )
    db.add(ai_msg)

    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()

    return ChatResponse(
        conversation_id=conversation_id,
        message=result["response"],
        agent_used=result.get("agent_used"),
        sources=result.get("sources", []),
        suggested_questions=result.get("suggested_questions", []),
        escalated=result.get("escalated", False),
    )


# ── WebSocket Chat ────────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time streaming chat."""
    await websocket.accept()
    logger.info("WebSocket connection opened")

    try:
        while True:
            data = await websocket.receive_json()
            token = data.get("token")
            message = data.get("message", "")
            conversation_id = data.get("conversation_id") or str(uuid.uuid4())

            # Authenticate via token
            user = None
            if token:
                try:
                    from backend.auth import decode_token
                    payload = decode_token(token)
                    user_id = int(payload.get("sub", 0))

                    async with AsyncSessionLocal() as db:
                        result = await db.execute(
                            select(User).where(User.id == user_id, User.is_active == True)
                        )
                        user = result.scalar_one_or_none()
                except Exception:
                    pass

            if not user:
                await websocket.send_json({"error": "Authentication required", "type": "error"})
                continue

            # Send typing indicator
            await websocket.send_json({"type": "typing", "conversation_id": conversation_id})

            async with AsyncSessionLocal() as db:
                # Get or create conversation
                conv_result = await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = conv_result.scalar_one_or_none()

                if not conversation:
                    conversation = Conversation(
                        id=conversation_id,
                        user_id=user.id,
                        title=message[:50] + ("..." if len(message) > 50 else ""),
                    )
                    db.add(conversation)
                    await db.flush()

                # Load history
                history_result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                    .limit(MAX_CONVERSATION_HISTORY)
                )
                history_messages = history_result.scalars().all()
                conversation_history = [
                    {"role": m.role, "content": m.content}
                    for m in history_messages
                ]

                # Save user message
                user_msg = Message(
                    conversation_id=conversation_id,
                    role="user",
                    content=message,
                )
                db.add(user_msg)

                # Process through graph
                result = await process_chat(
                    message=message,
                    conversation_history=conversation_history,
                    conversation_id=conversation_id,
                    user_id=user.id,
                )

                # Save AI message
                ai_msg = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=result["response"],
                    agent_used=result.get("agent_used"),
                    sources=json.dumps(result.get("sources", [])),
                    escalated=result.get("escalated", False),
                )
                db.add(ai_msg)
                conversation.updated_at = datetime.utcnow()
                await db.commit()

            # Send full response
            await websocket.send_json({
                "type": "response",
                "conversation_id": conversation_id,
                "message": result["response"],
                "agent_used": result.get("agent_used"),
                "sources": result.get("sources", []),
                "suggested_questions": result.get("suggested_questions", []),
                "escalated": result.get("escalated", False),
                "timestamp": datetime.utcnow().isoformat(),
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", str(e))
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass


# ── STT & TTS Endpoints (Open-Source Whisper & Piper) ───────────────────────────

@app.post("/api/stt", tags=["Voice"])
async def speech_to_text(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Transcribe spoken user audio into text using Open-Source Whisper STT model.
    """
    from backend.voice.stt_whisper import transcribe_audio_bytes

    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio payload")

        transcription = await transcribe_audio_bytes(audio_bytes, filename=file.filename or "recording.webm")
        return {"text": transcription}

    except Exception as e:
        logger.error("STT transcription error: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to transcribe speech: {str(e)}"
        )


@app.post("/api/tts", tags=["Voice"])
async def text_to_speech(
    req: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate text-to-speech audio using Open-Source Piper TTS engine.
    """
    from backend.voice.tts_piper import synthesize_piper_speech

    try:
        audio_bytes = await synthesize_piper_speech(
            text=req.text,
            voice=req.voice or settings.PIPER_VOICE_MODEL
        )

        if not audio_bytes:
            raise HTTPException(status_code=500, detail="TTS synthesis returned empty audio")

        media_type = "audio/wav" if audio_bytes.startswith(b"RIFF") else "audio/mpeg"

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=media_type,
            headers={"Content-Disposition": "inline; filename=response.wav"},
        )

    except Exception as e:
        logger.warning("Piper TTS API error (%s)", str(e))
        raise HTTPException(
            status_code=503,
            detail="Open-source Text-to-Speech service unavailable.",
        )



# ── RAG Admin ─────────────────────────────────────────────────────────────────

@app.post("/api/admin/reingest", tags=["Admin"])
async def reingest_knowledge_base():
    """Force re-ingest of knowledge base into Qdrant."""
    result = await ingest_knowledge_base(force_reingest=True)
    return result


@app.get("/api/admin/rag-status", tags=["Admin"])
async def rag_status():
    """Get current knowledge base / Qdrant status."""
    from backend.rag.qdrant_db import get_qdrant_client, get_collection_info
    client = get_qdrant_client()
    info = get_collection_info(client)
    return info


# ── Knowledge Base Document Inspector & Streaming ─────────────────────────────

@app.get("/api/knowledge/document/{document_name}", tags=["Knowledge"])
async def get_knowledge_document(document_name: str):
    """
    Fetch document text and page breakdown for interactive UI highlight modal.
    """
    from pathlib import Path
    from backend.config.settings import KNOWLEDGE_BASE_DIR
    
    # Safe path resolution
    base_dir = Path(KNOWLEDGE_BASE_DIR).resolve()
    target_path = (base_dir / document_name).resolve()
    
    # Security: prevent directory traversal
    if not str(target_path).startswith(str(base_dir)):
        raise HTTPException(status_code=400, detail="Invalid document path")
        
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge document '{document_name}' not found")
        
    file_type = target_path.suffix.lower().lstrip(".")
    pages_data = []
    full_text = ""
    
    if file_type == "pdf":
        try:
            import fitz
            doc = fitz.open(str(target_path))
            for idx, page in enumerate(doc):
                p_text = page.get_text().strip()
                pages_data.append({
                    "page": idx + 1,
                    "text": p_text
                })
            full_text = "\n\n--- Page Break ---\n\n".join(p["text"] for p in pages_data)
        except Exception as e:
            logger.error("Error reading PDF %s: %s", document_name, e)
            raise HTTPException(status_code=500, detail=f"Could not parse PDF: {str(e)}")
    else:
        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                full_text = f.read()
            pages_data.append({"page": 1, "text": full_text})
        except Exception as e:
            logger.error("Error reading text file %s: %s", document_name, e)
            raise HTTPException(status_code=500, detail=f"Could not read document: {str(e)}")
            
    return {
        "document_name": document_name,
        "file_type": file_type,
        "file_size": target_path.stat().st_size,
        "total_pages": len(pages_data),
        "pages": pages_data,
        "full_text": full_text,
        "file_url": f"/api/knowledge/file/{document_name}",
    }


@app.get("/api/knowledge/file/{document_name}", tags=["Knowledge"])
async def get_knowledge_file(document_name: str):
    """
    Stream the raw PDF or knowledge document file for browser inline viewing.
    """
    from pathlib import Path
    from backend.config.settings import KNOWLEDGE_BASE_DIR
    
    base_dir = Path(KNOWLEDGE_BASE_DIR).resolve()
    target_path = (base_dir / document_name).resolve()
    
    if not str(target_path).startswith(str(base_dir)) or not target_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    media_type = "application/pdf" if target_path.suffix.lower() == ".pdf" else "text/plain"
    return FileResponse(
        path=str(target_path),
        media_type=media_type,
        filename=document_name,
        headers={"Content-Disposition": f'inline; filename="{document_name}"'},
    )


# ── Include Mock API Router ───────────────────────────────────────────────────

from backend.api.mock_api import router as mock_router
app.include_router(mock_router)


# ── Serve Frontend Static Files ───────────────────────────────────────────────

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
