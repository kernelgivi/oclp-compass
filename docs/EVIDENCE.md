# Community evidence

Compass ships two short, independently written summaries of public owner reports. It does not scrape on startup or claim broad coverage. A useful community layer needs versioned data, explicit provenance, and review—not a fabricated “95% of owners agree” label.

## Import

```bash
python3 -m compass validate-evidence reports.json
python3 -m compass gui --reports reports.json
python3 -m compass recommend --demo --reports reports.json --json
```

Imports replace the seed corpus for this session. Validation is structural, not proof of authenticity. The application never fetches imported URLs, so a report cannot instruct it to connect to arbitrary systems. A user can deliberately open an approved source link in the browser. HTML in summaries is displayed as text.

Use an array with exactly these fields on every report:

```json
[
  {
    "id": "your-stable-report-id",
    "model": "MacBookPro13,3",
    "os_major": 15,
    "os_version": "15.7.1",
    "oclp_version": "2.4.1",
    "author": "source:public-author-handle",
    "reported_on": "2026-10-01",
    "reviewed_on": "2026-11-08",
    "ram_gb": 16,
    "storage": "ssd",
    "sentiment": "mixed",
    "summary": "Example only: replace with a faithful short summary of an actual report.",
    "url": "https://github.com/OWNER/REPOSITORY/issues/123"
  }
]
```

The example is synthetic and is not bundled as a real report. `reported_on` may be null when a source does not expose an exact date. `ram_gb` may be null. Storage: `ssd`, `hdd`, `fusion`, `unknown`. Sentiment: `positive`, `mixed`, `negative`. Dates cannot be in the future; publication cannot follow review. Files are limited to 2 MB and 5,000 records.

Allowed HTTPS source hosts: Reddit, GitHub, MacRumors forums, Dortania docs, and Apple Support. No credentials, nonstandard port, query, or fragment. For individual GitHub/MacRumors comments, use the thread permalink and make the specific author/context explicit in the summary; fragment URLs are currently rejected. One report per source permalink is allowed. This limitation favors auditable small imports over exhaustive thread mining.

## Review checklist

- Open the actual report; a search snippet is not sufficient.
- Match the exact model identifier. If the source unambiguously names a unique year/screen-size model, document that mapping; otherwise leave it out.
- Record OS and OCLP versions exactly as stated. Use `unspecified` for missing OCLP version; never invent it.
- Preserve negative/mixed experiences and relevant workload, fan, battery, or patching caveats.
- Do not treat upvotes as independent measurements. Do not summarize replies as the original author's experience.
- Keep unknown dates, RAM, and drives unknown. Review date is not publication date.
- Avoid reproducing full posts, screenshots, private messages, personal identifiers, or deleted content.
- Recheck a source before changing its sentiment or claiming an issue is resolved.

The 2015 13-inch report maps to MacBookPro12,1 because that description identifies that model family unambiguously. Both seed publication dates are null because retrieval exposed relative dates, not exact publication dates. Their score influence is correspondingly weak.

For genuinely strong evidence, submit a reproducible protocol: exact hardware, original GPU, OS build, patcher version, clean/upgrade install, time since indexing, workload, RAM pressure, frame-time distribution, power state, ambient/thermal conditions, and repeated runs. Benchmarks should become a separately validated data type, not be smuggled into sentiment summaries.
