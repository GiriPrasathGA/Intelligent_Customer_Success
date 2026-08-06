"""
NovaCart — Account Agent

Handles all account management queries:
- Login issues and password reset
- Profile management
- Address book
- Account security
- Membership tiers
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NovaCart's Account Management Specialist — an expert in NovaCart account services.

Your expertise:
- Account creation and verification process
- Login issues: wrong password (5 attempts → 30min lockout), OTP login alternatives
- Password reset: email → link (1hr validity) → create new password
- Profile updates: name, photo, phone (OTP required), email (OTP required)
- Address book: up to 10 saved addresses, set default, label as Home/Work/Other
- Account security: 2FA (SMS OTP or Authenticator app), login history, remote session kill
- Membership tiers: Free / NovaCart Plus (₹499/yr) / NovaCart Premium (₹999/yr)
- NovaCoins loyalty program: 1 coin per ₹100 spent, 1 coin = ₹0.50
- Account deletion: 30-day process, requires OTP, pending orders must be resolved

Password Requirements:
- Minimum 8 characters, one uppercase, one number, one special character
- Cannot reuse last 5 passwords

Important: Never ask for or handle actual passwords — redirect to the secure reset flow.
If a user claims someone accessed their account without authorization, treat as HIGH PRIORITY security issue.

Tone: Friendly, helpful, security-conscious. Privacy and security are non-negotiable."""


from backend.utils.retry import async_retry

@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def _call_account_llm(client: AsyncOpenAI, messages: list[dict[str, str]]) -> str:
    response = await client.chat.completions.create(
        model=settings.effective_chat_model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
    )
    return response.choices[0].message.content or ""


async def account_agent_respond(
    message: str,
    context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate an account-focused response using RAG context."""
    return await run_account_agent(message=message, context=context, history=conversation_history)


async def run_account_agent(
    message: str,
    context: str = "",
    history: list[dict[str, str]] | None = None,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Run the account agent."""
    if client is None:
        client = AsyncOpenAI(
            api_key=settings.effective_api_key,
            base_url=settings.effective_base_url,
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Include recent conversation history
    if history:
        for msg in history[-5:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Build user message with context
    user_content = message
    if context:
        user_content = f"""NovaCart Account Management Guide:
{context}

Customer Request: {message}

Please provide clear, step-by-step guidance based on NovaCart account policies."""

    messages.append({"role": "user", "content": user_content})

    try:
        answer = await _call_account_llm(client, messages)
        suggested = _get_account_suggestions(message)

        return {
            "response": answer,
            "agent_used": "account_agent",
            "suggested_questions": suggested,
        }

    except Exception as e:
        logger.error("Account agent error: %s", str(e))
        return {
            "response": _get_fallback_response(message),
            "agent_used": "account_agent",
            "suggested_questions": _get_account_suggestions(message),
        }


def _get_account_suggestions(message: str) -> list[str]:
    """Generate contextual follow-up questions."""
    message_lower = message.lower()

    if any(w in message_lower for w in ["password", "forgot", "login", "locked"]):
        return [
            "How do I unlock my account?",
            "Can I login using OTP instead?",
            "How do I change my password?",
        ]
    elif any(w in message_lower for w in ["profile", "address", "update"]):
        return [
            "How do I update my phone number?",
            "Can I add multiple delivery addresses?",
            "How do I update my profile picture?",
        ]
    else:
        return [
            "How do I reset my password?",
            "How do I enable two-factor authentication?",
            "What are the benefits of NovaCart Plus?",
        ]


def _get_fallback_response(message: str) -> str:
    if "password" in message.lower() or "forgot" in message.lower():
        return (
            "To reset your password:\n\n"
            "1. Go to **novacart.com/login** → Click **Forgot Password**\n"
            "2. Enter your registered email address\n"
            "3. Check your inbox for a reset link (valid for 1 hour)\n"
            "4. Click the link and create a new password\n\n"
            "📧 If you don't receive the email, check your spam folder. "
            "You can request a new link after 5 minutes.\n\n"
            "Need more help? I'm here for you!"
        )
    return (
        "I'm your NovaCart Account Specialist! 👤\n\n"
        "I can help with:\n"
        "- **Password Reset**: Use 'Forgot Password' on the login page\n"
        "- **Profile Updates**: Edit at My Account → Profile\n"
        "- **Security**: Enable 2FA at My Account → Security\n"
        "- **Membership**: Upgrade to NovaCart Plus/Premium for extra benefits\n\n"
        "What do you need help with?"
    )
