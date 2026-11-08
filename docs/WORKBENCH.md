# Workbench guide

## Understand the recommendation

The recommended version is the highest-scoring eligible option for the selected priority. A hard exclusion overrides its score: an experimental version cannot become recommended simply by scoring highly. The version table keeps excluded options visible by default so the reason can be inspected.

Use the question-mark buttons to explain the metrics. A version's detail button shows each smoothness penalty, essential-app checks, patching caveats, and the community adjustment. “No reviewed fit” means that no candidate is eligible under the current policy and constraints, or that the model has no reviewed policy. It is not a diagnosis of defective hardware.

“Newer apps” favors a more recent OS. To constrain an actual app, add its vendor-checked requirements in the essential-app form. The checkboxes describe requirements, not capabilities you can turn on. AVX2 is a CPU instruction set; installing a newer OS cannot add it to an older processor. Metal is a graphics API; a generic Metal check does not establish the exact feature family an application needs.

## Compare versions

Select two different macOS versions. The comparison shows the right-hand option minus the left-hand option in preference-index points. A gain of 10 points is not a 10% speed improvement. Native/OCLP path, stock graphics patches, exclusions, and evidence counts are compared separately.

Changing a priority or app requirement recomputes the comparison. An error, such as choosing the same OS twice, does not replace the last valid comparison.

## Prepare a plan

Choose a target version. Compass distinguishes three kinds of check:

- **Pass:** a limited condition follows from the current profile/policy, such as declared constraints or the advisory working-space threshold. It is not proof of installation readiness.
- **Review:** either information is missing or a human needs to check it.
- **Confirmed:** you checked a human-review box. The app has not verified the underlying claim.

A blocked target shows preparation guidance, not installation steps. A target lower than the installed major version includes a downgrade warning. A same-major target does not imply that reinstalling will help.

Confirmations are held separately for each target in the session. Changing hardware, priority, minimum OS, or essential-app constraints clears confirmations. The state “Planning checklist complete” is deliberately narrower than “safe to install.” Export a Markdown plan if you want to retain your checklist; no disk or boot changes occur.

## Inspect or simulate hardware

The inventory uses read-only macOS probes. `DEMO HARDWARE` means no Mac was scanned; `MANUAL PROFILE` means that the profile was selected or loaded by you. OpenCore can spoof the detected model, and the graphics policy assumes original stock hardware. Confirm both before installation.

**Analyze configuration** replaces the analysis profile. Changing models clears CPU/GPU capabilities and the known installed OS so details from the previous machine are not silently reused. Available space is cleared when choosing another model unless you explicitly enter a value.

**Run simulation** leaves the active profile unchanged and compares it with hypothetical RAM/drive assumptions. It does not tell you that the parts are replaceable or that a purchase will achieve a measured improvement.

**Rescan this Mac** runs the fixed inventory probes again. On other platforms it returns an explanatory error; the existing profile is retained. **Restore session profile** returns to the original profile or the latest successfully rescanned hardware.

**Save profile** exports hardware only. **Load profile** accepts that format, validates it on the local server, and labels it manual. A JSON analysis export is not a profile import. Files above 12 KiB are rejected in the browser. No imported profile or preference is automatically retained after the page/session closes.

## Read evidence

The corpus banner distinguishes bundled and imported reports and shows the actual number of reports and covered model identifiers. Report cards display missing dates, RAM, and storage without filling them in. Source permalinks open only when clicked; the app does not fetch or execute them.

The evidence filter changes the visible report list, not the ranking corpus. To change the corpus, launch with `--reports`. A structurally valid import may still contain false reports: human source review remains necessary.

## Readability and keyboard use

- Standard base text is 16 px; **Larger text** uses 18 px. Browser zoom remains available.
- **Light mode** switches to a high-contrast light palette. Both choices apply only to the current page session.
- `Command-K` / `Control-K` opens the command palette. Type to filter, press Enter for the first result, or use Tab to navigate buttons. Escape closes dialogs.
- The first keyboard focus target is a skip-to-workspace link. Navigation, forms, dialog actions, and dynamic confirmation checkboxes use native controls and visible focus rings.
- Narrow screens use a horizontally scrollable navigation row and version tables. The entire page should not scroll horizontally.

The launch URL contains a per-session capability. Compass removes its fragment from the address bar after opening. To reload, reopen the complete URL from Terminal. Do not share it; stop the process to revoke it.
