"""
Turns a product name + short description into a decent image-generation
prompt.

Uses Groq's free-tier chat completions API when GROQ_API_KEY is set
(Groq is OpenAI-compatible and has a generous free tier, which is why
I picked it over paid-only options). If no key is configured, it falls
back to a rule-based prompt builder so the service still works end to
end without anyone needing to sign up for anything first.
"""
import requests

from config import Config

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a prompt engineer for a product photography AI image generator. "
    "Given a product name and description, write ONE single-paragraph, "
    "highly visual image-generation prompt (35-60 words). Describe the "
    "product, an evocative lifestyle setting, lighting, and camera framing. "
    "Do not add commentary, quotes, or a preamble - reply with only the prompt."
)


def _fallback_prompt(product_name: str, description: str) -> str:
    """Rule-based backup so /generate never hard-fails on the LLM step."""
    return (
        f"Professional lifestyle product photography of {product_name}, "
        f"{description.strip().rstrip('.')}. Natural daylight, shallow "
        f"depth of field, styled on a clean textured surface, shot on a "
        f"85mm lens, warm and inviting color grade, high detail."
    )


def build_generation_prompt(product_name: str, description: str) -> str:
    if not Config.GROQ_API_KEY:
        return _fallback_prompt(product_name, description)

    payload = {
        "model": Config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Product: {product_name}\nDescription: {description}",
            },
        ],
        "temperature": 0.7,
        "max_tokens": 150,
    }
    headers = {"Authorization": f"Bearer {Config.GROQ_API_KEY}"}

    try:
        resp = requests.post(
            GROQ_ENDPOINT, json=payload, headers=headers, timeout=20
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        return content or _fallback_prompt(product_name, description)
    except Exception:
        # LLM being flaky shouldn't take the whole job down - degrade
        # gracefully to the template prompt instead.
        return _fallback_prompt(product_name, description)
