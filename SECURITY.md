# Security and privacy

This alpha has not received an independent security audit. No software can truthfully promise “no cybersecurity holes.” The design reduces exposed capabilities and tests its main trust boundaries.

## Scope

Compass is a read-only advisor. It does not install macOS, execute OCLP, modify NVRAM/EFI/system volumes, request `sudo`, change SIP/FileVault, or download executables. The default runtime makes no outbound requests. Opening an external reference is an explicit browser action.

The GUI binds only to `127.0.0.1` on a random port by default. Hardware and analysis APIs require a random per-run 256-bit capability in an Authorization header, an exact Host header, and an exact same-origin Origin header. The launch URL carries the capability in a fragment, which is removed from the address bar after boot; it is never embedded in served HTML or request logs. Reloading requires reopening the full launch URL. Stop the process to revoke the capability.

Static routes use a literal allowlist; there is no general filesystem server. JSON request bodies are bounded to 16 KiB; CLI JSON imports to 2 MB; browser hardware profile imports to 12 KiB. Duplicate object keys and non-finite constants are rejected by the server/CLI parser. Socket reads time out, and concurrent request workers are capped at 16. The server sends no-store, no-referrer, nosniff, frame denial, and a strict same-origin CSP. It sets no CORS permissions. Untrusted text is rendered with DOM `textContent`; no HTML injection, eval, or external script/font loading.

Hardware commands have fixed absolute paths and argument arrays, no shell, a restricted environment, and timeouts. Parsing projects only allowed data; full system output is not exported. GPU/system commands may still internally read device identifiers, but Compass does not retain them. JSON imports cannot add executables or arbitrary network destinations. Source links are restricted to known HTTPS hosts and are not fetched by the server.

## Residual risks

- A local malicious process, privileged user, compromised browser/extension, or a user sharing the launch URL can access the session. This is not a sandbox against malware on the same device.
- Loopback HTTP is appropriate only for the local machine. Do not reverse-proxy it, bind it to a public interface, share the capability, or expose it through a tunnel.
- This is a bounded standard-library HTTP server, not a production multiuser service. Connections can still cause local denial of service. No remote-host deployment is supported.
- System commands are trusted OS binaries; output is capped after capture, not streamed under a strict process memory budget.
- Community data can lie. Structural checks and bounded influence do not authenticate authors or prevent coordinated poisoning. Human review and primary-source compatibility gates remain necessary.
- Stock GPU assumptions and spoofed model identifiers can produce a bad hardware fit. Confirm original identity and actual configuration before installing.
- Reports and exports contain hardware model/configuration and optional public author handles. Inspect exports before sharing.
- Runtime has no third-party dependencies. Build and optional UI-test dependencies still need normal maintenance and review; GitHub Actions tags can move.

## Reporting a vulnerability

Use GitHub private vulnerability reporting on the published repository after the maintainer enables it. Do not post exploit details, launch capabilities, or private device data in a public issue. Until that channel is enabled, ask the maintainer for a private contact without disclosing the vulnerability publicly.


## Workbench actions

Comparisons, simulations, plans, and report exports are computed from validated profiles using the same engine. A simulation cannot modify the baseline. Checkboxes are user assertions, not automated checks; changes to analysis settings clear them. Rescanning is explicit, authenticated, and limited to the original fixed read-only probes. Profile imports never open arbitrary filesystem paths or execute profile content. UI session data and preferences use no browser cookies, localStorage, or IndexedDB.
