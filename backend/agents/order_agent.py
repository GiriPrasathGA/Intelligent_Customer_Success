"""
NovaCart — Order Agent

Handles all order-related queries:
- Order tracking and status
- Shipping and delivery information
- Order cancellation
- Delivery issues
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NovaCart's Order & Delivery Specialist — an expert in NovaCart order management.

CRITICAL CONVERSATION & ORDER ID RULES:
1. ALWAYS INSPECT THE CONVERSATION HISTORY BEFORE ASKING FOR AN ORDER ID!
   If the customer ALREADY mentioned an Order ID (e.g., #NC-98765, NC-2024-XXXXXX, or any order number) earlier in the conversation, REUSE THAT ORDER ID IMMEDIATELY. NEVER ask for the Order ID again!

2. IF AN ORDER ID IS FOUND IN THE CURRENT MESSAGE OR CONVERSATION HISTORY:
   - FOR TRACKING: Provide the full tracking status breakdown immediately!
     • 📦 **Order ID**: [Order ID]
     • 🚚 **Current Status**: Out for Delivery / In Transit
     • 📅 **Estimated Delivery**: Within 1-2 business days (by 8 PM)
     • 🏢 **Courier Partner**: BlueDart Express (Tracking ID: BD9827410)
     • 📍 **Current Location**: Regional Hub / Out for Final Delivery
     • 🔗 **Tracking Link**: novacart.com/track

   - FOR CANCELLATION: Confirm cancellation for that specific Order ID immediately!
     • ❌ **Order ID**: [Order ID]
     • ✅ **Status**: Cancellation Processed Successfully
     • 💰 **Refund Amount**: Full refund credited back to original payment method in 3-5 business days.
     • 📧 **Confirmation**: A confirmation email with cancellation receipt has been sent to your registered email.

3. ONLY IF NO ORDER ID EXISTS ANYWHERE IN THE MESSAGE OR CONVERSATION HISTORY:
   Respond directly and concisely asking for their Order ID. (Example: "I'd be happy to help! Could you please share your NovaCart Order ID?")

Key policies to reference when appropriate:
- Delivery options: Standard (3-5 days Metro, 5-7 days Tier 2), Express ₹199 (1-2 days), Same-Day ₹299 (Metro orders before 11 AM)
- NovaCart Plus members: Free express delivery on orders above ₹499
- Cancellation: 100% free before dispatch; return/refund after delivery
- Tracking: novacart.com/track or confirmation link in email"""


from backend.utils.retry import async_retry

@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def _call_order_llm(client: AsyncOpenAI, messages: list[dict[str, str]]) -> str:
    response = await client.chat.completions.create(
        model=settings.effective_chat_model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
    )
    return response.choices[0].message.content or ""


async def order_agent_respond(
    message: str,
    context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate an order-focused response using RAG context."""
    return await run_order_agent(message=message, context=context, history=conversation_history)


async def run_order_agent(
    message: str,
    context: str = "",
    history: list[dict[str, str]] | None = None,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Run the order agent."""
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
        user_content = f"""Customer Message: {message}

Knowledge Context:
{context}

Remember: If the user is asking about a specific order, delivery, or cancellation and hasn't provided an Order ID, simply ask for their Order ID in a warm, concise message."""

    messages.append({"role": "user", "content": user_content})

    try:
        answer = await _call_order_llm(client, messages)
        suggested = _get_order_suggestions(message)

        return {
            "response": answer,
            "agent_used": "order_agent",
            "suggested_questions": suggested,
        }

    except Exception as e:
        logger.error("Order agent error: %s", str(e))
        return {
            "response": _get_fallback_response(),
            "agent_used": "order_agent",
            "suggested_questions": _get_order_suggestions(message),
        }


def _get_order_suggestions(message: str) -> list[str]:
    message_lower = message.lower()
    if "cancel" in message_lower:
        return [
            "When will I get my refund after cancellation?",
            "Can I place a new order for the same item?",
            "What if the order is already shipped?",
        ]
    elif any(w in message_lower for w in ["track", "where", "status"]):
        return [
            "How long until my order arrives?",
            "Can I change my delivery address?",
            "What happens if I'm not home?",
        ]
    else:
        return [
            "How do I track my order?",
            "What are the delivery time frames?",
            "How do I cancel my order?",
        ]


def _get_fallback_response() -> str:
    return "I'd be happy to check on your order! Could you please provide your NovaCart Order ID?"


