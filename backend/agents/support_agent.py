"""
NovaCart — Support Agent

Handles technical troubleshooting and general support:
- Product technical issues
- App and website problems
- Error codes
- Setup assistance
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NovaCart's Technical Support Specialist — an expert troubleshooter for NovaCart products, devices, and online store services.

Your expertise:
- Smartphone troubleshooting: charging issues, battery drain, camera, overheating, connectivity, OS issues
- Laptop issues: startup problems, BSOD, keyboard/trackpad, thermal throttling, WiFi/Bluetooth
- Audio device pairing, ANC issues, and latency
- NovaCart app/website issues: login, checkout, payment errors, cart sync
- Error codes: E001-E008 system errors and their solutions
- Setup assistance for new gadgets and electronics

Troubleshooting approach:
1. Acknowledge the issue with empathy
2. Ask clarifying questions if needed (device model, brand, OS version)
3. Provide step-by-step solutions (numbered, clear)
4. Start with simplest solutions (restart, clear cache, power cycle)
5. Escalate to authorized brand warranty/service center if hardware defect is confirmed

Error code reference:
E001: Payment timeout → Retry
E002: Stock sold out during checkout → Search alternatives
E003: Address verification failed → Update profile address
E004: Session expired → Re-login
E005: API error → Wait 5 min, retry
E006: OTP delivery failed → Check signal, request resend
E007: Invalid coupon → Check code and eligibility
E008: Pincode not serviceable → Product doesn't ship to location

Tone: Patient, methodical, clear. Technical issues can be frustrating — be extra empathetic.
Always confirm if the suggested solution worked before closing the conversation."""


from backend.utils.retry import async_retry

@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def _call_support_llm(client: AsyncOpenAI, messages: list[dict[str, str]]) -> str:
    response = await client.chat.completions.create(
        model=settings.effective_chat_model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
    )
    return response.choices[0].message.content or ""


async def support_agent_respond(
    message: str,
    context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate a technical support response using RAG context."""
    return await run_support_agent(message=message, context=context, history=conversation_history)


async def run_support_agent(
    message: str,
    context: str = "",
    history: list[dict[str, str]] | None = None,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Run the support agent."""
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
        user_content = f"""NovaCart Troubleshooting Knowledge:
{context}

Customer Issue: {message}

Provide step-by-step troubleshooting guidance. Start simple, escalate if needed."""

    messages.append({"role": "user", "content": user_content})

    try:
        answer = await _call_support_llm(client, messages)
        suggested = _get_support_suggestions(message)

        return {
            "response": answer,
            "agent_used": "support_agent",
            "suggested_questions": suggested,
        }

    except Exception as e:
        logger.error("Support agent error: %s", str(e))
        return {
            "response": _get_fallback_response(),
            "agent_used": "support_agent",
            "suggested_questions": _get_support_suggestions(message),
        }


def _get_support_suggestions(message: str) -> list[str]:
    message_lower = message.lower()
    if any(w in message_lower for w in ["app", "website", "site"]):
        return [
            "Try clearing your browser cache and cookies",
            "Is the issue happening on mobile or desktop?",
            "Have you tried a different browser?",
        ]
    elif any(w in message_lower for w in ["phone", "laptop", "device"]):
        return [
            "Is the device still under warranty?",
            "Can you describe when the issue started?",
            "Have you tried restarting the device?",
        ]
    else:
        return [
            "What device or product are you having trouble with?",
            "How long has this issue been occurring?",
            "Would you like to raise a support ticket?",
        ]


def _get_fallback_response() -> str:
    return (
        "I'm your NovaCart Technical Support Specialist! 🔧\n\n"
        "I can help troubleshoot:\n"
        "- **Smartphones & Tablets**: Charging, battery, camera, connectivity\n"
        "- **Laptops**: Startup, performance, display, keyboard issues\n"
        "- **Audio Devices**: Pairing, connectivity, sound quality\n"
        "- **App/Website**: Login, checkout, payment errors\n\n"
        "Please describe your issue in detail and I'll walk you through the solution step by step!"
    )

