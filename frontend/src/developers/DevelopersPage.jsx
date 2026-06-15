import React, { useEffect } from "react";
import { DevNav, DevFooter } from "./DevChrome";
import { SandboxProvider } from "./SandboxContext";
import { Hero } from "./Hero";
import { WhyPfp } from "./WhyPfp";
import { Onboarding } from "./Onboarding";
import { Playground } from "./Playground";
import { GetStarted } from "./GetStarted";
import { Sdks } from "./Sdks";
import { VerificationExamples } from "./VerificationExamples";
import { UseCases } from "./UseCases";
import { TrustArchitecture } from "./TrustArchitecture";
import { Resources } from "./Resources";
import { PlatformStatus } from "./PlatformStatus";

export default function DevelopersPage() {
  useEffect(() => {
    document.title = "Developer Portal · Proof Fabric Protocol";
  }, []);

  return (
    <SandboxProvider>
      <div className="min-h-screen bg-white text-slate-900" data-testid="developers-page">
        <DevNav />
        <main>
          <Hero />
          <WhyPfp />
          <Onboarding />
          <Playground />
          <GetStarted />
          <Sdks />
          <VerificationExamples />
          <UseCases />
          <TrustArchitecture />
          <Resources />
          <PlatformStatus />
        </main>
        <DevFooter />
      </div>
    </SandboxProvider>
  );
}
