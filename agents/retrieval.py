import requests
import re
from bs4 import BeautifulSoup


# -------------------------
# OPENALEX SEARCH (MAIN)
# -------------------------
def search_openalex(query):
    url = "https://api.openalex.org/works"

    params = {
        "search": query,
        "per-page": 3
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            print("❌ OpenAlex failed")
            return []

        data = response.json()
        results = []

        for item in data.get("results", []):
            # Convert abstract if exists
            abstract = item.get("abstract_inverted_index")

            summary = "No abstract available"
            if abstract:
                try:
                    words = []
                    for word, positions in abstract.items():
                        for pos in positions:
                            words.append((pos, word))
                    words = sorted(words)
                    summary = " ".join([w[1] for w in words])
                except:
                    summary = str(abstract)

            results.append({
                "title": item.get("title"),
                "summary": summary,
                "source": "OpenAlex",
                "source_type": "paper",
                "date": item.get("publication_year"),
                "url": item.get("id")
            })

        print("✅ OpenAlex results:", len(results))
        return results

    except Exception as e:
        print("⚠️ OpenAlex error:", str(e))
        return []


# -------------------------
# ARXIV SEARCH (LATEST)
# -------------------------
def search_arxiv(query):
    url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results=3"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print("❌ arXiv failed")
            return []

        entries = response.text.split("<entry>")[1:]
        results = []

        for entry in entries:
            title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            link = re.search(r"<id>(.*?)</id>", entry)
            date = re.search(r"<published>(.*?)</published>", entry)

            results.append({
                "title": title.group(1).strip() if title else "",
                "summary": summary.group(1).strip() if summary else "",
                "source": "arXiv",
                "source_type": "preprint",
                "date": date.group(1)[:10] if date else "",
                "url": link.group(1) if link else ""
            })

        print("✅ arXiv results:", len(results))
        return results

    except Exception as e:
        print("⚠️ arXiv error:", str(e))
        return []


# -------------------------
# WEB SEARCH (DUCKDUCKGO)
# -------------------------
def search_web(query):
    url = "https://html.duckduckgo.com/html/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }

    data = {
        "q": query
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)

        if response.status_code != 200:
            print("❌ Web search failed:", response.status_code)
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        results = []

        for result in soup.select(".result")[:3]:
            title_tag = result.select_one(".result__title")
            snippet_tag = result.select_one(".result__snippet")
            link_tag = result.select_one("a.result__a")

            title = title_tag.get_text(strip=True) if title_tag else ""
            summary = snippet_tag.get_text(strip=True) if snippet_tag else ""
            link = link_tag["href"] if link_tag else ""

            results.append({
                "title": title,
                "summary": summary,
                "source": "Web",
                "source_type": "web",
                "date": "",
                "url": link
            })

        print("✅ Web results:", len(results))
        return results

    except Exception as e:
        print("⚠️ Web search error:", str(e))
        return []


# -------------------------
# COMBINED RETRIEVAL
# -------------------------
def retrieve_all(query):
    print("\n🔍 Searching:", query)

    results = []

    # Academic sources
    results += search_openalex(query)
    results += search_arxiv(query)

    # Web fallback
    results += search_web(query)

    return results