import json


def save_results(data, filename="outputs/results.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)