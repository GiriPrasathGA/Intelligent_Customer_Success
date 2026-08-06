"""
NovaCart — Billing Agent

Handles all payment and financial queries:
- Payment methods and processing
- Refunds and timelines
- Invoices and receipts
- Coupon codes and discounts
- EMI and installment plans
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NovaCart's Billing & Payments Specialist — an expert on all financial matters at NovaCart.

Your expertise:
- All payment methods: Cards (Visa/Mastercard/RuPay/Amex), UPI (GPay, PhonePe, Paytm), Net Banking, NovaCart Wallet, EMI, COD, BNPL
- Coupon codes and discount application (one coupon per order, check eligibility)
- Refund timelines: UPI/NetBanking 3-5 days, Cards 5-7 days, NovaCart Wallet instant
- EMI plans: No-cost EMI (3/6/9/12 months on major bank cards) and low-cost standard EMI
- Bank offers: Instant discounts with HDFC, ICICI, SBI, Axis cards
- Invoice generation and GST invoice support for business buyers
- Double charge / payment failure resolution
- COD availability (orders below ₹50,000, ₹50 convenience fee)

Active demo coupons: NOVACART10, NOVACART20, NEWUSER, WELCOME25, TECH2024, FLASH50

Critical rules:
- If a customer reports double charge or unauthorized transaction, treat as HIGH PRIORITY
- Always verify refund eligibility before confirming
- Clarify if refund goes to original payment method or NovaCart wallet
- For payment disputes, provide the process clearly

Tone: Professional, precise, reassuring. Financial matters require accuracy — never give vague answers.
When uncertain about specific amounts, ask for the order ID to check."""


from backend.utils.retry import async_retry

@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def _call_billing_llm(client: AsyncOpenAI, messages: list[dict[str, str]]) -> str:
    response = await client.chat.completions.create(
        model=settings.effective_chat_model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
    )
    return response.choices[0].message.content or ""


async def billing_agent_respond(
    message: str,
    context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate a billing-focused response using RAG context."""
    return await run_billing_agent(message=message, context=context, history=conversation_history)


async def run_billing_agent(
    message: str,
    context: str = "",
    history: list[dict[str, str]] | None = None,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Run the billing agent."""
    if client is None:
        client = AsyncOpenAI(
            api_key=settings.effective_api_key,
            base_url=settings.effective_base_url,
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        for msg in history[-5:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    user_content = message
    if context:
        user_content = f"""NovaCart Billing & Payment Policies:
{context}

Customer Query: {message}

Provide accurate billing information. For specific order refunds/payments, ask for the order ID."""

    messages.append({"role": "user", "content": user_content})

    try:
        answer = await _call_billing_llm(client, messages)
        suggested = _get_billing_suggestions(message)

        return {
            "response": answer,
            "agent_used": "billing_agent",
            "suggested_questions": suggested,
        }

    except Exception as e:
        logger.error("Billing agent error: %s", str(e))
        return {
            "response": _get_fallback_response(),
            "agent_used": "billing_agent",
            "suggested_questions": _get_billing_suggestions(message),
        }


def _get_billing_suggestions(message: str) -> list[str]:
    message_lower = message.lower()
    if "refund" in message_lower:
        return [
            "How long does the refund take to process?",
            "Can I get refund to my NovaCart wallet instead?",
            "How do I track my refund status?",
        ]
    elif any(w in message_lower for w in ["coupon", "discount", "promo"]):
        return [
            "Can I stack multiple coupon codes?",
            "What are the current bank card offers?",
            "How do I apply a coupon at checkout?",
        ]
    elif "emi" in message_lower or "installment" in message_lower:
        return [
            "Which cards support no-cost EMI?",
            "Can I prepay my EMI without penalty?",
            "Is EMI available for all products?",
        ]
    else:
        return [
            "What payment methods do you accept?",
            "Do you offer no-cost EMI?",
            "How do I download my invoice?",
        ]


def _get_fallback_response() -> str:
    return (
        "I'm your NovaCart Billing Specialist! 💳 I can help with:\n\n"
        "- **Refunds**: Tracked via Order History. UPI: 3-5 days, Cards: 5-7 days, NovaCart Wallet: Instant\n"
        "- **Coupons**: Use codes like `NOVACART10`, `NOVACART20` at checkout\n"
        "- **EMI**: No-cost EMI available on orders above ₹5,000 with major credit cards\n"
        "- **Invoices**: Download from My Orders → [Order] → Download Invoice\n\n"
        "Please share your Order ID for specific payment queries."
    )

