# Architecture and ranking policy

## Boundaries

`hardware.py` is the only module that launches system commands. All executable paths and arguments are fixed; no shell, administrator access, environment inheritance, or downloaded code. It projects system output into a small allowlisted profile. Serial numbers, account names, paths, UUIDs, and network addresses are not retained. The supported platforms are macOS for live detection and Python 3.10+ platforms for simulation.

`schema.py` validates hardware at the boundary. `requirements.py` validates declared essential-app requirements. `evidence.py` validates report shape and computes a weak sentiment signal. `engine.py` has no IO except reading packaged JSON; its date and evidence are injectable for reproducibility. `cli.py` and `server.py` call that engine. The web UI is plain HTML/CSS/JavaScript with no build step or third-party runtime.

The engine recognizes a deliberately bounded, explicit catalog. An identifier being absent means “unreviewed by Compass,” not “unsupported by OCLP.” Mac Pro/Xserve are excluded from the reviewed catalog because GPU swaps and CPU topology make a model-only answer unreliable. OpenCore can spoof model identifiers; the GUI and CLI warn about this rather than claiming to recover the original identity.

## Heuristics, not benchmarks

For each OS:

```
smoothness = clamp(capacity + 10 - RAM_penalty - storage_penalty
                   - OS_load - graphics_penalty + community_adjustment, 0, 100)
```

`capacity` is the hand-authored model prior in `models.json`. All variants in a model group currently share the same prior; CPU upgrades, clocks, throttling, and core count do not adjust it. This is a material limitation. GPU names are displayed, but graphics policy is based on stock configuration, not a PCI-device patch detector. Those two limitations are why results are provisional.

| RAM | Penalty |
| --- | --- |
| Under 4 GiB | 22 |
| 4 to under 8 GiB | 14 |
| 8 to under 16 GiB | 5 |
| 16 GiB or more | 0 |

| Storage | Penalty |
| --- | --- |
| SSD | 0 |
| Unknown | 7 |
| Fusion | 12 |
| HDD | 18 |

OS load: Big Sur 0, Monterey 3, Ventura 9, Sonoma 14, Sequoia 18, Tahoe 30. Graphics penalty: 18 for non-Metal, otherwise 6 when stock graphics require patches, otherwise 0.

Maintenance ease starts at 95; subtract 20 for an OCLP route, 18 for graphics patching, 12 for non-Metal. It estimates maintenance burden only, **not security posture**. Wi-Fi patching and version-specific behaviors are warnings rather than a complete patch inventory.

| Priority | Smoothness | OS recency | Maintenance ease |
| --- | --- | --- | --- |
| Balanced | 45% | 35% | 20% |
| Smoothness | 75% | 10% | 15% |
| Newer apps | 20% | 65% | 15% |

Recency is a manually assigned preference scale in `policy.json`. It does not establish whether Apple currently issues security fixes for an OS. Older native installations can win a smoothness-first ranking; their current app/security coverage still needs explicit verification. Security-update eligibility is not presently a hard ranking gate.

Candidates failing a hard constraint remain visible but cannot win. Ordering is eligibility, weighted score, then newer major version on a tie. An unknown AVX2 capability blocks a declared AVX2-dependent essential app. Meeting the declared minimums is labeled `meets_declared_requirements`, never “application verified.” Major OS requirements do not encode minor/build minimums yet.

## Community signal

Match exact model + major OS only. Do not transfer results between screen sizes, adjacent model identifiers, or unspecified years. Keep only the newest dated contribution per case-insensitive author for weighting. Undated reports are retained with reduced weight. Duplicate source URLs (including www/non-www Reddit variants) are rejected during validation.

Per-report weight begins at `0.5 ** (age_days / 365)`. An unknown publication date starts at `0.35`; the review date never substitutes for a publication date. Multiply by 0.7 for unknown RAM, or 0.4 if RAM differs by more than 4 GiB; multiply by 0.7 for unknown storage or 0.3 for mismatched storage.

Sentiment values: positive +1, mixed 0, negative -1. Then:

```
delta = 8 * sum(sentiment * weight) / (8 + sum(weight))
```

Contradictions, independent count, effective sample, links, and adjustment are returned in JSON. Confidence remains `limited` for every nonempty anecdotal sample; adding reports does not create benchmark confidence. Author independence is an assumption, not identity verification. This is resistant to accidental duplicate weighting, not a Sybil-proof reputation system. OS minor/build versions and OCLP versions are retained as context but not used for exclusion/matching, so always review them before acting.

## Policy maintenance

Snapshot reviewed: 2026-11-08. A snapshot older than 90 days gets a visible stale warning. No runtime refresh silently changes recommendations. Update policy and citations in a normal reviewed PR, re-run tests, and retain historical releases. The snapshot uses OCLP 2.5.1 stable and excludes Tahoe's 3.0.0-rc.5 path from stable recommendations.

Primary sources are in `policy.json`. Native support boundaries should be cross-checked against Apple's [MacBook Pro](https://support.apple.com/en-us/108052), [MacBook Air](https://support.apple.com/en-us/102869), [iMac](https://support.apple.com/en-us/108054), and [Mac mini](https://support.apple.com/en-us/102852) identification pages. This is an independent policy, not copied OCLP implementation code.


## Workbench and planning boundary (0.2)

`planning.py` consumes a recommendation result to compare two reviewed candidates, produce target-specific preparation phases, and format an escaped Markdown report. `scenarios.py` re-runs the same engine on an immutable hypothetical hardware profile; it never changes the original profile or baseline result. No planning or comparison function executes operating-system commands.

The GUI transport is isolated in `web/api.js`; DOM/text/download helpers are in `web/dom.js`. `web/app.js` owns in-memory session state, views, and event coordination. Replaced analyses abort superseded requests and invalidate dependent plan/comparison/scenario results. Results from older requests are ignored using revision counters. Invalid input leaves the previous valid analysis visible instead of committing a partially validated hardware profile. Changes to the analysis configuration invalidate all human plan confirmations.

The server uses the same validated request shape for analysis, comparison, plan, simulation, and report endpoints. `/api/rescan` is an authenticated, origin-checked explicit action that reruns the fixed read-only probes. No API writes user files or settings. Profile/Markdown/JSON saves are browser downloads initiated by a user action.

Planning space checks use the existing advisory 45 GiB threshold; they do not claim exact installer requirements. Human confirmations are assertions held by the browser for a single target/profile/session. A complete planning checklist is not an installation-safety gate, security guarantee, or privilege escalation.

Local imports reject duplicate JSON keys and non-finite JSON constants. Canonical ISO dates keep evidence sorting and decay consistent. Source URLs reject whitespace, backslashes, and HTML angle brackets as well as the original scheme/host/credential restrictions. Exported Markdown escapes imported notes and summaries rather than emitting active source HTML.
