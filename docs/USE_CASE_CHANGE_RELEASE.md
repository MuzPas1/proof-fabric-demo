# Use Case: Change & Release Management

> **Today's release readiness is report-focused. PFP makes it evidence-proof oriented.**

Change & Release Management is an official PFP use case. It turns the approvals,
test results and control checks that gate a production release into a single,
independently verifiable **Release Readiness Proof Artifact** — replacing
screenshots, email trails and spreadsheets with cryptographic evidence.

## The problem

Most organizations decide "are we ready to release?" using a **report**: a
checklist assembled from emails, screenshots, ticket links and verbal approvals.
Reports can be edited, backdated, or assembled after the fact, and an auditor
must *trust* the person presenting them.

| Traditional Approach | PFP Approach |
|---|---|
| Emails → Checklists → Screenshots → Approvals → **Trust** | Evidence → Validation → **Cryptographic Proof** → Verification |

## What PFP produces

When a release passes its readiness checks, PFP issues a **Release Readiness
Proof Artifact** with a **Release Readiness Proof ID**. The proof embeds and
cryptographically binds:

- **Workflow Type** — `Change & Release Management`
- **Release Name** and **Release ID**
- **Environment** — Dev / UAT / Production
- **Status** — Ready / Not Ready
- The full list of readiness checks and their pass/fail outcomes
- **Timestamp** (issued-at) and **Ed25519 signature**

A **Release Readiness Certificate** view summarizes this for stakeholders:
Release Name, Environment, Readiness Score, Proof ID, cryptographic signature,
verification status and generated timestamp.

## Readiness checks

The demo template runs ten Change & Release Management checks:

1. Test Execution Proof
2. UAT Completion Proof
3. Security Scan Proof
4. Vulnerability Remediation Proof
5. CAB Approval Proof
6. Change Approval Proof
7. Deployment Approval Proof
8. Rollback Validation Proof
9. Compliance Control Proof
10. Production Monitoring Readiness Proof

## Independent verification

Auditors, release managers, CAB members or downstream systems verify a release
using **only the Proof ID** — no raw release data is required. Verification
re-derives the canonical hash and checks the Ed25519 signature, confirming the
release readiness evidence is authentic and untampered.

## Same engine, no separate product

This use case reuses the existing PFP workflow end to end — the same proof
generation engine, proof artifact structure, Proof ID generation, signing flow
and auditor verification flow. It is an **additional industry template** in the
demo portal's Industry selector, not a separate application.

> Try it live: open the **[Demo Portal](https://demo.pfprotocol.com)**, choose
> **Change & Release Management** from the Industry dropdown, and generate a
> Release Readiness Proof in seconds.
