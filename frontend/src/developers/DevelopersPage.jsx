import React, { useEffect } from "react";
import { DevNav, DevFooter } from "./DevChrome";
import { Hero } from "./Hero";
import { GetStarted } from "./GetStarted";
import { Resources } from "./Resources";
import { Sdks } from "./Sdks";
import { VerificationExamples } from "./VerificationExamples";
import { PlatformStatus } from "./PlatformStatus";

export default function DevelopersPage() {
  useEffect(() => {
    document.title = "Developer Portal · Proof Fabric Protocol";
  }, []);

  return (
    <div className="min-h-screen bg-white text-slate-900" data-testid="developers-page">
      <DevNav />
      <main>
        <Hero />
        <GetStarted />
        <Resources />
        <Sdks />
        <VerificationExamples />
        <PlatformStatus />
      </main>
      <DevFooter />
    </div>
  );
}
