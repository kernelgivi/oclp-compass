# Validation record

## 0.2.0 build

Environment: Linux, Python 3.12, Node 24, headless Chromium 153 controlled by Playwright. No physical Intel Mac or Safari was available.

### Completed

- **78 Python tests pass.** Coverage includes all catalog entries, recommendation constraints, evidence boundaries, Darwin probe fixtures, loopback authorization, strict JSON parsing, pairwise comparisons, target plans, simulations, Markdown escaping, and terminal/API behavior.
- **The end-to-end Chromium workflow passes.** It exercises priorities, score explanations, version exclusions, comparisons, human confirmations, blocked targets, downgrade cautions, app constraints, confirmation invalidation, simulations, model search, invalid profile handling, restoration, evidence filters, downloads, command navigation, light mode, larger text, and unkeyed launch behavior.
- All six workspaces were checked for whole-page horizontal overflow at 390 px with larger text enabled. Internal tables/navigation retain their own horizontal scrolling.
- Desktop, plan, inventory, light/large-text, and mobile layouts were rendered and inspected. A narrow-screen overflow bug was found and corrected.
- The browser workflow observes no page exceptions or Content Security Policy violations.
- Automated axe checks for WCAG A/AA rules report no violations in the tested desktop view, version/command dialogs, and five additional mobile workspaces. Keyboard focus was added to scrollable comparison tables after these checks identified an issue. This does not establish full accessibility conformance.
- JavaScript syntax and consistent Python/web formatting checks pass.
- Source CLI and local HTTP integration tests run successfully. Package builds and installed-wheel smoke tests are performed as part of the delivery checks.

The Chromium binary used for local verification was a separate test-environment dependency. It is not bundled with Compass or required for running the app. The application still uses the host's browser. GitHub CI normally installs Chromium through Playwright; a local executable override is available via `COMPASS_BROWSER_EXECUTABLE`.

### Still outstanding before a stable release

- Live detection on an Intel Mac with an APFS SSD, an HDD/Fusion configuration, and dual-GPU hardware.
- Safari/WebKit interaction and layout checks, manual keyboard/screen-reader testing, and an independent accessibility review.
- Independent verification of model/native/graphics boundaries, modified-GPU behavior, and original-model spoofing caveats.
- Target-build validation after a backup, with actual OCLP root patches, recovery, and essential applications.
- Calibration of performance priors against reproducible frame-time and workload measurements.
- A substantially larger, reviewed community corpus with documented selection, provenance, conflicts, and licensing.
- Explicit security-update coverage and independent security review; enable GitHub private vulnerability reporting before public release.

No remote GitHub CI result, physical-Mac result, or security audit is implied by local tests.
