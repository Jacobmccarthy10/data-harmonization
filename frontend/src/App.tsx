import { useState } from "react";
import { analyzeClientFile, runCoverage, validateDiscoverFiles } from "./api/client";
import WorkflowStepper from "./components/WorkflowStepper";
import MappingGraphPage from "./pages/MappingGraphPage";
import Step1ClientUpload from "./pages/Step1ClientUpload";
import Step2Review from "./pages/Step2Review";
import Step3Recommendation from "./pages/Step3Recommendation";
import Step4DiscoverUpload from "./pages/Step4DiscoverUpload";
import Step5Dashboard from "./pages/Step5Dashboard";
import type { AnalysisResponse, CoverageResponse, DiscoverValidation } from "./types";

type AppView = "workflow" | "mapping_graph";

export default function App() {
  const [view, setView] = useState<AppView>("workflow");
  const [step, setStep] = useState(0);
  const [maxReached, setMaxReached] = useState(0);
  const [graphReturnStep, setGraphReturnStep] = useState(1);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [validation, setValidation] = useState<DiscoverValidation | null>(null);
  const [coverage, setCoverage] = useState<CoverageResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const go = (s: number) => {
    setStep(s);
    setMaxReached((m) => Math.max(m, s));
    setView("workflow");
  };

  const openMappingGraph = (returnStep: number) => {
    setGraphReturnStep(returnStep);
    setView("mapping_graph");
  };

  const closeMappingGraph = () => {
    setStep(graphReturnStep);
    setView("workflow");
  };

  const restart = () => {
    setView("workflow");
    setStep(0);
    setMaxReached(0);
    setGraphReturnStep(1);
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
      setView("workflow");
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

  const isMappingGraph = view === "mapping_graph" && analysis;

  return (
    <>
      <header className="app-header">
        <img src="/brand/niq-logo-white.png" alt="NielsenIQ" className="logo" />
        <div className="title-block">
          <h1>
            Coverage <span className="accent-serif">Harmonization</span> Studio
          </h1>
          <span className="tagline">
            Client file to Discover recommendation to Discover upload to coverage dashboard
          </span>
        </div>
      </header>
      <div className="container">
        {!isMappingGraph && (
          <WorkflowStepper current={step} maxReached={maxReached} onNavigate={setStep} />
        )}

        {isMappingGraph && (
          <MappingGraphPage analysis={analysis} coverage={coverage} onBack={closeMappingGraph} />
        )}

        {!isMappingGraph && step === 0 && (
          <Step1ClientUpload busy={busy} error={error} onFile={handleClientFile} />
        )}
        {!isMappingGraph && step === 1 && analysis && (
          <Step2Review
            analysis={analysis}
            onContinue={() => go(2)}
            onRestart={restart}
            onOpenMappingGraph={() => openMappingGraph(1)}
          />
        )}
        {!isMappingGraph && step === 2 && analysis && (
          <Step3Recommendation analysis={analysis} onContinue={() => go(3)} />
        )}
        {!isMappingGraph && step === 3 && analysis && (
          <Step4DiscoverUpload
            validation={validation}
            busyUpload={busy && !validation?.valid}
            busyRun={busy && !!validation?.valid}
            error={error}
            onFiles={handleDiscoverFiles}
            onRunCoverage={handleRunCoverage}
          />
        )}
        {!isMappingGraph && step === 4 && coverage && analysis && (
          <Step5Dashboard
            coverage={coverage}
            analysisId={analysis.analysis_id}
            onRestart={restart}
            onOpenMappingGraph={() => openMappingGraph(4)}
          />
        )}
      </div>
    </>
  );
}
