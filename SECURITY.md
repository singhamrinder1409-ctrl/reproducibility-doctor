# Security and trust boundary

This is an experimental portfolio project, not a hardened service for running arbitrary hostile code. Containers share a kernel and can have vulnerabilities. Use a disposable machine/VM for adversarial testing. Keep Docker and its host patched. The host Docker socket is privileged; Doctor uses only an explicitly selected local Unix socket and never exposes it to target code.

Read [the threat model](docs/01-scope-and-architecture.md) and [the live-validation checklist](docs/06-isolated-execution.md) before considering experimental execution. Reference execution/control/cleanup acceptance passed on the recorded Docker Desktop Linux ARM64 setup. Other execution configurations and arbitrary hostile-code safety are not established. There is no automatic execution of README commands, dependency installation, image pulling or approval.

Reports and plans may contain literal configuration or logs. They are private by default and are not automatically redacted. Review a separate copy before sharing. A local approval receipt is editable audit data, not authenticated identity.

For a vulnerability, avoid publishing exploit payloads, credentials or private source in a public issue. Use GitHub's private vulnerability reporting if the repository owner enables it. No private reporting channel or response SLA is claimed before that setting is verified. Until then, report only a minimal non-sensitive description and request a private contact method.
