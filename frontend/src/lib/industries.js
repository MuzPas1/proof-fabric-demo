/**
 * Industry presets for the PFP demo portal.
 *
 * IMPORTANT: This file only controls the *presentation layer* — the displayed
 * compliance check labels and descriptions. The underlying cryptographic
 * proof generation, FEA workflow, verification engine and API contracts are
 * untouched. The backend continues to receive the same compliance payload
 * (kyc/aml/limits/status) regardless of the selected industry.
 */

export const INDUSTRIES = {
  generic_builder: {
    id: "generic_builder",
    label: "Generic Workflow Builder",
    emoji: "\u{1F9F1}", // bricks / building blocks
    tagline: "Configure any workflow — fields, checks and proof — with zero code.",
    builder: true,
    hideConsistency: true,
    certificate: false,
    statusLabels: { pass: "Verified", fail: "Failed" },
    // Checks come from the live builder state, not from this list. Kept empty
    // so any defensive access stays safe.
    checks: [],
    positioning:
      "Most systems prove one workflow at a time. PFP turns any workflow — release, change, ticket, onboarding, approval, AI decision — into the same independently verifiable proof.",
    approaches: {
      traditional: ["Spreadsheets", "Emails", "Screenshots", "Sign-offs", "Trust"],
      pfp: ["Define", "Validate", "Cryptographic Proof", "Verify"],
    },
    ui: {
      heroTitle: "Turn any workflow into cryptographic proof.",
      heroSubtitle:
        "Define your own workflow — name it, add fields and checks — then issue an independently verifiable Proof Artifact. No code, no schema changes.",
      inputTitle: "Workflow Configuration",
      inputDesc:
        "Define the workflow, its fields and its checks. This is the primary demonstration mode.",
      processBtn: "Generate Proof",
      checksTitle: "Workflow Checks",
      checksDesc: "Checks configured for this workflow.",
      failToggle: "Simulate Failure",
      evidenceTitle: "Proof Generated",
      evidenceDesc:
        "A cryptographically verifiable Proof Artifact has been issued for this workflow.",
      evidencePlaceholder:
        "Configure your workflow above and generate the proof. A Proof Artifact (with a Proof ID) will appear here.",
      artifactLabel: "Proof Artifact",
      proofIdLabel: "Proof ID",
      auditorDesc:
        "Verify a workflow Proof using only its Proof ID — no raw workflow data required.",
    },
  },

  generic: {
    id: "generic",
    label: "Generic / Universal",
    emoji: "\u{1F310}", // globe
    tagline: "Cryptographic proof for any regulated workflow.",
    checks: [
      {
        name: "Identity Validation",
        desc: "Verifies the identity of the entity initiating the action or transaction.",
      },
      {
        name: "Authorization Verification",
        desc: "Checks whether the action is permitted under defined policies.",
      },
      {
        name: "Timestamp Integrity Check",
        desc: "Ensures events occurred at the claimed time without tampering.",
      },
      {
        name: "Policy Compliance Validation",
        desc: "Confirms adherence to applicable operational rules or policies.",
      },
      {
        name: "Data Completeness Verification",
        desc: "Checks whether all required information is present.",
      },
      {
        name: "Risk Threshold Analysis",
        desc: "Evaluates whether activity exceeds predefined risk limits.",
      },
      {
        name: "Evidence Completeness Check",
        desc: "Ensures all supporting artifacts required for proof are available.",
      },
      {
        name: "Proof Issuance Readiness",
        desc: "Confirms all checks passed before generating cryptographic proof.",
      },
    ],
  },

  financial: {
    id: "financial",
    label: "Financial Services",
    emoji: "\u{1F4B3}", // credit card
    tagline: "Proof-grade compliance for regulated financial transactions.",
    checks: [
      {
        name: "KYC Verification",
        desc: "Validates customer identity against onboarding requirements.",
      },
      {
        name: "AML Screening",
        desc: "Checks for suspicious activity patterns linked to money laundering.",
      },
      {
        name: "Sanctions Screening",
        desc: "Verifies entities are not listed on sanctions databases.",
      },
      {
        name: "Transaction Limit Validation",
        desc: "Ensures transactions remain within approved thresholds.",
      },
      {
        name: "PEP Verification",
        desc: "Checks whether parties are politically exposed persons.",
      },
      {
        name: "Fraud Detection",
        desc: "Identifies unusual patterns indicating potential fraud.",
      },
      {
        name: "Source of Funds Validation",
        desc: "Verifies legitimacy of funding origins.",
      },
      {
        name: "Regulatory Reporting Readiness",
        desc: "Confirms transaction satisfies reporting obligations.",
      },
    ],
  },

  telecom: {
    id: "telecom",
    label: "Telecom Expense Management (TEM)",
    emoji: "\u{1F4E1}", // satellite
    tagline: "Verifiable proof for telecom invoice and expense governance.",
    checks: [
      {
        name: "Contract-to-Invoice Compliance Validation",
        desc: "Checks whether billed charges match negotiated contract rates.",
      },
      {
        name: "Remit Address Validation",
        desc: "Verifies payment remittance details match approved vendor records to prevent misrouting or fraud.",
      },
      {
        name: "Cost Allocation Verification",
        desc: "Validates whether charges are assigned to correct cost centers.",
      },
      {
        name: "Billing Cycle Compliance Check",
        desc: "Ensures invoices follow expected billing periods.",
      },
      {
        name: "AP Scope Eligibility Verification",
        desc: "Confirms whether accounts qualify for payable processing.",
      },
      {
        name: "Duplicate Invoice Detection",
        desc: "Detects repeated or previously processed invoices.",
      },
      {
        name: "Invoice Processing SLA Compliance",
        desc: "Validates whether invoices were processed within agreed service-level timelines.",
      },
      {
        name: "Special Handling Account Compliance",
        desc: "Validates whether invoices linked to special handling accounts followed required processing rules and approvals.",
      },
    ],
  },

  healthcare: {
    id: "healthcare",
    label: "Healthcare",
    emoji: "\u{1F3E5}", // hospital
    tagline: "Cryptographic proof for clinical and patient-record workflows.",
    checks: [
      {
        name: "Patient Identity Verification",
        desc: "Confirms patient identity before processing records or services.",
      },
      {
        name: "Consent Validation",
        desc: "Checks whether required patient consent exists.",
      },
      {
        name: "Access Authorization Check",
        desc: "Verifies only authorized parties access sensitive records.",
      },
      {
        name: "Prescription Integrity Validation",
        desc: "Ensures prescriptions remain unaltered and valid.",
      },
      {
        name: "Medical Record Completeness Check",
        desc: "Confirms required healthcare information is present.",
      },
      {
        name: "Privacy Compliance Verification",
        desc: "Checks adherence to healthcare privacy regulations.",
      },
      {
        name: "Clinical Workflow Validation",
        desc: "Verifies required clinical procedures were followed.",
      },
      {
        name: "Retention Policy Compliance",
        desc: "Ensures records meet retention requirements.",
      },
    ],
  },

  insurance: {
    id: "insurance",
    label: "Insurance",
    emoji: "\u{1F6E1}", // shield
    tagline: "Auditable proof for policy issuance and claims workflows.",
    checks: [
      {
        name: "Policy Validity Verification",
        desc: "Confirms policy coverage is active and applicable.",
      },
      {
        name: "Coverage Eligibility Validation",
        desc: "Checks whether claims fall within approved coverage.",
      },
      {
        name: "Claim Authenticity Check",
        desc: "Verifies legitimacy of submitted claims.",
      },
      {
        name: "Beneficiary Verification",
        desc: "Confirms beneficiary identity and entitlement.",
      },
      {
        name: "Fraud Screening",
        desc: "Detects suspicious claim patterns.",
      },
      {
        name: "Claim History Validation",
        desc: "Reviews historical claims for anomalies.",
      },
      {
        name: "Underwriting Compliance Check",
        desc: "Ensures underwriting rules were followed.",
      },
      {
        name: "Regulatory Reporting Readiness",
        desc: "Confirms compliance with reporting obligations.",
      },
    ],
  },

  supply_chain: {
    id: "supply_chain",
    label: "Supply Chain",
    emoji: "\u{1F69A}", // delivery truck
    tagline: "Tamper-evident proof across the goods lifecycle.",
    checks: [
      {
        name: "Supplier Verification",
        desc: "Validates supplier legitimacy and approval status.",
      },
      {
        name: "Provenance Tracking Validation",
        desc: "Verifies origin and history of goods.",
      },
      {
        name: "Chain-of-Custody Verification",
        desc: "Confirms custody changes across the lifecycle.",
      },
      {
        name: "Shipment Integrity Check",
        desc: "Checks whether shipment data remains consistent.",
      },
      {
        name: "Customs Compliance Validation",
        desc: "Ensures adherence to import/export regulations.",
      },
      {
        name: "Quality Certification Verification",
        desc: "Confirms quality certifications are valid.",
      },
      {
        name: "Environmental Compliance Check",
        desc: "Validates sustainability or environmental obligations.",
      },
      {
        name: "Delivery Confirmation Validation",
        desc: "Verifies successful delivery events.",
      },
    ],
  },

  government: {
    id: "government",
    label: "Government / Public Sector",
    emoji: "\u{1F3DB}", // classical building
    tagline: "Audit-ready proof for citizen services and public records.",
    checks: [
      {
        name: "Identity Verification",
        desc: "Confirms citizen or entity identity.",
      },
      {
        name: "Eligibility Validation",
        desc: "Checks qualification for programs or services.",
      },
      {
        name: "Document Authenticity Check",
        desc: "Verifies submitted documents are genuine.",
      },
      {
        name: "Authorization Approval Validation",
        desc: "Ensures required approvals exist.",
      },
      {
        name: "Policy Compliance Verification",
        desc: "Checks adherence to government rules.",
      },
      {
        name: "Grant/Subsidy Eligibility Check",
        desc: "Confirms qualification for benefits or subsidies.",
      },
      {
        name: "Public Audit Readiness",
        desc: "Ensures actions are traceable for audits.",
      },
      {
        name: "Record Retention Compliance",
        desc: "Verifies records meet retention mandates.",
      },
    ],
  },

  ecommerce: {
    id: "ecommerce",
    label: "E-commerce",
    emoji: "\u{1F6D2}", // shopping cart
    tagline: "Verifiable proof across orders, payments and fulfillment.",
    checks: [
      {
        name: "Customer Identity Verification",
        desc: "Confirms customer identity where required.",
      },
      {
        name: "Payment Validation",
        desc: "Checks payment authenticity and completeness.",
      },
      {
        name: "Seller Verification",
        desc: "Validates seller legitimacy.",
      },
      {
        name: "Fraud Screening",
        desc: "Detects suspicious transaction behavior.",
      },
      {
        name: "Order Integrity Validation",
        desc: "Ensures order details remain unchanged.",
      },
      {
        name: "Return Eligibility Verification",
        desc: "Checks compliance with return policies.",
      },
      {
        name: "Delivery Confirmation Validation",
        desc: "Verifies order delivery completion.",
      },
      {
        name: "Marketplace Policy Compliance",
        desc: "Confirms adherence to marketplace rules.",
      },
    ],
  },

  manufacturing: {
    id: "manufacturing",
    label: "Manufacturing",
    emoji: "\u{1F3ED}", // factory
    tagline: "Proof-grade traceability for production and quality controls.",
    checks: [
      {
        name: "Supplier Compliance Verification",
        desc: "Validates approved supplier adherence.",
      },
      {
        name: "Batch Traceability Validation",
        desc: "Tracks product batches through production.",
      },
      {
        name: "Quality Inspection Verification",
        desc: "Confirms inspection requirements were met.",
      },
      {
        name: "Production Approval Compliance",
        desc: "Checks production approvals before release.",
      },
      {
        name: "Equipment Certification Validation",
        desc: "Verifies certification status of equipment.",
      },
      {
        name: "Safety Regulation Compliance",
        desc: "Ensures adherence to safety standards.",
      },
      {
        name: "Environmental Compliance Verification",
        desc: "Checks environmental obligations are met.",
      },
      {
        name: "Recall Readiness Check",
        desc: "Confirms traceability for recall scenarios.",
      },
    ],
  },

  change_release: {
    id: "change_release",
    label: "Release Readiness Evaluation",
    emoji: "\u{1F680}", // rocket
    tagline: "Evidence-proof release readiness — not just a report.",
    workflow: "Release Readiness Evaluation",
    // Today's release readiness is report-focused. PFP makes it evidence-proof oriented.
    positioning:
      "Today's release readiness is report-focused. PFP makes it evidence-proof oriented.",
    approaches: {
      traditional: ["Emails", "Checklists", "Screenshots", "Approvals", "Trust"],
      pfp: ["Evidence", "Validation", "Cryptographic Proof", "Verification"],
    },
    // Industry-specific input form (replaces the default 3-field transaction form).
    fields: [
      { key: "release_name", label: "Release Name", default: "Payments Platform v4.2", mono: false },
      { key: "release_id", label: "Release ID", default: "REL-2026-001", mono: true },
      { key: "environment", label: "Environment", type: "select", options: ["Dev", "UAT", "Production"], default: "Production" },
      { key: "application", label: "Application", default: "Payments Platform", mono: false },
      { key: "cab_reference", label: "CAB Reference", default: "CAB-APPROVED-2026", mono: true },
      { key: "release_window", label: "Release Window", default: "Weekend Deployment", mono: false },
    ],
    // Map custom fields onto the canonical proof payload (engine/contract unchanged).
    mapTo: { transaction_id: "release_id", user_id: "application" },
    // UI terminology overrides.
    workflowField: "release_name",
    environmentField: "environment",
    idField: "release_id",
    statusLabels: { pass: "Ready", fail: "Not Ready" },
    certificate: true,
    hideConsistency: true,
    ui: {
      heroTitle: "Cryptographic proof of release readiness.",
      heroSubtitle:
        "Turn change & release approvals into an independently verifiable Release Readiness Proof Artifact — no screenshots, no email trails.",
      inputTitle: "Release Details",
      inputDesc: "Enter the release details to begin readiness verification.",
      processBtn: "Generate Release Readiness Proof",
      checksTitle: "Release Readiness Checks",
      checksDesc: "Automated readiness checks for Release Readiness Evaluation.",
      failToggle: "Simulate Readiness Failure",
      evidenceTitle: "Evidence Generated",
      evidenceDesc: "A Release Readiness Proof Artifact has been issued for this release.",
      evidencePlaceholder:
        "Enter release details above and generate the proof. A Release Readiness Proof Artifact (with a Release Readiness Proof ID) will appear here.",
      artifactLabel: "Release Readiness Proof Artifact",
      proofIdLabel: "Release Readiness Proof ID",
      auditorDesc: "Verify a Release Readiness Proof using only its Proof ID — no raw release data required.",
    },
    checks: [
      { name: "Test Execution Proof", desc: "Confirms functional and regression test suites executed and passed for this release." },
      { name: "UAT Completion Proof", desc: "Verifies user acceptance testing was completed and signed off by business stakeholders." },
      { name: "Security Scan Proof", desc: "Attests that SAST/DAST security scans ran with no unresolved critical findings." },
      { name: "Vulnerability Remediation Proof", desc: "Confirms identified vulnerabilities were remediated or formally risk-accepted." },
      { name: "CAB Approval Proof", desc: "Verifies the Change Advisory Board reviewed and approved the release." },
      { name: "Change Approval Proof", desc: "Confirms the change request was approved per the change-management policy." },
      { name: "Deployment Approval Proof", desc: "Attests deployment was authorized for the target environment and release window." },
      { name: "Rollback Validation Proof", desc: "Verifies a tested rollback / back-out plan exists and was validated." },
      { name: "Compliance Control Proof", desc: "Confirms required compliance and governance controls were satisfied." },
      { name: "Production Monitoring Readiness Proof", desc: "Verifies monitoring, alerting and observability are in place for go-live." },
    ],
  },
};

export const INDUSTRY_ORDER = [
  "generic_builder",
  "generic",
  "financial",
  "telecom",
  "healthcare",
  "insurance",
  "supply_chain",
  "government",
  "ecommerce",
  "manufacturing",
  "change_release",
];

export const DEFAULT_INDUSTRY = "financial";
