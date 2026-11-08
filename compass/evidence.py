"""Evidence is data, never executable instructions or a compatibility authority."""

from __future__ import annotations
from datetime import date
from .schema import MODEL, number, source_url, text

FIELDS = {
    "id",
    "model",
    "os_major",
    "os_version",
    "oclp_version",
    "author",
    "reported_on",
    "reviewed_on",
    "ram_gb",
    "storage",
    "sentiment",
    "summary",
    "url",
}


def validate_reports(data, today=None):
    today = today or date.today()
    if not isinstance(data, list) or len(data) > 5000:
        raise ValueError("Expected an array of at most 5000 reports")
    seen_ids, seen_urls = set(), set()
    for r in data:
        if not isinstance(r, dict) or set(r) != FIELDS:
            raise ValueError("Report fields must exactly match the documented schema")
        for key in ("id", "model", "os_version", "oclp_version", "author", "summary"):
            text(r[key], key, 500 if key == "summary" else 200)
        if (
            not MODEL.fullmatch(r["model"])
            or type(r["os_major"]) is not int
            or r["os_major"] not in {11, 12, 13, 14, 15, 26}
        ):
            raise ValueError("Invalid model or macOS major")
        if r["ram_gb"] is not None:
            number(r["ram_gb"], "report RAM", 1, 2048)
        if r["storage"] not in {"ssd", "hdd", "fusion", "unknown"} or r[
            "sentiment"
        ] not in {"positive", "mixed", "negative"}:
            raise ValueError("Invalid storage or sentiment")
        for key in ("reported_on", "reviewed_on"):
            if r[key] is None and key == "reported_on":
                continue
            if (
                not isinstance(r[key], str)
                or date.fromisoformat(r[key]).isoformat() != r[key]
                or date.fromisoformat(r[key]) > today
            ):
                raise ValueError("Evidence dates cannot be in the future")
        if r["reported_on"] and r["reported_on"] > r["reviewed_on"]:
            raise ValueError("Review precedes report publication")
        source_url(r["url"])
        url_key = (
            r["url"]
            .replace("https://www.reddit.com/", "https://reddit.com/")
            .rstrip("/")
        )
        if r["id"] in seen_ids or url_key in seen_urls:
            raise ValueError("Duplicate report identifier or source permalink")
        seen_ids.add(r["id"])
        seen_urls.add(url_key)
    return data


def summarize(reports, hw, major, today):
    matched = [r for r in reports if r["model"] == hw.model and r["os_major"] == major]
    usable, authors = [], set()
    for r in sorted(matched, key=lambda x: x["reported_on"] or "", reverse=True):
        # One independent contribution per author per model + OS. No vote weighting.
        author = r["author"].casefold()
        if author in authors:
            continue
        authors.add(author)
        weight = (
            0.35
            if r["reported_on"] is None
            else 0.5 ** ((today - date.fromisoformat(r["reported_on"])).days / 365)
        )
        if r["ram_gb"] is None:
            weight *= 0.7
        elif abs(r["ram_gb"] - hw.ram_gb) > 4:
            weight *= 0.4
        if r["storage"] == "unknown" or hw.storage == "unknown":
            weight *= 0.7
        elif r["storage"] != hw.storage:
            weight *= 0.3
        usable.append((r, weight))
    total = sum(w for _, w in usable)
    direction = sum(
        {"positive": 1, "mixed": 0, "negative": -1}[r["sentiment"]] * w
        for r, w in usable
    )
    # Eight neutral pseudo-observations shrink anecdotes; adjustment is capped at ±8.
    delta = round(8 * direction / (8 + total), 2)
    opinions = {r["sentiment"] for r, _ in usable}
    return {
        "count": len(matched),
        "independent": len(usable),
        "effective_sample": round(total, 2),
        "adjustment": delta,
        "confidence": "limited" if usable else "none",
        "conflicting": "positive" in opinions and "negative" in opinions,
        "reports": matched,
    }
