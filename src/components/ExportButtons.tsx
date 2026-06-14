import { exportUrls } from "../api/client";

export default function ExportButtons({
  analysisId,
  coverageId,
}: {
  analysisId: string;
  coverageId: string | null;
}) {
  return (
    <div className="card">
      <h2>Export results</h2>
      <p className="sub">CSV exports of the normalized client data, coverage output, and exceptions.</p>
      <div className="btn-row" style={{ marginTop: 4 }}>
        <a className="btn secondary" href={exportUrls.normalizedClient(analysisId)} download>
          ⬇ Normalized client data (CSV)
        </a>
        {coverageId && (
          <>
            <a className="btn secondary" href={exportUrls.coverage(coverageId)} download>
              ⬇ Coverage results (CSV)
            </a>
            <a className="btn secondary" href={exportUrls.exceptions(coverageId)} download>
              ⬇ Exception report (CSV)
            </a>
          </>
        )}
      </div>
    </div>
  );
}
