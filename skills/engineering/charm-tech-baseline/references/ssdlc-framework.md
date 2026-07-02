# SSDLC framework — summary for per-repo audits

Source documents: Canonical Library. This file summarises the
parts a per-repo audit needs; it is not the authoritative copy.

## SEC0023 applicability matrix

Two dimensions select the requirement set: **product classification**
and **release type planned in the cycle**.

### Product classifications observed on this estate

| Class | Examples | Notes |
|---|---|---|
| Tools & frameworks | `operator`, `jubilant`, `pytest-jubilant`, `charmlibs`, `concierge`, `charmhub-listing-review`, `api_demo_server` | Major / Minor / Initial release types; **no LTS concept**; **no Penetration Testing or PSIRT Integration mandate**. |
| Component & Platform | `pebble` | Full LTS treatment; Penetration Testing Request + Security Documentation + PSIRT Integration apply on LTS. |
| Packaging (Opinionated) | `charm-ubuntu` | Requirements apply only to the packaging layer + opinionated decisions. Underlying packaged artefact follows its own class. |

### Per-classification requirement scaling

**Tools & frameworks:**

- **Major** — SBOM, Vulnerability Management, Vulnerability Scanning,
  Static Code Analysis, Threat Model, Security Event Logging, Security
  Documentation.
- **Minor** — SBOM, Vulnerability Scanning only.
- **Initial** — as Major minus Security Documentation.

**Component & Platform (pebble):**

- **LTS** — full set including Penetration Testing Request, Security
  Documentation, and PSIRT Integration.
- **Major** — SBOM, Vulnerability Management, Vulnerability Scanning,
  SCA, Threat Model, Security Event Logging, Security Documentation.
- **Minor** — SBOM, Vulnerability Scanning.
- **Initial** — as Major minus Security Documentation.

### Cross-cutting (apply regardless of class)

- **`SECURITY.md`** in every Canonical repository (public or
  private) — independent of release type. Use the SSDLC template;
  adopt the [Ubuntu disclosure policy](https://ubuntu.com/security/disclosure-policy)
  unless there is a clear reason not to. Reference: the LXD
  `SECURITY.md`.
- **CI/CD integration of dependency monitoring** — Dependabot (or
  Renovate) on every Canonical repo; downstream products / repos that
  vendor or bundle code must additionally run software-composition
  scanning on every PR/merge.
- **High/Critical (CVSS) and any CISA KEV-listed** vulnerabilities
  must be remediated before cycle close, or a Risk Acceptance Form
  filed with GRC/OCISO.

## Per-requirement reference

| Requirement | Doc | What an auditor checks |
|---|---|---|
| Static Code Analysis (SCA) | SEC0024 | TIOBE TICS configured (correct viewer config; `flake8`/`pylint` or `staticcheck` available); per-repo Security metric (TQI) target recorded in the *TiCS Targets* spreadsheet. |
| Vulnerability Discovery & Identification | SEC0025 | Dependabot config exists; for downstream/bundled products, a software-composition scanner (`OSV-Scanner`, `Trivy`) is wired into CI; secscan runs at least once per cycle with `--ssdlc-product-name`, `--ssdlc-cycle`, `--ssdlc-product-channel`, `--ssdlc-product-version`. |
| Vulnerability Response (Management) | SEC0026 | `SECURITY.md` present and adopting Ubuntu disclosure policy; SSDLC Vulnerability Response plan authored and reviewed within the past 6 months. |
| Vulnerability Response Standard | SEC0061 | "Know your upstream" data exists for any vendored/bundled component; SEC0061 Annex I upstream/downstream checklist walked. |
| Vulnerability Embargo Policy | — | Standing embargo subteam exists; embargo process documented (need-to-know, ≤90-day embargoes, no silent patching without GRC approval). |
| SBOM | SEC0027 | SBOM generated via `sbom-request.canonical.com`; review requested in `~SSDLC`; required at every release type. |
| Threat Modeling | SEC0028 | Threat model in the central SSDLC Artifacts Drive folder; refreshed every cycle; demonstrates no unacceptable residual risk; any accepted risk has a Risk Acceptance Form. |
| Penetration Testing | SEC0029 | Centrally budgeted by CISO Office; not mandated for tools & frameworks; pebble represented if it hits LTS-equivalent commitment. |
| Security Documentation | SEC0030 | All seven sections per V1.3: Product architecture, Secure by design, Cryptography (A overview, B internal, C exposed, D providing packages, E transit/at-rest), Hardening guidelines, Logging and monitoring, Secure decommissioning, Security lifecycle (EOL + maintained versions + delivery + verification). Plus Reporting a vulnerability. |
| Security Event Logging | SEC0045 | For products with an authn/user/admin surface, the 17 OWASP Application Logging Vocabulary events emitted as JSON (or logfmt), prefer OTLP. |
| PSIRT Coordination | SEC0037 / SEC0038 | Contact path to PSIRT documented (`security@ubuntu.com`, Launchpad private security bug, GitHub Security Advisory); CNA process understood; 24h notice before a security release. |

## Where artifacts live

- **Threat models** — central SSDLC Artifacts Drive (Charm SDK
  consolidated sheet for ops/ops-scenario/ops-tracing/jubilant/concierge;
  separate sheet for pebble).
- **SBOMs** — central SSDLC Artifacts directory, per-product folder.
- **Vulnerability tracker** — GRC *Vulnerability Tracker* template per
  product.
- **TQI security targets** — *TiCS Targets 26.10* spreadsheet.
