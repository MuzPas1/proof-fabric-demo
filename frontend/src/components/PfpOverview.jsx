import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  FileCheck2,
  ShieldCheck,
  Bot,
  Users,
  ScrollText,
  History,
  Building2,
  Landmark,
  Radio,
  Activity,
  Workflow,
  GitBranch,
  ArrowRight,
  CheckCircle2,
  HelpCircle,
  Eye,
  Fingerprint,
} from "lucide-react";

/* --------------------------------- data ---------------------------------- */

const HERO_BADGES = [
  "Proof Generation",
  "Independent Verification",
  "AI Provenance",
  "AI Accountability",
  "Compliance Evidence",
  "Audit Trail Integrity",
  "Enterprise Governance",
  "Tamper-Evident Records",
];

const PROBLEMS = [
  "How can I prove an AI decision occurred?",
  "How can I verify an approval happened?",
  "How can auditors independently verify records?",
  "How can organizations generate compliance evidence automatically?",
  "How can businesses improve accountability?",
  "How can enterprises create verifiable audit trails?",
  "How can organizations reduce manual evidence collection?",
  "How can governance controls become independently verifiable?",
];

const TRADITIONAL = [
  "Trust",
  "Manual evidence collection",
  "Screenshots",
  "Email approvals",
  "Audit reconstruction",
];

const PFP_WAY = [
  "Verification",
  "Cryptographic proof artifacts",
  "Independent validation",
  "Built-in accountability",
  "Audit-ready evidence",
];

const STEPS = [
  {
    n: "1",
    title: "Event Capture",
    body: "Business events, approvals, transactions, workflow actions, and AI decisions are captured as structured evidence.",
    icon: FileCheck2,
  },
  {
    n: "2",
    title: "Proof Generation",
    body: "PFP generates a cryptographically signed proof artifact containing evidence, integrity metadata, timestamps, provenance information, and accountability records.",
    icon: Fingerprint,
  },
  {
    n: "3",
    title: "Independent Verification",
    body: "Authorized parties can independently verify proof authenticity without relying on the originating system.",
    icon: ShieldCheck,
  },
  {
    n: "4",
    title: "Audit & Accountability",
    body: "Proof artifacts can be retained, shared, reviewed, and independently verified during audits, investigations, governance reviews, and compliance assessments.",
    icon: ScrollText,
  },
];

const USE_CASES = [
  { title: "Financial Services", icon: Landmark },
  { title: "AI Governance", icon: Bot },
  { title: "Compliance & Audit", icon: ScrollText },
  { title: "Change & Release Management", icon: GitBranch },
  { title: "Telecom Operations", icon: Radio },
  { title: "Government & Public Sector", icon: Building2 },
  { title: "Risk & Control Monitoring", icon: Activity },
  { title: "Enterprise Workflow Accountability", icon: Workflow },
];

const AI_GOV = [
  "AI provenance",
  "AI accountability",
  "Approval chains",
  "Human oversight",
  "Decision traceability",
  "Governance reviews",
  "Audit readiness",
];

const FAQS = [
  {
    q: "What is a Proof Artifact?",
    a: "A cryptographically verifiable record proving that a specific event occurred and met defined requirements.",
  },
  {
    q: "Can proof artifacts be independently verified?",
    a: "Yes. Independent verification is a core capability of PFP.",
  },
  {
    q: "Is PFP a blockchain?",
    a: "No. PFP is a proof infrastructure platform focused on evidence generation and verification.",
  },
  {
    q: "Does PFP replace auditors?",
    a: "No. PFP helps reduce manual evidence collection and verification effort while supporting audit processes.",
  },
  {
    q: "Can PFP support AI governance?",
    a: "Yes. PFP supports AI provenance, accountability, approval chains, and evidence generation for AI-driven workflows.",
  },
];

const KNOWLEDGE = [
  {
    term: "What is a Proof Artifact?",
    body: "A proof artifact is a cryptographically signed, self-contained record that shows a specific event occurred and satisfied its defined requirements. It bundles the evidence, integrity metadata, a timestamp, and — where applicable — provenance and accountability records, so it can be verified later without access to the originating system.",
  },
  {
    term: "What is Independent Verification?",
    body: "Independent verification means a third party can confirm a proof artifact is authentic and unaltered using only the artifact and the published verification method — without trusting, querying, or accessing the system that produced it.",
  },
  {
    term: "What is AI Accountability?",
    body: "AI accountability is the ability to demonstrate which AI system acted, in what role, and whether appropriate human oversight and approval occurred. PFP captures this as verifiable evidence rather than an unverifiable claim.",
  },
  {
    term: "What is AI Provenance?",
    body: "AI provenance records the identity of the AI system involved in an action — provider, model, version, and workflow context — bound cryptographically to the proof so the participation can be independently confirmed. PFP records provenance using hashes only, without exposing raw prompts, inputs, or outputs.",
  },
  {
    term: "What is Compliance Evidence?",
    body: "Compliance evidence is documentation that demonstrates a control, policy, or requirement was met. PFP produces this evidence as verifiable proof artifacts, reducing manual collection and making it independently checkable during audits.",
  },
  {
    term: "What is Proof of Approval?",
    body: "Proof of approval is verifiable evidence that a required approval — such as a sign-off, review, or authorization — actually took place, by whom (as an opaque reference), and in what sequence, captured within a proof artifact.",
  },
  {
    term: "What is Proof of Execution?",
    body: "Proof of execution is verifiable evidence that a workflow action, transaction, or process step was carried out and met its defined conditions, recorded as a tamper-evident proof artifact.",
  },
  {
    term: "What is Audit Readiness?",
    body: "Audit readiness is the state of having evidence available in a form auditors can independently verify. PFP supports audit readiness by generating proof artifacts continuously, so evidence does not have to be reconstructed after the fact.",
  },
];

/* --------------------------- small building blocks ------------------------ */

function SectionHeading({ eyebrow, title, subtitle, id }) {
  return (
    <div className="max-w-2xl">
      {eyebrow && (
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-blue-600">
          {eyebrow}
        </div>
      )}
      <h2
        id={id}
        className="mt-2 text-2xl sm:text-3xl font-semibold tracking-tight text-gray-900 font-['Space_Grotesk']"
      >
        {title}
      </h2>
      {subtitle && <p className="mt-3 text-base text-gray-600">{subtitle}</p>}
    </div>
  );
}

/* ------------------------------- top sections ----------------------------- */

export function PfpTopSections() {
  return (
    <div data-testid="pfp-overview-top">
      {/* Hero */}
      <section
        className="max-w-5xl mx-auto px-6 pt-12 pb-8"
        data-testid="pfp-hero"
      >
        <h1
          className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-gray-900 font-['Space_Grotesk']"
          data-testid="pfp-hero-h1"
        >
          Proof Fabric Protocol (PFP)
        </h1>
        <h2
          className="mt-3 text-lg sm:text-xl font-medium text-gray-700 max-w-3xl"
          data-testid="pfp-hero-h2"
        >
          Independently Verifiable Proof Infrastructure for Compliance,
          Governance, and Accountability
        </h2>
        <p className="mt-4 text-base text-gray-600 max-w-2xl">
          Proof Fabric Protocol (PFP) generates cryptographically verifiable
          proof artifacts for transactions, approvals, workflow actions, AI
          decisions, and business events.
        </p>
        <p className="mt-2 text-base text-gray-600 max-w-2xl">
          PFP helps organizations move from trust-based assertions to
          independently verifiable proof.
        </p>

        <div
          className="mt-6 flex flex-wrap gap-2"
          data-testid="pfp-hero-badges"
        >
          {HERO_BADGES.map((b) => (
            <span
              key={b}
              className="inline-flex items-center rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700"
              data-testid={`pfp-badge-${b.toLowerCase().replace(/\s+/g, "-")}`}
            >
              {b}
            </span>
          ))}
        </div>
      </section>

      {/* What is PFP */}
      <section
        className="max-w-5xl mx-auto px-6 py-8 border-t border-gray-100"
        data-testid="pfp-what"
      >
        <SectionHeading eyebrow="Overview" title="What is PFP?" />
        <div className="mt-5 rounded-2xl border border-gray-200 bg-gradient-to-br from-gray-50 to-white px-6 py-6 shadow-sm">
          <p className="text-base text-gray-700 leading-relaxed">
            Proof Fabric Protocol (PFP) is a{" "}
            <span className="font-semibold text-gray-900">
              cryptographic proof infrastructure platform
            </span>{" "}
            that generates independently verifiable evidence for transactions,
            approvals, workflow actions, AI decisions, and business events.
          </p>
          <p className="mt-4 text-base text-gray-700 leading-relaxed">
            Instead of relying on screenshots, emails, logs, spreadsheets, or
            manual attestations, PFP generates cryptographically verifiable
            proof artifacts that can be independently verified.
          </p>
        </div>
      </section>

      {/* Problems */}
      <section
        className="max-w-5xl mx-auto px-6 py-8 border-t border-gray-100"
        data-testid="pfp-problems"
      >
        <SectionHeading
          eyebrow="The Problem"
          title="Problems PFP helps address"
          subtitle="Common accountability and evidence questions enterprises face today."
        />
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {PROBLEMS.map((p, i) => (
            <div
              key={i}
              className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-4 shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-50/40"
              data-testid={`pfp-problem-${i}`}
            >
              <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
              <span className="text-sm font-medium text-gray-800">{p}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Why PFP */}
      <section
        className="max-w-5xl mx-auto px-6 py-8 border-t border-gray-100"
        data-testid="pfp-why"
      >
        <SectionHeading eyebrow="Why PFP" title='Move from "Trust Me" to "Verify It Yourself."' />
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-gray-200 bg-gray-50 px-6 py-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Traditional Approach
            </div>
            <ul className="mt-4 space-y-2.5">
              {TRADITIONAL.map((t) => (
                <li key={t} className="flex items-center gap-2.5 text-sm text-gray-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-blue-200 bg-blue-50/50 px-6 py-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-blue-700">
              PFP Approach
            </div>
            <ul className="mt-4 space-y-2.5">
              {PFP_WAY.map((t) => (
                <li key={t} className="flex items-center gap-2.5 text-sm font-medium text-gray-800">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-blue-600" />
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section
        className="max-w-5xl mx-auto px-6 py-8 border-t border-gray-100"
        data-testid="pfp-how"
      >
        <SectionHeading eyebrow="How it works" title="How PFP Works" />
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {STEPS.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.n}
                className="relative rounded-2xl border border-gray-200 bg-white px-6 py-6 shadow-sm"
                data-testid={`pfp-step-${s.n}`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-sm font-semibold text-white">
                    {s.n}
                  </div>
                  <Icon className="h-5 w-5 text-blue-600" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-gray-900">
                  Step {s.n} — {s.title}
                </h3>
                <p className="mt-2 text-sm text-gray-600 leading-relaxed">
                  {s.body}
                </p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

/* ------------------------------ bottom sections --------------------------- */

export function PfpBottomSections() {
  return (
    <div data-testid="pfp-overview-bottom" className="space-y-0">
      {/* Enterprise use cases */}
      <section className="pt-10 mt-6 border-t border-gray-200" data-testid="pfp-usecases">
        <SectionHeading
          eyebrow="Applications"
          title="Enterprise Use Cases"
          subtitle="Where independently verifiable proof creates measurable trust."
        />
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {USE_CASES.map((u, i) => {
            const Icon = u.icon;
            return (
              <div
                key={i}
                className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-4 shadow-sm transition-colors hover:border-blue-200"
                data-testid={`pfp-usecase-${i}`}
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50">
                  <Icon className="h-4.5 w-4.5 text-blue-600" />
                </div>
                <span className="text-sm font-medium text-gray-800">
                  {u.title}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* AI Governance */}
      <section className="pt-10 mt-8 border-t border-gray-200" data-testid="pfp-ai-governance">
        <SectionHeading
          eyebrow="AI Trust Layer"
          title="AI Governance & Accountability"
          subtitle="PFP can generate evidence that supports how AI-driven decisions are governed, reviewed, and held accountable."
        />
        <div className="mt-6 rounded-2xl border border-gray-200 bg-gradient-to-br from-blue-50/60 to-white px-6 py-6 shadow-sm">
          <div className="flex items-center gap-3">
            <Bot className="h-5 w-5 text-blue-600" />
            <span className="text-sm font-semibold text-gray-900">
              Evidence PFP can support
            </span>
          </div>
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {AI_GOV.map((a) => (
              <div
                key={a}
                className="flex items-center gap-2.5 rounded-lg border border-gray-100 bg-white px-4 py-3"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0 text-blue-600" />
                <span className="text-sm text-gray-700">{a}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="pt-10 mt-8 border-t border-gray-200" data-testid="pfp-faq">
        <SectionHeading eyebrow="FAQ" title="Frequently Asked Questions" />
        <div className="mt-5 rounded-2xl border border-gray-200 bg-white px-2 shadow-sm">
          <Accordion type="single" collapsible className="w-full">
            {FAQS.map((f, i) => (
              <AccordionItem
                key={i}
                value={`faq-${i}`}
                className="px-4"
                data-testid={`pfp-faq-item-${i}`}
              >
                <AccordionTrigger className="text-left text-sm font-semibold text-gray-900 hover:no-underline">
                  {f.q}
                </AccordionTrigger>
                <AccordionContent className="text-sm text-gray-600 leading-relaxed">
                  {f.a}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      {/* Knowledge Center */}
      <section className="pt-10 mt-8 border-t border-gray-200" data-testid="pfp-knowledge">
        <SectionHeading
          eyebrow="Knowledge Center"
          title="Concepts & Definitions"
          subtitle="Plain-language explanations of the core ideas behind verifiable proof."
        />
        <div className="mt-5 rounded-2xl border border-gray-200 bg-white px-2 shadow-sm">
          <Accordion type="single" collapsible className="w-full">
            {KNOWLEDGE.map((k, i) => (
              <AccordionItem
                key={i}
                value={`kc-${i}`}
                className="px-4"
                data-testid={`pfp-knowledge-item-${i}`}
              >
                <AccordionTrigger className="text-left text-sm font-semibold text-gray-900 hover:no-underline">
                  {k.term}
                </AccordionTrigger>
                <AccordionContent className="text-sm text-gray-600 leading-relaxed">
                  {k.body}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>
    </div>
  );
}
