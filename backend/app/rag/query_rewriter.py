import logging


from app.rag.llm import LLMResult, generate

logger = logging.getLogger(__name__)


REWRITE_SYSTEM = (
    "You rewrite a user's question into one standalone search query for a document "
    "knowledge base. Resolve pronouns using the chat history. Keep the important topic "
    "keywords, but drop words that refer to the file itself such as 'document', 'PDF', "
    "'file' or 'uploaded'. Output only the query, nothing else."
)


async def rewrite_query(
    question: str, history: list[tuple[str, str]]
) -> tuple[str, LLMResult | None]:
    history_text = "\n".join(f"User: {q}\nAssistant: {a}" for q, a in history[-3:])
    prompt = (
        f"Chat history:\n{history_text or '(none)'}\n\n"
        f"Question: {question}\n\nStandalone search query:"
    )
    try:
        result = await generate(prompt, system=REWRITE_SYSTEM)
        rewritten = result.text.strip().strip('"')
        return (rewritten or question), result
    except Exception:
        logger.warning("Query rewrite failed, using original question", exc_info=True)
        return question, None