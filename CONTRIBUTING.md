# Contributing

Keep policy data, evidence, and implementation changes separately reviewable. Explain the concrete behavior that changes and link the primary source. Unsupported configurations should lead to abstention, not a guessed confident answer.

For policy changes, include original model identifier, stock versus modified hardware, affected OS/builds, OCLP release, and an upstream citation. Update `policy.json` review date only after reviewing the whole snapshot, not after editing one report. Native macOS boundaries must be checked against Apple as well as Dortania.

For evidence changes, follow [EVIDENCE.md](docs/EVIDENCE.md), retain incomplete/negative outcomes, and validate the JSON. Do not add synthetic reports to the real corpus. Larger collections should document how they were selected and deduplicated. Open issue forms are a contribution intake, not an automatically trusted database.

For code changes, run `python3 -m unittest discover -v`, `node --check compass/web/app.js`, and relevant browser tests. Add focused tests around new decision boundaries. Use fixed argument arrays for OS probes. Avoid new runtime dependencies unless their value and maintenance cost are explicit. UI text and report summaries must remain data, never HTML.

Before submitting detection fixtures, remove serial numbers, UUIDs, user paths, hostnames, network identifiers, and credentials. The project needs a diverse real Intel Mac smoke-test matrix; passing fixture tests is not a replacement.
