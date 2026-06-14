import FileUploadCard from "../components/FileUploadCard";

interface Props {
  busy: boolean;
  error: string | null;
  onFile: (file: File) => void;
}

export default function Step1ClientUpload({ busy, error, onFile }: Props) {
  return (
    <>
      <FileUploadCard
        title="Step 1 — Upload a client file"
        subtitle="Start with the messy client export: shipment, POS, or retail data in Excel or CSV. The app will detect its structure, standardize it into NIQ-compatible concepts, and recommend the Discover pull to run."
        busy={busy}
        busyLabel="Analyzing client file — detecting structure, mapping columns, normalizing periods and metrics…"
        onFiles={(files) => onFile(files[0])}
      />
      {error && <div className="error-box">{error}</div>}
      <div className="card">
        <h2>How this works</h2>
        <ul className="tight">
          <li>Upload one client file per workflow (multi-sheet workbooks supported — the first sheet with meaningful tabular data is used).</li>
          <li>The app detects period fields, product identifiers, customer/market fields, and metrics generically — no client-specific templates.</li>
          <li>You then get a recommended Discover pull. Export it from Discover and upload it here to run the coverage comparison.</li>
          <li>The Discover export is expected to be clean and close to the recommended pull.</li>
        </ul>
      </div>
    </>
  );
}
