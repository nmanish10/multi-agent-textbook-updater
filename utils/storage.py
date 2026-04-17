import json
import os
from datetime import datetime


# -------------------------
# SAFE SERIALIZER (IMPROVED)
# -------------------------
def safe_serialize(obj):
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)


# -------------------------
# BUILD METADATA
# -------------------------
def build_metadata(data):
    if isinstance(data, list):
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "num_chapters": None,
            "num_updates": len(data)
        }

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "num_chapters": len(data.get("chapters", [])) if isinstance(data, dict) else None,
        "num_updates": len(data.get("updates", [])) if isinstance(data, dict) else None
    }


# -------------------------
# VERSIONED FILE NAME
# -------------------------
def get_versioned_filename(base_path):
    if not os.path.exists(base_path):
        return base_path

    name, ext = os.path.splitext(base_path)

    i = 1
    while True:
        new_path = f"{name}_v{i}{ext}"
        if not os.path.exists(new_path):
            return new_path
        i += 1


# -------------------------
# MAIN SAVE FUNCTION
# -------------------------
def save_results(
    data,
    filename="outputs/results.json",
    pretty=True,
    versioning=True,
    include_metadata=True
):
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # -------------------------
        # ADD METADATA
        # -------------------------
        if include_metadata:
            data = {
                "metadata": build_metadata(data),
                "data": data
            }

        # -------------------------
        # VERSION CONTROL
        # -------------------------
        if versioning:
            filename = get_versioned_filename(filename)

        # -------------------------
        # SAVE FILE
        # -------------------------
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=4 if pretty else None,
                ensure_ascii=False,
                default=safe_serialize
            )

        print(f"💾 Results saved to {filename}")

    except Exception as e:
        print(f"❌ Failed to save results: {str(e)}")


# -------------------------
# LOAD FUNCTION (NEW)
# -------------------------
def load_results(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load results: {str(e)}")
        return None
