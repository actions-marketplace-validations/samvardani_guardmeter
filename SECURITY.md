# Security Policy

## Supported versions

GuardMeter is pre-1.0. Security fixes are released for the **latest minor
version** only. Please upgrade to the newest `0.x` release before reporting an
issue.

| Version | Supported |
|---------|-----------|
| 0.5.x   | ✅ |
| < 0.5   | ❌ |

## Reporting a vulnerability

Please report vulnerabilities privately through **GitHub Private Vulnerability
Reporting**: open the repository's **Security** tab → **Report a vulnerability**
(https://github.com/samvardani/guardmeter/security/advisories/new). This keeps
the report confidential until a fix is available. Do not open a public issue for
security problems. We aim to acknowledge reports within a few days and will
credit reporters who wish to be named.

## `guardmeter serve` threat model

`guardmeter serve` is a **local developer tool**: it binds `127.0.0.1` by
default and performs no evaluation that a local user could not already run. When
bound to any non-loopback interface it **requires** a `GUARDMETER_TOKEN`, which
every `/api/*` request must present as a Bearer token (compared with
`hmac.compare_digest`), and it applies a per-IP rate limit. It terminates
**plain HTTP with no TLS**, so if you must expose it beyond localhost, put it
behind a reverse proxy that provides TLS and access control.

## Notes

- Guard adapters read API keys from environment variables
  (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`); keys are never taken from CLI flags.
- Log output is passed through a redactor that masks common secret shapes
  (API keys, bearer tokens, long hex/base64 runs).
- Generated reports carry a `MANIFEST.json` of SHA-256 hashes; run
  `guardmeter verify-report <dir>` to detect tampering.
