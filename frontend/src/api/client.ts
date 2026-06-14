import type { AnalysisResponse, CoverageResponse, DiscoverValidation } from "../types";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function analyzeClientFile(file: File): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/client/analyze", { method: "POST", body: form });
  return handle<AnalysisResponse>(res);
}

export async function validateDiscoverFiles(
  analysisId: string,
  files: File[],
): Promise<DiscoverValidation> {
  const form = new FormData();
  form.append("analysis_id", analysisId);
  for (const file of files) form.append("files", file);
  const res = await fetch("/api/discover/validate", { method: "POST", body: form });
  return handle<DiscoverValidation>(res);
}

export async function runCoverage(
  analysisId: string,
  discoverId: string,
): Promise<CoverageResponse> {
  const res = await fetch("/api/coverage/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId, discover_id: discoverId }),
  });
  return handle<CoverageResponse>(res);
}

export const exportUrls = {
  normalizedClient: (analysisId: string) => `/api/export/normalized-client/${analysisId}`,
  coverage: (coverageId: string) => `/api/export/coverage/${coverageId}`,
  exceptions: (coverageId: string) => `/api/export/exceptions/${coverageId}`,
};
