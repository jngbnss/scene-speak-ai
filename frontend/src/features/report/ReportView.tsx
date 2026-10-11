import { useEffect, useMemo, useState } from "react";

import { fetchReport, fetchReports } from "../../services/api";
import type { ReportEntry } from "../../types/messages";
import { compareMetrics, flatten, formatValue, metricInfo, type CompareRow } from "./compare";

const KIND_LABEL: Record<string, string> = {
  suite: "전체",
  dialogue: "대화",
  feedback: "피드백",
  asr: "음성인식",
};

const GROUP_LABEL: Record<string, string> = {
  dialogue: "NPC 대화 (EXP-DLG)",
  feedback: "피드백 (EXP-FB)",
  asr: "음성인식 (EXP-ASR)",
};

function entryLabel(e: ReportEntry): string {
  const when = e.created_at ? e.created_at.slice(5, 16).replace("T", " ") : e.name.slice(0, 13);
  return `${when} · ${KIND_LABEL[e.kind] ?? e.kind} · ${e.label ?? e.name}`;
}

function Bars({ row }: { row: CompareRow }) {
  const max = Math.max(Math.abs(row.old ?? 0), Math.abs(row.new ?? 0)) || 1;
  const width = (v: number | null) => `${v === null ? 0 : (Math.abs(v) / max) * 100}%`;
  return (
    <div className="bars" aria-hidden="true">
      <span className="bar bar-old" style={{ width: width(row.old) }} />
      <span className={`bar bar-new verdict-${row.verdict}`} style={{ width: width(row.new) }} />
    </div>
  );
}

/** Evaluation results side by side: pick a baseline and a candidate run. */
export function ReportView() {
  const [entries, setEntries] = useState<ReportEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [oldName, setOldName] = useState("");
  const [newName, setNewName] = useState("");
  const [files, setFiles] = useState<Record<string, Record<string, unknown>>>({});

  useEffect(() => {
    fetchReports()
      .then((list) => {
        setEntries(list);
        const suites = list.filter((e) => e.kind === "suite");
        const pool = suites.length >= 2 ? suites : list;
        setNewName(pool[0]?.name ?? "");
        setOldName(pool[1]?.name ?? "");
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    for (const name of [oldName, newName]) {
      if (!name || files[name]) continue;
      fetchReport(name)
        .then((data) => setFiles((f) => ({ ...f, [name]: data })))
        .catch((e: Error) => setError(e.message));
    }
  }, [oldName, newName, files]);

  const rows = useMemo(() => {
    const a = files[oldName];
    const b = files[newName];
    if (!a || !b) return [];
    return compareMetrics(flatten(a, oldName), flatten(b, newName), metricInfo(a, b));
  }, [files, oldName, newName]);

  if (error) return <p className="banner error">평가 결과를 불러오지 못했어요 ({error}).</p>;
  if (!entries) return <p className="muted">불러오는 중…</p>;
  if (entries.length === 0) {
    return <p className="muted">평가 결과가 없어요. evals/run.py로 먼저 측정해 주세요.</p>;
  }

  const groups = [...new Set(rows.map((r) => r.metric.split(".")[0]))];
  const a = files[oldName];
  const b = files[newName];
  const improved = rows.filter((r) => r.verdict === "개선").length;
  const worse = rows.filter((r) => r.verdict === "악화").length;

  return (
    <section className="report" aria-label="평가 리포트">
      <div className="review-head">
        <h2>평가 리포트</h2>
        <p className="muted">같은 평가 데이터로 돌린 두 결과를 비교해요. 결과 파일은 evals/results에 있어요.</p>
      </div>

      <div className="report-pick">
        <label>
          기준
          <select value={oldName} onChange={(e) => setOldName(e.target.value)}>
            {entries.map((e) => (
              <option key={e.name} value={e.name}>
                {entryLabel(e)}
              </option>
            ))}
          </select>
        </label>
        <label>
          비교
          <select value={newName} onChange={(e) => setNewName(e.target.value)}>
            {entries.map((e) => (
              <option key={e.name} value={e.name}>
                {entryLabel(e)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {a && b && (
        <p className="muted">
          {String(a.label ?? oldName)} (커밋 {String(a.git_commit ?? "?")}) → {String(b.label ?? newName)}{" "}
          (커밋 {String(b.git_commit ?? "?")}) · 개선 {improved} · 악화 {worse}
          {typeof b.note === "string" && b.note && ` · ${b.note}`}
        </p>
      )}
      {a && b && rows.length === 0 && <p className="banner neutral">두 파일에 공통 지표가 없어요.</p>}

      {groups.map((g) => (
        <article key={g} className="card report-card">
          <h3>{GROUP_LABEL[g] ?? g}</h3>
          <div className="table-wrap">
            <table className="metrics">
              <thead>
                <tr>
                  <th scope="col">지표</th>
                  <th scope="col">기준</th>
                  <th scope="col">비교</th>
                  <th scope="col">변화</th>
                  <th scope="col" className="bars-col">
                    <span className="legend legend-old">기준</span> <span className="legend legend-new">비교</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows
                  .filter((r) => r.metric.startsWith(`${g}.`))
                  .map((r) => (
                    <tr key={r.metric}>
                      <th scope="row">{r.label}</th>
                      <td>{formatValue(r.old)}</td>
                      <td>{formatValue(r.new)}</td>
                      <td className={`verdict-${r.verdict}`}>
                        {r.delta === null ? "—" : `${r.delta > 0 ? "+" : ""}${formatValue(r.delta)}`}
                        {r.changePct !== null && ` (${r.changePct > 0 ? "+" : ""}${r.changePct.toFixed(1)}%)`}
                        {(r.verdict === "개선" || r.verdict === "악화") && ` ${r.verdict}`}
                      </td>
                      <td className="bars-col">
                        <Bars row={r} />
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </article>
      ))}
    </section>
  );
}
