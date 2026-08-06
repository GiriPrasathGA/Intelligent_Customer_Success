"""
NovaCart — Supervisor Agent

Coordinates specialized customer success sub-agents (Order, Support, Billing,
Product, Account, Warranty, Human Escalation) using a router LLM.
Determines intent, routes to the appropriate specialist, and synthesizes final response.
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the NovaCart AI Supervisor Agent — the intelligent orchestrator of a world-class e-commerce customer support system.

Your responsibilities:
1. Deeply understand what the customer is asking
2. Identify the primary intent and secondary intents
3. Maintain context from previous messages
4. Determine which specialist agent should handle this

Available specialist agents:
- product_agent: Products, specifications, availability, comparison, recommendations
- order_agent: Order tracking, shipping status, delivery, cancellation
- billing_agent: Payments, refunds, invoices, coupons, discounts, EMI
- warranty_agent: Warranty claims, repairs, replacements, NovaCartCare+
- account_agent: Login, password reset, profile, addresses, account management
- support_agent: Technical troubleshooting, product issues, error codes
- human_agent: Escalations, fraud, legal complaints, complex unresolved issues

Rules:
- Respond ONLY with the agent name in lowercase, nothing else
- If the question spans multiple agents, pick the PRIMARY one
- If unsure or general greeting, pick "support_agent"
- If customer is angry, frustrated, or requesting a human: "human_agent"
- For fraud/legal: ALWAYS "human_agent"

Examples:
User: "Where is my order?" → order_agent
User: "What's the best phone under 50000?" → product_agent
User: "My payment was deducted twice" → billing_agent
User: "Warranty claim for my broken screen" → warranty_agent
User: "I forgot my password" → account_agent
User: "My laptop won't turn on" → support_agent
User: "I want to speak to a manager, this is fraud!" → human_agent"""


from backend.utils.retry import async_retry

@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def _call_supervisor_llm(client: AsyncOpenAI, messages: list[dict[str, str]]) -> str:
    response = await client.chat.completions.create(
        model=settings.effective_chat_model,
        messages=messages,
        temperature=0.1,    # Low temperature for deterministic routing
        max_tokens=20,
    )
    return response.choices[0].message.content.strip().lower()


async def supervisor_route(
    message: str,
    conversation_history: list[dict[str, str]],
) -> str:
    """
    Analyze the user message and route to the appropriate specialist agent.
    Retries LLM completion up to 3 times before using keyword fallback.
    """
    client = AsyncOpenAI(**settings.openai_client_kwargs)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Include last few turns of conversation history for context
    for turn in conversation_history[-6:]:
        messages.append(turn)

    messages.append({"role": "user", "content": f"Route this message: {message}"})

    try:
        agent_name = await _call_supervisor_llm(client, messages)

        # Validate agent name
        valid_agents = {
            "product_agent", "order_agent", "billing_agent",
            "warranty_agent", "account_agent", "support_agent", "human_agent"
        }
        if agent_name not in valid_agents:
            agent_name = "support_agent"  # safe default

        logger.info("Supervisor routed to: %s for message: '%s'", agent_name, message[:50])
        return agent_name

    except Exception as e:
        logger.warning("Supervisor routing error (%s) — using keyword fallback", str(e))
        return _keyword_fallback_routing(message)



def _keyword_fallback_routing(message: str) -> str:
    """Keyword-based routing fallback when LLM is unavailable."""
    from backend.config.settings import AGENT_ROUTING_KEYWORDS

    message_lower = message.lower()
    scores: dict[str, int] = {}

    for agent, keywords in AGENT_ROUTING_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message_lower)
        if score > 0:
            scores[agent] = score

    if not scores:
        return "support_agent"

    return max(scores, key=lambda k: scores[k])
