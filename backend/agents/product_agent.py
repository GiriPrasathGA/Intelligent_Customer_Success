"""
NovaCart — Product Agent

Handles all product-related queries:
- Product details and specifications
- Availability and stock status
- Product recommendations
- Product comparison
- Price information
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NovaCart's Product Specialist — an expert on all genuine consumer electronics and products on NovaCart.

Your personality: Enthusiastic, knowledgeable, and helpful. You love helping customers find the perfect product from real-world brands (Apple, Samsung, OnePlus, Google Pixel, Motorola, Dell, HP, Lenovo, ASUS, Sony, Boat, JBL, etc.).

Your expertise:
- Detailed product specifications (display, processor, RAM, storage, camera, battery, build)
- Price ranges, real-time comparisons, and current offers
- Product availability and stock levels across NovaCart fulfillment centers
- Honest, objective product comparisons across brands and models
- Personalized recommendations tailored to budget (e.g. Under ₹30,000) and user requirements

Guidelines:
- Always mention prices in INR (₹) when discussing products
- Highlight ongoing discounts, bank offers, and exchange value
- For comparisons, use structured format with clean bullet points
- When a product is out of stock or over budget, suggest suitable alternatives
- Always include key specs (display, chipset, camera, battery)
- Mention NovaCart's return policy (10 days for electronics) and 100% genuine brand warranty
- If a specific product isn't in your knowledge, provide helpful general guidance

Response format:
- Use clean markdown for formatting (bold product names, concise bullet points)
- Keep responses engaging, structured, and easy to read
- Include a clear recommendation at the end when comparing or advising
- Mention warranty coverage

You represent NovaCart — maintain a premium, professional, and helpful tone at all times."""


from backend.utils.retry import async_retry

@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def _call_product_llm(client: AsyncOpenAI, messages: list[dict[str, str]]) -> str:
    response = await client.chat.completions.create(
        model=settings.effective_chat_model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
    )
    return response.choices[0].message.content or ""


async def product_agent_respond(
    message: str,
    context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate a product-focused response using RAG context."""
    return await run_product_agent(message=message, context=context, history=conversation_history)


async def run_product_agent(
    message: str,
    context: str = "",
    history: list[dict[str, str]] | None = None,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Run the product agent."""
    if client is None:
        client = AsyncOpenAI(
            api_key=settings.effective_api_key,
            base_url=settings.effective_base_url,
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Include recent conversation history (last 5 messages)
    if history:
        for msg in history[-5:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Build user message with context
    user_content = message
    if context:
        user_content = f"""Knowledge Base Context:
{context}

Customer Question: {message}

Please answer based on the above context. If context doesn't contain the answer, use your general knowledge about NovaCart's genuine consumer electronics catalog."""

    messages.append({"role": "user", "content": user_content})

    try:
        answer = await _call_product_llm(client, messages)

        # Generate contextual follow-up questions
        suggested = _get_product_suggestions(message)

        return {
            "response": answer,
            "agent_used": "product_agent",
            "suggested_questions": suggested,
        }


    except Exception as e:
        logger.error("Product agent error: %s", str(e))
        return {
            "response": _get_fallback_response(message),
            "agent_used": "product_agent",
            "suggested_questions": _get_product_suggestions(message),
        }


def _get_product_suggestions(message: str) -> list[str]:
    """Generate contextual follow-up questions."""
    message_lower = message.lower()

    if any(w in message_lower for w in ["phone", "smartphone", "mobile"]):
        return [
            "What are the camera specs of this phone?",
            "Does it support 5G connectivity?",
            "What warranty does this come with?",
        ]
    elif any(w in message_lower for w in ["laptop", "computer"]):
        return [
            "Can I upgrade the RAM on this laptop?",
            "What is the battery life?",
            "Is this good for gaming/video editing?",
        ]
    elif any(w in message_lower for w in ["compare", "vs", "difference", "better"]):
        return [
            "Which one has better battery life?",
            "Which is more value for money?",
            "What are the warranty differences?",
        ]
    else:
        return [
            "What are the available color options?",
            "Is this product currently in stock?",
            "Are there any ongoing discounts?",
        ]


def _get_fallback_response(message: str) -> str:
    return (
        "I'm your NovaCart Product Specialist! I can help you with product details, "
        "specifications, availability, and comparisons across leading brands like Apple, "
        "Samsung, OnePlus, Motorola, Dell, HP, ASUS, Sony, Boat, and more. "
        "Could you tell me more about what you're looking for? "
        "I'd love to help you find the perfect product!"
    )
