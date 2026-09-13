# Security Policy

## Supported versions

We support the latest minor release with security patches.

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report vulnerabilities privately:

1. Open a private security advisory on GitHub:
   `https://github.com/bucky-ops/intelligent-profiling-engine/security/advisories/new`
2. Or email the maintainers directly with "SECURITY" in the subject.

Please include:
- a minimal reproduction,
- the affected version (commit hash or tag),
- the expected and actual behaviour,
- any mitigations you have already tried.

We aim to acknowledge reports within 72 hours and to ship a patch within
30 days for high-severity issues.

## Hardening recommendations for production deployments

- Run the Streamlit / GUI process under a dedicated non-root OS user.
- Store `profiles.json` on an encrypted volume and restrict file permissions
  to `0600`.
- Do **not** expose the Streamlit app directly to the internet without
  authentication; place it behind a reverse proxy with auth (e.g., Caddy /
  nginx + OAuth2 proxy).
- Set `LOG_LEVEL=WARNING` and ship logs to a central collector.
- Enable the `bandit` and `pip-audit` jobs in CI (already wired in
  `.github/workflows/ci.yml`).

## Privacy notice

The engine is designed to operate on **fully synthetic** data. If you ingest
real personal data, ensure you have a lawful basis under your local data
protection regime (e.g., GDPR, CCPA) and implement the appropriate
retention policies.
