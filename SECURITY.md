# Security Policy

## Supported Versions

Only the latest `master` commit is supported. No release channel exists yet —
please upgrade to `master` before reporting.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, email the maintainers at the address shown on the GitHub profile
(alimaandev), or use GitHub's private vulnerability reporting:

> **Security** tab → **Report a vulnerability** on the repository page.

Please include:

- A description of the vulnerability and the affected component
- Steps to reproduce (without secrets)
- Any impact assessment you can make (e.g. whether an API key or OAuth token
  could leak)

You will receive a response within a few days. We ask that you give us time to
fix and release a patch before disclosing the issue publicly.

## Scope

Relevant concerns: secrets handling (`.env`, OAuth tokens, API keys), upload
credentials, and any code execution risks in the Remotion render path.
