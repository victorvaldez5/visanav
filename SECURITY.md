# Security Policy

VisaNav handles sensitive information for a vulnerable audience: conversation
content (encrypted at rest), immigration questions, and a directory of legal-aid
organizations. We take security reports seriously and appreciate your help
keeping the project and its users safe.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately through GitHub's **Private Vulnerability Reporting**:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue, the affected component, and steps to reproduce.

This creates a private advisory visible only to you and the maintainers.

Please include, as far as you can:

- The affected service (`api/`, `frontend/`, `scrapers/`, or the `data/` pipeline).
- A description of the vulnerability and its impact.
- Steps to reproduce or a proof of concept.
- Any suggested remediation.

## What to expect

This is a small, volunteer-run project, so responses are **best effort** rather
than bound by a formal SLA. We aim to acknowledge a report within a few days,
keep you updated as we investigate, and credit you in the advisory once a fix is
released (unless you prefer to remain anonymous).

## Scope

In scope:

- The Django API (`api/`): authentication, the chat/SSE pipeline, the
  public-resources endpoints, data handling and retention.
- The Vue frontend (`frontend/`).
- The USCIS scraper (`scrapers/`) and the data ingestion pipeline.
- Handling of secrets and configuration (`config/.env`).

Out of scope:

- Vulnerabilities in third-party dependencies with no exploitable path in this
  project (report those upstream, but feel free to flag them to us too).
- Findings that require a compromised host, physical access, or a
  self-inflicted misconfiguration.
- Reports generated solely by automated scanners with no demonstrated impact.

## A note on data sensitivity

If a report involves exposure of **conversation content or personal data**,
say so explicitly in the title so we can prioritize it. See the "Data retention
& encryption" section of the [README](README.md) for how conversation data is
stored and purged.
