"""
NovaCart — Warranty Agent

Handles all warranty-related queries:
- Warranty coverage and terms
- Warranty claim process
- NovaCartCare+ extended warranty plans
- Device repair and replacement
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NovaCart's Warranty & After-Sales Specialist — an expert on NovaCart's warranty and service programs.

Your expertise:
- Standard manufacturer warranties (Smartphones: 1yr, Laptops: 1-2yr, Appliances: 1-2yr + component warranty)
- NovaCartCare+ Extended Warranty plans (1yr, 2yr, Comprehensive)
- What's covered: Manufacturing defects, genuine hardware failures, screen/motherboard defects, battery health degradation
- What's NOT covered: Unauthorized tampering, unauthorized third-party repairs
- Warranty claim process: Register online → Diagnosis → Free Doorstep Pickup/Drop-off → Authorized Brand Service → Free Return Delivery
- Service center locations: novacart.com/service-centers
- Loaner device policy for repairs >7 days (Comprehensive plan)
- DOA (Dead on Arrival): Report within 48 hours for immediate replacement

NovaCartCare+ Plans:
- 1 Year: ₹999-₹2,999 + 1 accidental damage claim
- 2 Year: ₹1,999-₹5,999 + 2 accidental damage claims
- Comprehensive: ₹2,999-₹8,999 + unlimited accidental damage
- Must purchase within 30 days of device purchase

Key empathy notes:
- Customers with broken/faulty devices are stressed — be empathetic and solution-focused
- For DOA: Express urgency and initiate replacement immediately
- For damage claims: Clarify coverage before raising hopes
- Always ask for: Order ID + Serial number + Description of issue

Tone: Empathetic, professional, and solution-oriented."""


from backend.utils.retry import async_retry

@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def _call_warranty_llm(client: AsyncOpenAI, messages: list[dict[str, str]]) -> str:
    response = await client.chat.completions.create(
        model=settings.effective_chat_model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
    )
    return response.choices[0].message.content or ""


async def warranty_agent_respond(
    message: str,
    context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate a warranty-focused response using RAG context."""
    return await run_warranty_agent(message=message, context=context, history=conversation_history)


async def run_warranty_agent(
    message: str,
    context: str = "",
    history: list[dict[str, str]] | None = None,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Run the warranty agent."""
    if client is None:
        client = AsyncOpenAI(
            api_key=settings.effective_api_key,
            base_url=settings.effective_base_url,
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        for turn in history[-8:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

    user_content = message
    if context:
        user_content = f"""NovaCart Warranty & After-Sales Policies:
{context}

Customer Issue: {message}

Help the customer with their warranty concern. Be empathetic and provide clear next steps."""

    messages.append({"role": "user", "content": user_content})

    try:
        answer = await _call_warranty_llm(client, messages)
        suggested = _get_warranty_suggestions(message)

        return {
            "response": answer,
            "agent_used": "warranty_agent",
            "suggested_questions": suggested,
        }

    except Exception as e:
        logger.error("Warranty agent error: %s", str(e))
        return {
            "response": _get_fallback_response(),
            "agent_used": "warranty_agent",
            "suggested_questions": _get_warranty_suggestions(message),
        }


def _get_warranty_suggestions(message: str) -> list[str]:
    return [
        "How do I register my product for warranty?",
        "Where is the nearest NovaCart authorized service center?",
        "What is the NovaCartCare+ extended warranty?",
    ]


def _get_fallback_response() -> str:
    return (
        "I'm your NovaCart Warranty Specialist! 🛠️\n\n"
        "To raise a warranty claim, I'll need:\n"
        "1. **Order ID** (NC-YYYY-XXXXXX)\n"
        "2. **Product Serial Number** (found on device/box)\n"
        "3. **Description of the issue**\n\n"
        "**Standard Coverage**: All genuine consumer electronics get 1-year brand manufacturer warranty.\n"
        "**Extended**: NovaCartCare+ plans available for up to 3 years total coverage.\n\n"
        "Please describe what's happening with your device and I'll get this sorted for you!"
    )

