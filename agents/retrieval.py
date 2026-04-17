import asyncio
import re
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer, util


embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


TRUSTED_WEB_DOMAINS = {
    "nature.com": 0.93,
    "science.org": 0.93,
    "springer.com": 0.9,
    "ieee.org": 0.95,
    "acm.org": 0.95,
    "nih.gov": 0.96,
    "nist.gov": 0.98,
    "who.int": 0.98,
    "oecd.org": 0.96,
    "arxiv.org": 0.72,
    "wikipedia.org": 0.55,
}

LOW_SIGNAL_DOMAINS = {
    "medium.com",
    "towardsdatascience.com",
    "linkedin.com",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
}


def generate_queries(query):
    base = simplify_query(query)
    return [
        base,
        f"recent advances in {base}",
        f"{base} machine learning research",
        f"{base} applications and methods",
    ]


def simplify_query(query, max_words=8):
    return " ".join(query.split()[:max_words])


def canonicalize_url(url):
    if not url:
        return ""

    url = url.strip()
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc:
        redirect = parse_qs(parsed.query).get("uddg")
        if redirect:
            url = unquote(redirect[0])
            parsed = urlparse(url)

    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def extract_domain(url):
    canonical = canonicalize_url(url)
    parsed = urlparse(canonical)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def infer_credibility(source_type, url):
    if source_type == "paper":
        return 0.95
    if source_type == "preprint":
        return 0.78

    domain = extract_domain(url)
    if domain in TRUSTED_WEB_DOMAINS:
        return TRUSTED_WEB_DOMAINS[domain]
    if domain in LOW_SIGNAL_DOMAINS:
        return 0.28
    if domain.endswith(".edu") or domain.endswith(".gov"):
        return 0.88
    if domain.endswith(".org"):
        return 0.72
    return 0.45


def normalize_result(item):
    url = canonicalize_url(item.get("url"))
    source_type = item.get("source_type")
    return {
        "title": (item.get("title") or "").strip(),
        "summary": (item.get("summary") or "").strip(),
        "source": item.get("source"),
        "source_name": item.get("source_name") or item.get("source"),
        "source_type": source_type,
        "date": item.get("date"),
        "url": url,
        "domain": extract_domain(url),
        "credibility_score": infer_credibility(source_type, url),
    }


def is_valid_result(item):
    if not (item["title"] and len(item["title"]) > 5 and item["summary"] and len(item["summary"]) > 30):
        return False
    domain = item.get("domain", "")
    if domain in LOW_SIGNAL_DOMAINS:
        return False
    if len(item["summary"].split()) < 8:
        return False
    return True


def compute_relevance(query, result):
    doc_text = result["title"] + " " + result["summary"]
    if not doc_text.strip():
        return 0.0
    target_emb = embedding_model.encode(query, convert_to_tensor=True)
    doc_emb = embedding_model.encode(doc_text, convert_to_tensor=True)
    return util.cos_sim(target_emb, doc_emb)[0][0].item()


def deduplicate_results(results):
    seen = set()
    unique = []
    for result in results:
        key = (
            canonicalize_url(result.get("url"))
            or re.sub(r"\W+", "", (result["title"] + result["summary"]).lower())
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


def score_result(query, result):
    relevance = compute_relevance(query, result)
    credibility = result.get("credibility_score", 0.5)
    score = 0.72 * relevance + 0.28 * credibility
    result["retrieval_score"] = round(score, 4)
    result["semantic_score"] = round(relevance, 4)
    return result


async def search_openalex(query, session: aiohttp.ClientSession):
    url = "https://api.openalex.org/works"
    params = {"search": query, "per-page": 4}
    try:
        async with session.get(url, params=params, timeout=15) as res:
            if res.status != 200:
                return []

            data = await res.json()
            results = []
            for item in data.get("results", []):
                abstract = item.get("abstract_inverted_index")
                summary = ""
                if abstract:
                    try:
                        words = []
                        for word, positions in abstract.items():
                            for pos in positions:
                                words.append((pos, word))
                        words.sort()
                        summary = " ".join(word for _, word in words)
                    except Exception:
                        summary = ""

                doi = item.get("doi") or item.get("id")
                result = normalize_result(
                    {
                        "title": item.get("title"),
                        "summary": summary,
                        "source": "OpenAlex",
                        "source_name": "OpenAlex",
                        "source_type": "paper",
                        "date": item.get("publication_year"),
                        "url": doi,
                    }
                )
                if is_valid_result(result):
                    results.append(result)
            return results
    except Exception:
        return []


async def search_arxiv(query, session: aiohttp.ClientSession):
    url = f"http://export.arxiv.org/api/query?search_query=all:{query}&max_results=4"
    try:
        async with session.get(url, timeout=15) as res:
            if res.status != 200:
                return []

            text_data = await res.text()
            entries = text_data.split("<entry>")[1:]
            results = []
            for entry in entries:
                title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
                link = re.search(r"<id>(.*?)</id>", entry)
                published = re.search(r"<published>(.*?)</published>", entry)
                result = normalize_result(
                    {
                        "title": title.group(1).strip() if title else "",
                        "summary": summary.group(1).strip() if summary else "",
                        "source": "arXiv",
                        "source_name": "arXiv",
                        "source_type": "preprint",
                        "date": (published.group(1)[:10] if published else ""),
                        "url": link.group(1) if link else "",
                    }
                )
                if is_valid_result(result):
                    results.append(result)
            return results
    except Exception:
        return []


async def search_web(query, session: aiohttp.ClientSession):
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with session.post(url, headers=headers, data={"q": query}, timeout=10) as res:
            text_data = await res.text()
            soup = BeautifulSoup(text_data, "html.parser")
            results = []
            for item in soup.select(".result")[:3]:
                title = item.select_one(".result__title")
                snippet = item.select_one(".result__snippet")
                link = item.select_one("a.result__a")
                result = normalize_result(
                    {
                        "title": title.get_text(strip=True) if title else "",
                        "summary": snippet.get_text(strip=True) if snippet else "",
                        "source": "Web",
                        "source_name": extract_domain(link["href"]) if link else "Web",
                        "source_type": "web",
                        "url": link["href"] if link else "",
                    }
                )
                if is_valid_result(result):
                    results.append(result)
            return results
    except Exception:
        return []


async def retrieve_all_async(query):
    queries = generate_queries(query)
    all_results = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for refined_query in queries:
            tasks.append(search_openalex(refined_query, session))
            tasks.append(search_arxiv(refined_query, session))
            tasks.append(search_web(refined_query, session))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for item in gathered:
            if isinstance(item, list):
                all_results.extend(item)
    return all_results


def retrieve_all(query):
    print(f"\nSearching (Concurrent): {query}")
    all_results = asyncio.run(retrieve_all_async(query))
    all_results = deduplicate_results(all_results)
    if not all_results:
        return []

    scored = [score_result(query, result) for result in all_results]
    scored = sorted(
        scored,
        key=lambda item: (item["retrieval_score"], item.get("credibility_score", 0)),
        reverse=True,
    )
    final_results = scored[:8]
    print(f"Total relevant results: {len(final_results)}\n")
    return final_results
