from openai import AsyncOpenAI
from app.core.config import settings

SYSTEM_PROMPT = """You are the AI assistant in an AI chat application.
Be helpful, accurate, concise, and clear. If you are uncertain, say so."""

async def generate_ai_response(prompt: str, history: list[dict[str, str]] | None = None) -> str:
    if not settings.OPENROUTER_API_KEY:
        return "AI service is not configured. Add OPENROUTER_API_KEY to your .env file."

    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": settings.PROJECT_NAME,
        },
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": prompt})
    try:
        response = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=800,
        )
        return (response.choices[0].message.content or "No AI response was returned.").strip()
    finally:
        await client.close()
