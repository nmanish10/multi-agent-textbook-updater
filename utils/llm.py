import json
import os
import re
import time

import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from diskcache import Cache


load_dotenv()

API_KEY = os.getenv("MISTRAL_API_KEY")
if not API_KEY:
    raise ValueError("MISTRAL_API_KEY not found in .env")

cache = Cache(os.path.join(os.path.dirname(__file__), "..", ".llm_cache"))

MISTRAL_API_URL = os.environ.get(
    "MISTRAL_API_URL",
    "https://api.mistral.ai/v1/chat/completions",
)
MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-large-latest")

_DEFAULT_MODEL_CHAIN = [
    MISTRAL_MODEL,
    "open-mistral-nemo",
    "mistral-small-latest",
]

MODEL_CHAIN = []
for model_name in _DEFAULT_MODEL_CHAIN:
    if model_name and model_name not in MODEL_CHAIN:
        MODEL_CHAIN.append(model_name)

_PROMPT_TRACES = []


def reset_prompt_traces():
    _PROMPT_TRACES.clear()


def get_prompt_traces():
    return list(_PROMPT_TRACES)


def record_prompt_trace(
    prompt_name,
    prompt_version,
    structured,
    temperature,
    used_system_prompt,
    cache_hit,
):
    _PROMPT_TRACES.append(
        {
            "prompt_name": prompt_name or "unspecified",
            "prompt_version": prompt_version or "unversioned",
            "model_chain": list(MODEL_CHAIN),
            "structured": structured,
            "temperature": temperature,
            "used_system_prompt": used_system_prompt,
            "cache_hit": cache_hit,
        }
    )


def clean_response(text):
    if not text:
        return ""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"```.*?\n", "", text, flags=re.DOTALL)
        text = text.replace("```", "").strip()
    return text.strip()


def is_valid_response(content):
    return bool(content and len(content.strip()) >= 10)


def get_temperature(prompt):
    prompt_lower = prompt.lower()
    if "json" in prompt_lower:
        return 0.1
    if "academic" in prompt_lower or "write" in prompt_lower:
        return 0.3
    return 0.2


def call_mistral(
    prompt,
    system_prompt=None,
    max_retries=2,
    prompt_name=None,
    prompt_version=None,
):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    temperature = get_temperature(prompt)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    cache_key = f"{prompt}_{system_prompt}"
    if cache_key in cache:
        print("⚡ Cache hit for Mistral API call")
        record_prompt_trace(prompt_name, prompt_version, False, temperature, bool(system_prompt), True)
        return cache[cache_key]

    record_prompt_trace(prompt_name, prompt_version, False, temperature, bool(system_prompt), False)

    for model in MODEL_CHAIN:
        for attempt in range(max_retries + 1):
            try:
                print(f"🔁 {model} | attempt {attempt + 1}")
                data = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                response = requests.post(
                    MISTRAL_API_URL,
                    headers=headers,
                    json=data,
                    timeout=30,
                )

                if response.status_code == 429:
                    wait = 2 * (attempt + 1)
                    print(f"⏳ Rate limited. Waiting {wait}s")
                    time.sleep(wait)
                    continue

                if response.status_code != 200:
                    print(f"ERROR: {model} failed: {response.status_code}")
                    time.sleep(1.5 * (attempt + 1))
                    continue

                result = response.json()
                content = (
                    result.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                content = clean_response(content)
                if is_valid_response(content):
                    print(f"SUCCESS: {model}")
                    cache[cache_key] = content
                    return content

                print(f"WARNING: Weak response from {model}")
            except requests.exceptions.Timeout:
                print(f"WARNING: Timeout: {model}")
            except Exception as e:
                print(f"WARNING: Error: {model} -> {str(e)}")

            time.sleep(1.5 * (attempt + 1))

    raise Exception("ERROR: All models failed after retries")


def call_mistral_structured(
    prompt: str,
    pydantic_schema,
    system_prompt=None,
    max_retries=3,
    prompt_name=None,
    prompt_version=None,
):
    schema_json = pydantic_schema.model_json_schema()
    struct_sys_prompt = system_prompt or "You are a helpful assistant."
    struct_sys_prompt += (
        "\n\nYou MUST return raw JSON ONLY. Do not write markdown blocks or text. "
        f"Your JSON must abide by this strict schema:\n{json.dumps(schema_json)}"
    )

    temperature = get_temperature(prompt)
    record_prompt_trace(prompt_name, prompt_version, True, temperature, True, False)

    for attempt in range(max_retries):
        result_text = call_mistral(
            prompt,
            system_prompt=struct_sys_prompt,
            max_retries=1,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
        )
        try:
            result_json = json.loads(result_text)
            return pydantic_schema.model_validate(result_json)
        except json.JSONDecodeError:
            print(f"WARNING: JSON parsing failed (attempt {attempt + 1})")
        except ValidationError as e:
            print(f"WARNING: Pydantic validation failed (attempt {attempt + 1}): {e}")

    raise Exception(f"ERROR: Structured parsing failed for schema {pydantic_schema.__name__}")
