def rank_and_select(candidates, top_k=3):

    # sort by final_score
    sorted_candidates = sorted(
        candidates,
        key=lambda x: x["scores"]["final_score"],
        reverse=True
    )

    selected = []
    seen_titles = []

    for cand in sorted_candidates:
        title = cand["candidate_title"].lower()

        # simple dedup (can improve later)
        if any(t in title for t in seen_titles):
            continue

        selected.append(cand)
        seen_titles.append(title)

        if len(selected) >= top_k:
            break

    return selected