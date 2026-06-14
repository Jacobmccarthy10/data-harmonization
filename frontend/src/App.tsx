import { useState } from "react";
import { analyzeClientFile, runCoverage, validateDiscoverFiles } from "./api/client";
import WorkflowStepper from "./components/WorkflowStepper";
import Step1ClientUpload from "./pages/Step1ClientUpload";
import Step2Review from "./pages/Step2Review";
import Step3Recommendation from "./pages/Step3Recommendation";
import Step4DiscoverUpload from "./pages/Step4DiscoverUpload";
import Step5Dashboard from "./pages/Step5Dashboard";
import type { AnalysisResponse, CoverageResponse, DiscoverValidation } from "./types";

export default function App() {
  const [step, setStep] = useState(0);
  const [maxReached, setMaxReached] = useState(0);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [validation, setValidation] = useState<DiscoverValidation | null>(null);
  const [coverage, setCoverage] = useState<CoverageResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const go = (s: number) => {
    setStep(s);
    setMaxReached((m) => Math.max(m, s));
  };

  const restart = () => {
    setStep(0);
    setMaxReached(0);
    setAnalysis(null);
    setValidation(null);
    setCoverage(null);
    setError(null);
  };

  const handleClientFile = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const result = await analyzeClientFile(file);
      setAnalysis(result);
      setValidation(null);
      setCoverage(null);
      setMaxReached(1);
      setStep(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleDiscoverFiles = async (files: File[]) => {
    if (!analysis) return;
    setBusy(true);
    setError(null);
    try {
      const result = await validateDiscoverFiles(analysis.analysis_id, files);
      setValidation(result);
      setCoverage(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleRunCoverage = async () => {
    if (!analysis || !validation?.discover_id) return;
    setBusy(true);
    setError(null);
    try {
      const result = await runCoverage(analysis.analysis_id, validation.discover_id);
      setCoverage(result);
      go(4);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <header className="app-header">
        <img src="/brand/niq-logo-white.png" alt="NielsenIQ" className="logo" />
        <div className="title-block">
          <h1>
            Coverage <span className="accent-serif">Harmonization</span> Studio
          </h1>
          <span className="tagline">
            Client file → Discover recommendation → Discover upload → coverage dashboard
          </span>
        </div>
      </header>
      <div className="container">
        <WorkflowStepper current={step} maxReached={maxReached} onNavigate={setStep} />

        {step === 0 && (
          <Step1ClientUpload busy={busy} error={error} onFile={handleClientFile} />
        )}
        {step === 1 && analysis && (
          <Step2Review analysis={analysis} onContinue={() => go(2)} onRestart={restart} />
        )}
        {step === 2 && analysis && (
          <Step3Recommendation analysis={analysis} onContinue={() => go(3)} />
        )}
        {step === 3 && analysis && (
          <Step4DiscoverUpload
            validation={validation}
            busyUpload={busy && !validation?.valid}
            busyRun={busy && !!validation?.valid}
            error={error}
            onFiles={handleDiscoverFiles}
            onRunCoverage={handleRunCoverage}
          />
        )}
        {step === 4 && coverage && analysis && (
          <Step5Dashboard
            coverage={coverage}
            analysisId={analysis.analysis_id}
            onRestart={restart}
          />
        )}
      </div>
    </>
  );
}
