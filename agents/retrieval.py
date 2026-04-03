import requests
import time


# -------------------------
# SEMANTIC SCHOLAR SEARCH
# -------------------------
def search_semantic_scholar(query):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"

    params = {
        "query": query,
        "limit": 3,
        "fields": "title,year,authors,url,abstract"
    }

    try:
        # 🔥 small delay to reduce rate limiting
        time.sleep(1)

        response = requests.get(url, params=params, timeout=10)

        print("🔍 Academic Query:", query)
        print("Status:", response.status_code)

        # ❗ If rate limited, just skip (no retry, no fallback)
        if response.status_code == 429:
            print("⏳ Rate limited. Skipping academic results.")
            return []

        if response.status_code != 200:
            print("❌ API failed")
            return []

        data = response.json()

        if not data.get("data"):
            print("⚠️ No academic results found")
            return []

        results = []

        for paper in data.get("data", []):
            summary = paper.get("abstract")

            if not summary:
                summary = "No abstract available"

            results.append({
                "title": paper.get("title"),
                "summary": summary,
                "source": "Semantic Scholar",
                "source_type": "paper",
                "date": paper.get("year"),
                "url": paper.get("url")
            })

        return results

    except Exception as e:
        print("⚠️ Error in Semantic Scholar:", str(e))
        return []


# -------------------------
# WEB SEARCH
# -------------------------
def search_web(query):
    return [
        {
            "title": f"Web result for {query}",
            "summary": f"Summary about {query}",
            "source": "Web",
            "source_type": "web",
            "date": "2024",
            "url": f"https://www.google.com/search?q={query.replace(' ', '+')}"
        }
    ]


# -------------------------
# COMBINED RETRIEVAL
# -------------------------
def retrieve_all(query):
    # ✅ Try academic once (no fallback)
    academic = search_semantic_scholar(query)

    # ✅ Always include web results
    web = search_web(query)

    return academic + web