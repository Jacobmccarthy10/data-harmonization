import type { DiscoverValidation } from "../types";

export default function ValidationSummary({ result }: { result: DiscoverValidation }) {
  const multi = result.files.length > 1;
  return (
    <div className="card">
      <h2>
        Discover file validation{" "}
        {result.valid ? (
          <span className="badge green">valid</span>
        ) : (
          <span className="badge red">invalid</span>
        )}
      </h2>
      <p className="sub">
        {multi
          ? `${result.files.length} files stitched into one dataset`
          : result.file_profile.file_name}{" "}
        — {result.row_count.toLocaleString()} rows
        {result.period_start ? `, ${result.period_start} → ${result.period_end}` : ""}
      </p>

      {multi && (
        <>
          <h3>Files</h3>
          <div className="tbl-scroll" style={{ maxHeight: 200 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Status</th>
                  <th className="num">Rows</th>
                  <th>Period range</th>
                </tr>
              </thead>
              <tbody>
                {result.files.map((f) => (
                  <tr key={f.file_name}>
                    <td>{f.file_name}</td>
                    <td>
                      {f.valid ? (
                        <span className="badge green">valid</span>
                      ) : (
                        <span className="badge red">invalid</span>
                      )}
                    </td>
                    <td className="num">{f.row_count.toLocaleString()}</td>
                    <td>
                      {f.period_start ? `${f.period_start} → ${f.period_end}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {result.missing_required_fields.length > 0 && (
        <div className="banner red">
          <strong>Missing required fields</strong>
          <ul className="tight">
            {result.missing_required_fields.map((f) => (
              <li key={f}>
                <code className="field">{f}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="banner amber">
          <strong>Warnings</strong>
          <ul className="tight">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <h3>Matched fields</h3>
      <div className="tbl-scroll" style={{ maxHeight: 220 }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Canonical field</th>
              <th>Source column</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(result.matched_fields).map(([canonical, source]) => (
              <tr key={canonical}>
                <td>
                  <code className="field">{canonical}</code>
                </td>
                <td>{source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.preview.length > 0 && (
        <>
          <h3>Sample preview</h3>
          <div className="tbl-scroll" style={{ maxHeight: 240 }}>
            <table className="tbl">
              <thead>
                <tr>
                  {Object.keys(result.preview[0]).map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.preview.map((row, i) => (
                  <tr key={i}>
                    {Object.values(row).map((v, j) => (
                      <td key={j}>{v ?? "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
