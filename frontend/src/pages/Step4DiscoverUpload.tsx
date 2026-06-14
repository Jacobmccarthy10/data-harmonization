import FileUploadCard from "../components/FileUploadCard";
import ValidationSummary from "../components/ValidationSummary";
import type { DiscoverValidation } from "../types";

interface Props {
  validation: DiscoverValidation | null;
  busyUpload: boolean;
  busyRun: boolean;
  error: string | null;
  onFiles: (files: File[]) => void;
  onRunCoverage: () => void;
}

export default function Step4DiscoverUpload({
  validation,
  busyUpload,
  busyRun,
  error,
  onFiles,
  onRunCoverage,
}: Props) {
  return (
    <>
      <FileUploadCard
        title="Step 4 — Upload the Discover export"
        subtitle="Upload the clean Discover export matching the recommended pull. If Discover's export cell limit forced you to split the pull into 2-3 files (e.g. by period or category), select all of them — they are validated individually and stitched into one dataset. Light field-name tolerance is applied (e.g. “$ Sales” → dollar_sales), but the files are expected to be clean — this is not another harmonization step."
        busy={busyUpload}
        busyLabel="Validating and stitching Discover export(s)…"
        multiple
        onFiles={onFiles}
      />
      {error && <div className="error-box">{error}</div>}
      {validation && <ValidationSummary result={validation} />}
      {validation?.valid && (
        <div className="btn-row">
          <button className="btn" onClick={onRunCoverage} disabled={busyRun}>
            {busyRun ? "Running coverage comparison…" : "Run coverage comparison →"}
          </button>
        </div>
      )}
    </>
  );
}
