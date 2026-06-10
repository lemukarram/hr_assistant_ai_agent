"""
HR Assistant Agent — LangGraph-based agentic orchestration.

Graph topology:
  START → intent_classifier → security_guard ─┬─► blocked_response → END
                                               └─► rag_retrieval → planner ⇄ tools → END

Security guarantees:
  - employee_id is injected from the JWT before the graph runs; never from user message
  - Security guard blocks prompt injection before any LLM call
  - RAG retrieval runs before the planner so policy answers are grounded
"""
from __future__ import annotations

from typing import AsyncIterator, Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.prompts import build_system_prompt
from app.agents.state import AgentState, make_initial_state
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import check_injection
from app.mcp_tools.client import get_mcp_tools
from app.rag.retriever import HybridRetriever

logger = get_logger(__name__)

# ── Intent classification keywords ───────────────────────────────────────────
# Priority-ordered: first match wins
_INTENT_KEYWORDS: dict[str, list[str]] = {
    "leave_action": [
        "أريد إجازة", "تقديم طلب إجازة", "request leave", "apply for leave",
        "submit leave", "طلب إجازة", "submit a leave",
    ],
    "leave_balance": [
        "رصيد إجازة", "رصيد الإجازة", "إجازة سنوية تبقى", "leave balance",
        "vacation days", "أيام الإجازة", "leave remaining", "annual leave days",
        "رصيد إجازتي", "رصيد إجازاتي", "إجازاتي السنوية", "leave days",
        "how many annual leave", "how many leave",
    ],
    "payslip": [
        "راتب", "قسيمة", "payslip", "salary", "pay slip", "الراتب", "paycheck",
        "كشف الراتب", "last payslip",
    ],
    "org_chart": [
        "مدير", "هيكل", "org chart", "manager", "reports to",
        "من هو مديري", "who is my manager", "direct reports", "org",
    ],
    "benefits": [
        "مزايا", "تأمين", "benefits", "insurance", "health", "صحي",
        "تغطية", "coverage", "health insurance",
    ],
    "policy": [
        "سياسة", "لوائح", "قواعد", "policy", "rules", "regulation",
        "handbook", "دليل", "كيف أتقدم", "procedure",
    ],
    "profile": [
        "بياناتي", "بيانات شخصية", "employee profile", "my profile",
        "personal data", "معلوماتي",
    ],
    "attendance": [
        "حضور", "غياب", "تأخر", "تسجيل الدخول", "attendance", "check-in",
        "check in", "absent", "late", "وقت الحضور", "أوقات الدوام",
        "كم تأخرت", "دوام", "حضوري",
    ],
    "overtime": [
        "عمل إضافي", "ساعات إضافية", "overtime", "extra hours",
        "سجل عمل إضافي", "log overtime", "ساعات العمل الإضافية",
        "عمل بعد الدوام",
    ],
}


def _classify_intent_heuristic(query: str) -> str:
    """
    Keyword-based intent classifier — no LLM call.
    Used by intent_classifier_node and exposed for unit tests.
    """
    text = query.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return intent
    return "general"


# ── Nodes ─────────────────────────────────────────────────────────────────────

def intent_classifier_node(state: AgentState) -> dict:
    """
    Classify query domain and language without an LLM call.
    Saves a full round-trip for simple intent determination.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "general", "language": "ar"}

    last = messages[-1]
    content: str = (
        last.get("content", "") if isinstance(last, dict)
        else getattr(last, "content", "")
    )
    text_lower = content.lower()

    detected_intent = _classify_intent_heuristic(text_lower)

    arabic_chars = sum(1 for c in content if "؀" <= c <= "ۿ")
    total_chars  = max(len(content.replace(" ", "")), 1)
    ratio        = arabic_chars / total_chars
    language     = "ar" if ratio > 0.4 else "en" if ratio < 0.15 else "mixed"

    logger.debug("Intent classified", intent=detected_intent, language=language)
    return {"intent": detected_intent, "language": language}


def security_guard_node(state: AgentState) -> dict:
    """
    Prompt-injection guard — runs before any LLM call.
    Returns security_passed=True when the input is clean.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"security_passed": True, "block_reason": None}

    last = messages[-1]
    content: str = (
        last.get("content", "") if isinstance(last, dict)
        else getattr(last, "content", "")
    )

    result = check_injection(content)
    if result.is_injection:
        logger.warning(
            "Prompt injection blocked",
            employee_id=state.get("employee_id"),
            matched_pattern=result.matched_pattern,
        )
        return {"security_passed": False, "block_reason": "security_violation"}

    return {"security_passed": True, "block_reason": None}


def _security_router(state: AgentState) -> Literal["rag_retrieval", "blocked_response"]:
    """Route based on the result of the security guard node."""
    return "blocked_response" if not state.get("security_passed", True) else "rag_retrieval"


def blocked_response_node(state: AgentState) -> dict:
    """Emit a localised refusal and terminate the graph."""
    language = state.get("language", "ar")
    if language == "en":
        msg = (
            "I'm sorry, I cannot process this request. "
            "Please ensure your question is related to your own HR matters."
        )
    else:
        msg = (
            "عذراً، لا يمكنني معالجة هذا الطلب. "
            "يُرجى التأكد من أن سؤالك يتعلق بشؤون الموارد البشرية الخاصة بك."
        )
    return {
        "messages": list(state.get("messages", [])) + [AIMessage(content=msg)],
        "response": msg,
    }


async def rag_retrieval_node(state: AgentState, retriever: HybridRetriever) -> dict:
    """
    Retrieve relevant handbook chunks before the planner LLM call.
    Only runs for policy/benefits/leave intents to avoid unnecessary latency.
    """
    if state.get("intent") not in ("policy", "leave_action", "benefits", "leave_balance", "overtime", "attendance"):
        return {}

    messages = state.get("messages", [])
    if not messages:
        return {}

    last = messages[-1]
    query: str = (
        last.get("content", "") if isinstance(last, dict)
        else getattr(last, "content", "")
    )

    try:
        chunks = await retriever.retrieve(query, top_k=settings.RAG_TOP_K_RERANK)
        logger.debug("RAG retrieved", count=len(chunks), intent=state.get("intent"))
        return {"retrieved_context": chunks}
    except Exception as exc:
        logger.warning("RAG retrieval failed — continuing without context", error=str(exc))
        return {"retrieved_context": []}


async def planner_node(state: AgentState, llm_with_tools) -> dict:
    """
    Core ReAct planner.  The LLM sees the system prompt (with employee_id injected),
    the conversation history, and — if available — pre-retrieved policy context.
    """
    system_prompt = build_system_prompt(
        employee_id=state["employee_id"],
        language=state.get("language", "ar"),
        intent=state.get("intent", "general"),
    )

    messages: list = [SystemMessage(content=system_prompt)] + list(state.get("messages", []))

    # Augment the last user message with RAG context when available
    retrieved = state.get("retrieved_context") or []
    if retrieved and messages:
        rag_block = _format_rag_context(retrieved)
        last_msg = messages[-1]
        last_content: str = (
            last_msg.get("content", "") if isinstance(last_msg, dict)
            else getattr(last_msg, "content", "")
        )
        messages = messages[:-1] + [
            HumanMessage(content=f"{last_content}\n\n[سياق من دليل الموارد البشرية]\n{rag_block}")
        ]

    response = await llm_with_tools.ainvoke(messages)
    return {"messages": list(state.get("messages", [])) + [response]}


def _format_rag_context(chunks: list[dict]) -> str:
    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        meta    = chunk.get("metadata", {})
        section = meta.get("section", "غير محدد")
        page    = meta.get("page", "?")
        score   = chunk.get("rerank_score", chunk.get("score", 0.0))
        parts.append(
            f"[{i}] القسم: {section} (صفحة {page}) — الصلة: {score:.2f}\n{chunk['text']}"
        )
    return "\n\n".join(parts)


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_agent_graph(retriever: HybridRetriever):
    """Compile the LangGraph state machine. Called once at startup."""
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=120,
    )

    mcp_tools       = get_mcp_tools()
    llm_with_tools  = llm.bind_tools(mcp_tools)

    async def planner(state: AgentState) -> dict:
        return await planner_node(state, llm_with_tools)

    async def rag_retrieval(state: AgentState) -> dict:
        return await rag_retrieval_node(state, retriever)

    def should_use_tools(state: AgentState) -> Literal["tools", "__end__"]:
        messages = state.get("messages", [])
        if not messages:
            return END
        last = messages[-1]
        tool_calls = getattr(last, "tool_calls", None)
        return "tools" if tool_calls else END

    graph = StateGraph(AgentState)

    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("security_guard",    security_guard_node)
    graph.add_node("blocked_response",  blocked_response_node)
    graph.add_node("rag_retrieval",     rag_retrieval)
    graph.add_node("planner",           planner)
    graph.add_node("tools",             ToolNode(mcp_tools))

    graph.add_edge(START, "intent_classifier")
    graph.add_edge("intent_classifier", "security_guard")
    graph.add_conditional_edges(
        "security_guard",
        _security_router,
        {"rag_retrieval": "rag_retrieval", "blocked_response": "blocked_response"},
    )
    graph.add_edge("rag_retrieval", "planner")
    graph.add_conditional_edges("planner", should_use_tools, {"tools": "tools", END: END})
    graph.add_edge("tools", "planner")   # ReAct loop
    graph.add_edge("blocked_response", END)

    return graph.compile()


# ── Public interface ──────────────────────────────────────────────────────────

class HRAssistantAgent:
    """
    High-level agent interface consumed by the API layer.
    The compiled graph is a singleton per process.
    """

    def __init__(self) -> None:
        self._retriever = HybridRetriever()
        self._graph     = build_agent_graph(self._retriever)

    async def chat_stream(
        self,
        message: str,
        employee_id: str,
        session_id: str,
        history: list[dict],
    ) -> AsyncIterator[str]:
        """
        Yield LLM response tokens one at a time.
        employee_id MUST come from the validated JWT — never from the message body.
        """
        initial = make_initial_state(employee_id=employee_id, session_id=session_id)
        initial["messages"] = _build_history(history) + [HumanMessage(content=message)]

        async for event in self._graph.astream_events(initial, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield chunk.content

    async def chat(
        self,
        message: str,
        employee_id: str,
        session_id: str,
        history: list[dict],
    ) -> dict:
        """Non-streaming chat — used for testing and fallback clients."""
        initial = make_initial_state(employee_id=employee_id, session_id=session_id)
        initial["messages"] = _build_history(history) + [HumanMessage(content=message)]

        result    = await self._graph.ainvoke(initial)
        messages  = result.get("messages", [])
        last_msg  = messages[-1] if messages else None
        text      = getattr(last_msg, "content", "") if last_msg else ""
        tool_calls = getattr(last_msg, "tool_calls", []) if last_msg else []

        return {
            "text":             text,
            "tools_used":       [tc["name"] for tc in (tool_calls or [])],
            "was_blocked":      not result.get("security_passed", True),
            "retrieved_chunks": result.get("retrieved_context", []),
        }


def _build_history(history: list[dict]) -> list[BaseMessage]:
    """Convert raw history dicts to LangChain message objects."""
    out: list[BaseMessage] = []
    for msg in history:
        role    = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
    return out
