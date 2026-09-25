from google import genai
from app.config import settings
import random
import time
from google.genai import errors, types

client = genai.Client(api_key=settings.gemini_api_key)

_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3

def generate_with_retry(prompt: str, *, temperature: float, max_output_tokens: int) -> str:
    """Call Gemini's text model with a couple of retries. Returns the text, "" if the model said nothing."""
    config = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_output_tokens)
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=settings.gemini_generation_model, contents=prompt, config=config
            )
            return (response.text or "").strip()
        except errors.APIError as exc:
            if exc.code not in _RETRYABLE_CODES or attempt == _MAX_ATTEMPTS:
                raise
            time.sleep(min(2 ** attempt, 10) + random.random())