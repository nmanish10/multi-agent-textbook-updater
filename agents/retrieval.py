import asyncio
from datetime import datetime, timezone
import logging
import os
import re
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer, util

from core.logging import get_logger, log_event

logger = get_logger("textbook_updater.retrieval")
embedding_model = None
embedding_model_failed = False
semantic_scholar_semaphore = asyncio.Semaphore(3)
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()


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

OFFICIAL_SOURCE_REGISTRY = {
    "openai": {"label": "OpenAI", "domain": "openai.com", "query_prefix": "site:openai.com", "credibility": 0.98},
    "google_deepmind": {
        "label": "Google DeepMind",
        "domain": "deepmind.google",
        "query_prefix": "site:deepmind.google",
        "credibility": 0.98,
    },
    "meta_ai": {"label": "Meta AI", "domain": "ai.meta.com", "query_prefix": "site:ai.meta.com", "credibility": 0.96},
    "nist": {"label": "NIST", "domain": "nist.gov", "query_prefix": "site:nist.gov", "credibility": 0.98},
    "ieee": {"label": "IEEE", "domain": "ieee.org", "query_prefix": "site:ieee.org", "credibility": 0.96},
}

VENUE_TIERS = {
    "neurips": 0.95,
    "icml": 0.95,
    "iclr": 0.95,
    "nature": 0.95,
    "science": 0.95,
    "aaai": 0.88,
    "emnlp": 0.88,
    "cvpr": 0.88,
    "acl": 0.88,
    "ieee": 0.82,
    "acm": 0.82,
    "arxiv": 0.55,
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


def get_embedding_model():
    global embedding_model, embedding_model_failed
    if embedding_model is not None:
        return embedding_model
    if embedding_model_failed:
        return None
    try:
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as exc:
        embedding_model_failed = True
        log_event(
            logger,
            logging.WARNING,
            "Embedding model unavailable; falling back to lexical relevance",
            error=str(exc),
        )
        return None
    return embedding_model


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
    if source_type == "official_source":
        domain = extract_domain(url)
        for entry in OFFICIAL_SOURCE_REGISTRY.values():
            if domain.endswith(entry["domain"]):
                return entry["credibility"]
        return 0.95
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


def months_since(date_value):
    if not date_value:
        return 12.0
    try:
        if isinstance(date_value, int):
            parsed = datetime(int(date_value), 1, 1, tzinfo=timezone.utc)
        else:
            text = str(date_value).strip()
            parsed = None
            for fmt, length in [("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)]:
                try:
                    parsed = datetime.strptime(text[:length], fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
            if parsed is None:
                return 12.0
        delta_days = max((datetime.now(timezone.utc) - parsed).days, 0)
        return max(delta_days / 30.0, 0.1)
    except Exception:
        return 12.0


def compute_recency_score(date_value):
    return round(max(0.30, 1.0 - (months_since(date_value) / 24.0)), 4)


def compute_citation_velocity(cited_by_count, date_value):
    if not cited_by_count:
        return 0.5
    velocity = float(cited_by_count) / max(months_since(date_value), 0.1)
    return round(min(velocity / 20.0, 1.0), 4)


def infer_venue_score(venue, source_type):
    venue_text = (venue or "").lower()
    for key, score in VENUE_TIERS.items():
        if key in venue_text:
            return score
    if source_type == "official_source":
        return 0.95
    if source_type == "paper":
        return 0.75
    if source_type == "preprint":
        return 0.55
    return 0.5


def infer_author_signal(item):
    explicit_h_index = float(item.get("author_h_index", 0) or 0)
    if explicit_h_index > 0:
        return round(min(explicit_h_index / 50.0, 1.0), 4)
    works_count = float(item.get("author_works_count", 0) or 0)
    cited_by = float(item.get("author_cited_by_count", 0) or 0)
    if works_count <= 0 or cited_by <= 0:
        return 0.5
    pseudo_h_index = (cited_by / max(works_count, 1)) ** 0.5 * 5
    return round(min(pseudo_h_index / 50.0, 1.0), 4)


def source_channel_score(source_type):
    return {
        "peer_reviewed_journal": 0.92,
        "conference_paper": 0.90,
        "official_source": 0.95,
        "paper": 0.90,
        "preprint": 0.60,
        "web": 0.40,
    }.get(source_type, 0.50)


def compute_credibility(item):
    source_type = item.get("source_type", "")
    url = item.get("url", "")
    venue_score = infer_venue_score(item.get("venue", ""), source_type)
    author_signal = infer_author_signal(item)
    recency_score = compute_recency_score(item.get("date"))
    citation_velocity = compute_citation_velocity(item.get("cited_by_count"), item.get("date"))
    channel_score = source_channel_score(source_type)
    domain_floor = infer_credibility(source_type, url)

    score = (
        0.30 * venue_score
        + 0.25 * author_signal
        + 0.20 * recency_score
        + 0.15 * citation_velocity
        + 0.10 * channel_score
    )
    score = max(score, domain_floor)
    return {
        "credibility_score": round(min(score, 1.0), 4),
        "venue_score": round(venue_score, 4),
        "author_signal": round(author_signal, 4),
        "recency_score": round(recency_score, 4),
        "citation_velocity": round(citation_velocity, 4),
    }


def normalize_result(item):
    url = canonicalize_url(item.get("url"))
    source_type = item.get("source_type")
    normalized = {
        "title": (item.get("title") or "").strip(),
        "summary": (item.get("summary") or "").strip(),
        "source": item.get("source"),
        "source_name": item.get("source_name") or item.get("source"),
        "source_type": source_type,
        "date": item.get("date"),
        "url": url,
        "domain": extract_domain(url),
        "venue": item.get("venue", ""),
        "cited_by_count": item.get("cited_by_count"),
        "author_works_count": item.get("author_works_count"),
        "author_cited_by_count": item.get("author_cited_by_count"),
        "author_h_index": item.get("author_h_index"),
    }
    normalized.update(compute_credibility(normalized))
    return normalized


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
    model = get_embedding_model()
    if model is None:
        query_tokens = set(simplify_query(query, max_words=12).lower().split())
        doc_tokens = set(re.findall(r"\b[a-z0-9]+\b", doc_text.lower()))
        if not query_tokens or not doc_tokens:
            return 0.0
        return len(query_tokens & doc_tokens) / len(query_tokens | doc_tokens)
    target_emb = model.encode(query, convert_to_tensor=True)
    doc_emb = model.encode(doc_text, convert_to_tensor=True)
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
                        "venue": ((item.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
                        "cited_by_count": item.get("cited_by_count"),
                        "author_works_count": sum(
                            ((author.get("author") or {}).get("works_count", 0) or 0)
                            for author in item.get("authorships", [])[:3]
                        ),
                        "author_cited_by_count": sum(
                            ((author.get("author") or {}).get("cited_by_count", 0) or 0)
                            for author in item.get("authorships", [])[:3]
                        ),
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
                        "venue": "arXiv",
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


async def search_semantic_scholar(query, session: aiohttp.ClientSession):
    headers = {}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    params = {
        "query": query,
        "limit": 4,
        "fields": "title,abstract,year,url,citationCount,tldr,venue,authors.hIndex,authors.paperCount,authors.citationCount",
    }
    try:
        async with semantic_scholar_semaphore:
            async with session.get(SEMANTIC_SCHOLAR_API_URL, params=params, headers=headers, timeout=20) as res:
                if res.status != 200:
                    return []

                payload = await res.json()
                results = []
                for item in payload.get("data", []):
                    abstract = (item.get("abstract") or "").strip()
                    tldr = ((item.get("tldr") or {}).get("text") or "").strip()
                    summary = abstract or tldr
                    authors = item.get("authors") or []
                    max_h_index = max((float(author.get("hIndex", 0) or 0) for author in authors), default=0.0)
                    total_papers = sum(float(author.get("paperCount", 0) or 0) for author in authors[:3])
                    total_citations = sum(float(author.get("citationCount", 0) or 0) for author in authors[:3])

                    result = normalize_result(
                        {
                            "title": item.get("title"),
                            "summary": summary,
                            "source": "Semantic Scholar",
                            "source_name": "Semantic Scholar",
                            "source_type": "paper",
                            "date": item.get("year"),
                            "url": item.get("url"),
                            "venue": item.get("venue", ""),
                            "cited_by_count": item.get("citationCount"),
                            "author_h_index": max_h_index,
                            "author_works_count": total_papers,
                            "author_cited_by_count": total_citations,
                        }
                    )
                    if is_valid_result(result):
                        results.append(result)
                return results
    except Exception:
        return []


async def search_official_sources(query, session: aiohttp.ClientSession):
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []
    for source in OFFICIAL_SOURCE_REGISTRY.values():
        scoped_query = f"{source['query_prefix']} {query}"
        try:
            async with session.post(
                "https://html.duckduckgo.com/html/",
                headers=headers,
                data={"q": scoped_query},
                timeout=10,
            ) as res:
                text_data = await res.text()
                soup = BeautifulSoup(text_data, "html.parser")
                for item in soup.select(".result")[:2]:
                    title = item.select_one(".result__title")
                    snippet = item.select_one(".result__snippet")
                    link = item.select_one("a.result__a")
                    result = normalize_result(
                        {
                            "title": title.get_text(strip=True) if title else "",
                            "summary": snippet.get_text(strip=True) if snippet else "",
                            "source": source["label"],
                            "source_name": source["label"],
                            "source_type": "official_source",
                            "url": link["href"] if link else "",
                            "venue": source["label"],
                        }
                    )
                    if result["domain"].endswith(source["domain"]) and is_valid_result(result):
                        results.append(result)
        except Exception:
            continue
    return results


async def retrieve_all_async(query, enabled_sources=None):
    configured_sources = ["openalex", "arxiv", "web", "official"] if enabled_sources is None else enabled_sources
    enabled = {item.lower() for item in configured_sources}
    queries = generate_queries(query)
    all_results = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for refined_query in queries:
            if "openalex" in enabled:
                tasks.append(search_openalex(refined_query, session))
            if "arxiv" in enabled:
                tasks.append(search_arxiv(refined_query, session))
            if "web" in enabled:
                tasks.append(search_web(refined_query, session))
            if "official" in enabled:
                tasks.append(search_official_sources(refined_query, session))
            if "semantic_scholar" in enabled:
                tasks.append(search_semantic_scholar(refined_query, session))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for item in gathered:
            if isinstance(item, list):
                all_results.extend(item)
    return all_results


def retrieve_all(query, enabled_sources=None):
    configured_sources = ["openalex", "arxiv", "web", "official"] if enabled_sources is None else enabled_sources
    log_event(logger, logging.INFO, "Starting retrieval", query=query, enabled_sources=configured_sources)
    all_results = asyncio.run(retrieve_all_async(query, enabled_sources=enabled_sources))
    all_results = deduplicate_results(all_results)
    if not all_results:
        log_event(logger, logging.INFO, "No retrieval results after deduplication", query=query)
        return []

    scored = [score_result(query, result) for result in all_results]
    scored = sorted(
        scored,
        key=lambda item: (item["retrieval_score"], item.get("credibility_score", 0)),
        reverse=True,
    )
    final_results = scored[:8]
    log_event(
        logger,
        logging.INFO,
        "Completed retrieval",
        query=query,
        total_candidates=len(all_results),
        returned_results=len(final_results),
    )
    return final_results
