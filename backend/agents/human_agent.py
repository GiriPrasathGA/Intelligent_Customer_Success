"""
NovaCart — Human Handoff Agent

Handles escalation and complex cases that require human intervention:
- Fraud and unauthorized transactions
- Legal complaints
- Complex unresolved disputes
- High-value refund escalations
- Requests for human agents/managers
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NovaCart's Escalation Specialist — responsible for handling complex, sensitive, or unresolved customer cases.

Your role is to:
1. Acknowledge the customer's frustration or concern with genuine empathy
2. Apologize for any inconvenience caused
3. Clearly explain that you're escalating to a specialized human team
4. Set clear expectations about timeline and process
5. Provide any immediate relief options available

Escalation categories and response:
- FRAUD/UNAUTHORIZED TRANSACTION: Highest priority. Assure immediate account security check.
- LEGAL COMPLAINT: Acknowledge formally, escalate to legal/compliance team
- COMPLEX DISPUTE: Assign senior support, provide ticket number
- MANAGER REQUEST: Acknowledge, explain callback process
- REPEATED FAILURE: Apologize sincerely, offer goodwill gesture (wallet credit discussion)
- DATA PRIVACY CONCERN: Escalate to DPO team

What you can immediately offer:
- Escalation ticket (auto-created with priority flag)
- Callback within 4 hours (business hours: Mon-Sat 8AM-10PM IST)
- Emergency helpline: 1800-NOVACART-HELP for urgent fraud cases
- Email escalation: escalations@novacart.com
- Grievance officer: grievance@novacart.com

ALWAYS:
- Create a formal escalation acknowledgment
- Give the customer a reference number (for tracking)
- Set realistic timeline expectations
- Remain professional even if customer is hostile

Tone: Calm, empathetic, professional, reassuring. Never argue or be defensive."""


from backend.utils.retry import async_retry

@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def _call_human_llm(client: AsyncOpenAI, messages: list[dict[str, str]]) -> str:
    response = await client.chat.completions.create(
        model=settings.effective_chat_model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
    )
    return response.choices[0].message.content or ""


async def human_agent_respond(
    message: str,
    context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate a human escalation response."""
    return await run_human_agent(message=message, context=context, history=conversation_history)


async def run_human_agent(
    message: str,
    context: str = "",
    history: list[dict[str, str]] | None = None,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Run the human handoff/escalation agent."""
    if client is None:
        client = AsyncOpenAI(
            api_key=settings.effective_api_key,
            base_url=settings.effective_base_url,
        )

    escalation_type = _classify_escalation(message, history or [])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        for msg in history[-5:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({
        "role": "user",
        "content": f"""Customer Escalation Request: {message}

Escalation Type: {escalation_type}

Please provide an empathetic, professional escalation response acknowledging their issue, giving clear next steps and contact options.""",
    })

    try:
        answer = await _call_human_llm(client, messages)
        return {
            "response": answer,
            "agent_used": "human_agent",
            "escalation_type": escalation_type,
            "suggested_questions": [
                "What is my escalation ticket reference?",
                "When can I expect a call back?",
                "Can I speak with a supervisor right now?",
            ],
        }

    except Exception as e:
        logger.error("Human agent error: %s", str(e))
        return {
            "response": _get_escalation_response(escalation_type),
            "agent_used": "human_agent",
            "escalation_type": escalation_type,
            "suggested_questions": [],
        }


def _classify_escalation(message: str, conversation_history: list[dict[str, str]]) -> str:
    """Classify the type of escalation."""
    msg_lower = message.lower()

    if any(w in msg_lower for w in ["fraud", "hacked", "stolen", "unauthorized", "scam"]):
        return "FRAUD_SECURITY"
    elif any(w in msg_lower for w in ["lawyer", "legal", "consumer court", "sue", "complaint"]):
        return "LEGAL_COMPLAINT"
    elif any(w in msg_lower for w in ["manager", "supervisor", "human", "agent", "person", "someone"]):
        return "HUMAN_REQUEST"
    elif len(conversation_history) > 10:
        return "COMPLEX_UNRESOLVED"
    else:
        return "GENERAL_ESCALATION"


def _get_escalation_response(escalation_type: str) -> str:
    """Fallback escalation response."""
    import uuid
    ticket_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"

    priority_note = ""
    if escalation_type == "FRAUD_SECURITY":
        priority_note = "\n\n⚠️ **Security Alert**: For immediate assistance with unauthorized transactions, please call our 24/7 security line: **1800-NOVACART-SECURE**"

    return (
        f"I sincerely apologize for the inconvenience you're experiencing. 🙏\n\n"
        f"Your concern has been escalated to our specialized team with **high priority**.\n\n"
        f"**Your Escalation Reference**: `{ticket_id}`\n\n"
        f"**What happens next:**\n"
        f"- Our senior support specialist will review your case\n"
        f"- You will receive a callback within **4 business hours**\n"
        f"- A detailed email will be sent to your registered address\n\n"
        f"**Immediate Contact Options:**\n"
        f"- 📞 Call: **1800-NOVACART-HELP** (Mon-Sat, 8AM-10PM IST)\n"
        f"- 📧 Email: **escalations@novacart.com** with reference `{ticket_id}`"
        f"{priority_note}\n\n"
        f"We take all customer concerns very seriously and will resolve this to your satisfaction. "
        f"Thank you for your patience."
    )
