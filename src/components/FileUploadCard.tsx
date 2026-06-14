import { useRef, useState } from "react";

interface Props {
  title: string;
  subtitle: string;
  busy: boolean;
  busyLabel: string;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
}

const ACCEPT = ".xlsx,.xls,.csv";

export default function FileUploadCard({
  title,
  subtitle,
  busy,
  busyLabel,
  multiple = false,
  onFiles,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  const pick = (files: FileList | null) => {
    if (files && files.length > 0) onFiles(Array.from(files));
  };

  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="sub">{subtitle}</p>
      {busy ? (
        <div className="dropzone">
          <span className="spinner" />
          {busyLabel}
        </div>
      ) : (
        <div
          className={drag ? "dropzone drag" : "dropzone"}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            pick(e.dataTransfer.files);
          }}
        >
          <strong>
            {multiple
              ? "Drop one or more files here or click to browse"
              : "Drop a file here or click to browse"}
          </strong>
          <div className="hint">
            Supported formats: .xlsx, .xls, .csv
            {multiple ? " — select multiple files with Ctrl+click" : ""}
          </div>
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple={multiple}
        style={{ display: "none" }}
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
