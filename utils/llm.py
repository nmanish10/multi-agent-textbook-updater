import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MISTRAL_API_KEY")

if not API_KEY:
    raise ValueError("MISTRAL_API_KEY not found in .env")

MISTRAL_API_URL = os.environ.get(
    "MISTRAL_API_URL",
    "https://api.mistral.ai/v1/chat/completions"
)

MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-large-latest")

_DEFAULT_MODEL_CHAIN = [
    MISTRAL_MODEL,
    "open-mistral-nemo",
    "mistral-small-latest"
]

MODEL_CHAIN = []
for m in _DEFAULT_MODEL_CHAIN:
    if m and m not in MODEL_CHAIN:
        MODEL_CHAIN.append(m)


# -------------------------
# CALL WITH FALLBACK
# -------------------------
def call_mistral(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    for model in MODEL_CHAIN:
        try:
            print(f"🔁 Trying model: {model}")

            data = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }

            response = requests.post(
                MISTRAL_API_URL,
                headers=headers,
                json=data,
                timeout=20
            )

            if response.status_code != 200:
                print(f"❌ {model} failed: {response.status_code}")
                continue

            result = response.json()

            content = result["choices"][0]["message"]["content"]

            if content:
                print(f"✅ Success with {model}")
                return content

        except Exception as e:
            print(f"⚠️ Error with {model}: {str(e)}")
            continue

    raise Exception("❌ All models failed")