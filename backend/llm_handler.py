import os
import json
import base64

import litellm
from dotenv import load_dotenv
from json_repair import repair_json

litellm.drop_params = True


class LLMHandler:
    """
    Universal LLM handler powered by LiteLLM.

    Works with any provider LiteLLM supports — set LLM_MODEL in .env to switch:

        Gemini      ->  LLM_MODEL=gemini/gemini-2.0-flash      + GEMINI_API_KEY
        Claude      ->  LLM_MODEL=claude-opus-4-7               + ANTHROPIC_API_KEY
        OpenAI      ->  LLM_MODEL=gpt-4o                        + OPENAI_API_KEY
        Ollama      ->  LLM_MODEL=ollama/llava                  (no key, runs locally)
        NVIDIA NIM  ->  LLM_MODEL=nvidia_nim/meta/llama-3.2-90b-vision-instruct + NVIDIA_NIM_API_KEY
        Groq        ->  LLM_MODEL=groq/llama-3.2-90b-vision-preview             + GROQ_API_KEY
    """

    def __init__(self):
        load_dotenv()
        self.model = os.getenv("LLM_MODEL")
        if not self.model:
            raise RuntimeError(
                "LLM_MODEL is not set in .env.\n"
                "Example: LLM_MODEL=gemini/gemini-2.0-flash"
            )

    def generate(self, prompt: str, image_bytes: bytes = None) -> tuple[str, dict]:
        """
        Send a prompt (optionally with an image) and return
        (response_text, usage_stats).

        usage_stats keys: input_tokens, output_tokens, cost_usd, model
        """
        content = []

        if image_bytes:
            b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })

        content.append({"type": "text", "text": prompt})

        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
        )

        try:
            cost_usd = litellm.completion_cost(completion_response=response) or 0.0
        except Exception:
            cost_usd = 0.0

        usage = {
            "input_tokens":  getattr(response.usage, "prompt_tokens",     0),
            "output_tokens": getattr(response.usage, "completion_tokens",  0),
            "cost_usd":      cost_usd,
            "model":         self.model,
        }

        return response.choices[0].message.content, usage

    def generate_json(self, prompt: str, image_bytes: bytes = None) -> tuple[dict, dict]:
        """Send a prompt and return (parsed_dict, usage_stats)."""
        text, usage = self.generate(prompt, image_bytes)
        return self._parse_json(text), usage

    def _parse_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(repair_json(text[start:end + 1]))
            raise
