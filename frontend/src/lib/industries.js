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
};

export const INDUSTRY_ORDER = [
  "generic",
  "financial",
  "telecom",
  "healthcare",
  "insurance",
  "supply_chain",
  "government",
  "ecommerce",
  "manufacturing",
];

export const DEFAULT_INDUSTRY = "generic";
