"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import apiClient from "@/lib/api-client";

interface MedicalReport {
  id: string;
  report_type: string;
  title: string;
  content: string | null;
  file_url: string | null;
  file_type: string | null;
  ai_summary: string | null;
  ai_analysis: Record<string, unknown> | null;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  created_by: string;
}

const reportTypeBadge: Record<string, string> = {
  lab: "bg-blue-100 text-blue-700",
  imaging: "bg-purple-100 text-purple-700",
  pathology: "bg-red-100 text-red-700",
  radiology: "bg-indigo-100 text-indigo-700",
  discharge: "bg-gray-100 text-gray-700",
  consultation: "bg-teal-100 text-teal-700",
  progress: "bg-green-100 text-green-700",
  other: "bg-gray-100 text-gray-700",
};

const statusBadge: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  processing: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  reviewed: "bg-green-100 text-green-700",
};

const REPORT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "lab", label: "Lab results" },
  { value: "imaging", label: "Imaging" },
  { value: "pathology", label: "Pathology" },
  { value: "radiology", label: "Radiology" },
  { value: "discharge", label: "Discharge summary" },
  { value: "consultation", label: "Consultation" },
  { value: "progress", label: "Progress note" },
  { value: "other", label: "Other" },
];

function asStringList(val: unknown): string[] {
  if (!Array.isArray(val)) return [];
  return val.map((x) => String(x).trim()).filter(Boolean);
}

/** Renders LLM output: summary, key points, recommendations, limitations (patient-friendly). */
function ReportAiPatientView({ report }: { report: MedicalReport }) {
  const a = report.ai_analysis;
  const obj = a && typeof a === "object" ? (a as Record<string, unknown>) : null;
  const src = obj?.source;
  const hasStructuredSummary =
    obj &&
    typeof obj.summary === "string" &&
    String(obj.summary).trim().length > 0 &&
    src !== "error" &&
    src !== "raw" &&
    src !== "fallback";

  if (hasStructuredSummary) {
    const summary = String(obj!.summary).trim();
    const keyPoints = asStringList(obj!.key_points);
    const recommendations = asStringList(obj!.recommendations);
    const limitations =
      typeof obj!.limitations === "string" ? obj!.limitations.trim() : "";
    const disclaimer =
      typeof obj!.disclaimer === "string" ? obj!.disclaimer.trim() : "";

    return (
      <div className="space-y-4">
        <section>
          <h4 className="text-sm font-semibold text-foreground">Summary</h4>
          <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">{summary}</p>
        </section>
        {keyPoints.length > 0 && (
          <section>
            <h4 className="text-sm font-semibold text-foreground">Key points</h4>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {keyPoints.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        )}
        {recommendations.length > 0 && (
          <section>
            <h4 className="text-sm font-semibold text-foreground">Recommendations</h4>
            <p className="mt-0.5 text-xs text-muted-foreground">
              General guidance only—not a diagnosis. Discuss with your clinician.
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {recommendations.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        )}
        {limitations && (
          <section>
            <h4 className="text-sm font-semibold text-foreground">Limitations</h4>
            <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">{limitations}</p>
          </section>
        )}
        {disclaimer && (
          <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            {disclaimer}
          </p>
        )}
      </div>
    );
  }

  if (report.ai_summary) {
    return (
      <section>
        <h4 className="text-sm font-semibold text-foreground">AI summary</h4>
        <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">{report.ai_summary}</p>
      </section>
    );
  }

  if (obj && src === "error" && typeof obj.message === "string" && obj.message.trim()) {
    return (
      <section>
        <h4 className="text-sm font-semibold text-foreground">AI analysis</h4>
        <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">{String(obj.message).trim()}</p>
      </section>
    );
  }

  return null;
}

/** True when the API has something meaningful to show (not an empty analysis placeholder). */
function hasDisplayableAiContent(r: MedicalReport): boolean {
  if (r.ai_summary && String(r.ai_summary).trim()) return true;
  const a = r.ai_analysis;
  if (!a || typeof a !== "object") return false;
  const o = a as Record<string, unknown>;
  if (typeof o.summary === "string" && o.summary.trim()) return true;
  if (o.source === "error" && (typeof o.message === "string" || r.ai_summary)) return true;
  if (o.source === "raw") return true;
  if (o.source === "fallback") return true;
  return false;
}

function getPatientIdFromStorage(): string | null {
  const userStr = localStorage.getItem("user");
  if (!userStr) return null;
  try {
    const user = JSON.parse(userStr) as { id?: string; patient_id?: string };
    return user.id ?? user.patient_id ?? null;
  } catch {
    return null;
  }
}

function pickStr(obj: Record<string, unknown>, ...keys: string[]): string | null {
  for (const k of keys) {
    const v = obj[k];
    if (v != null && typeof v === "string") return v;
  }
  return null;
}

/** Normalize list item (snake_case or accidental camelCase from proxies). */
function normalizeReport(raw: unknown): MedicalReport {
  const r = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const status = String(pickStr(r, "status", "Status") ?? "pending").toLowerCase();
  const aiRaw = r.ai_analysis ?? r.aiAnalysis;
  const ai_analysis =
    aiRaw && typeof aiRaw === "object" && !Array.isArray(aiRaw)
      ? (aiRaw as Record<string, unknown>)
      : null;

  return {
    id: String(r.id ?? ""),
    report_type: String(pickStr(r, "report_type", "reportType") ?? "other"),
    title: String(pickStr(r, "title") ?? ""),
    content: pickStr(r, "content"),
    file_url: pickStr(r, "file_url", "fileUrl"),
    file_type: pickStr(r, "file_type", "fileType"),
    ai_summary: pickStr(r, "ai_summary", "aiSummary"),
    ai_analysis,
    status,
    reviewed_by: pickStr(r, "reviewed_by", "reviewedBy"),
    reviewed_at: pickStr(r, "reviewed_at", "reviewedAt"),
    created_at: String(pickStr(r, "created_at", "createdAt") ?? ""),
    created_by: String(pickStr(r, "created_by", "createdBy") ?? ""),
  };
}

export default function ReportsPage() {
  const [reports, setReports] = useState<MedicalReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadReportType, setUploadReportType] = useState("lab");
  const [uploadNotes, setUploadNotes] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [listRefreshing, setListRefreshing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [analysisRetryId, setAnalysisRetryId] = useState<string | null>(null);

  /** Poll while the server has not yet written AI output (pending or processing). */
  const needsAnalysisPolling = useMemo(
    () =>
      reports.some(
        (r) =>
          !hasDisplayableAiContent(r) &&
          (r.status === "processing" || r.status === "pending")
      ),
    [reports]
  );

  const fetchReports = useCallback(async () => {
    try {
      const patientId = getPatientIdFromStorage();
      if (!patientId) {
        setError("User not found. Please log in again.");
        setLoading(false);
        return;
      }

      const res = await apiClient.get(`/reports/${patientId}`, { timeout: 60_000 });
      setError(null);
      const data = res.data?.reports ?? res.data;
      setReports(Array.isArray(data) ? data.map(normalizeReport) : []);
    } catch (err: unknown) {
      const status =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      if (status === 404) {
        setReports([]);
      } else {
        setError("Failed to load medical reports.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  /** Refetch when returning to the tab (polling may have stopped while in background). */
  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "visible") void fetchReports();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [fetchReports]);

  /** LLM analysis can take minutes; poll until completed or cap (matches backend vision timeout). */
  const pollStartRef = useRef<number | null>(null);
  useEffect(() => {
    if (!needsAnalysisPolling) {
      pollStartRef.current = null;
      return;
    }
    if (pollStartRef.current === null) {
      pollStartRef.current = Date.now();
    }
    const maxMs = 10 * 60 * 1000;
    const intervalMs = 4000;
    const id = window.setInterval(() => {
      if (pollStartRef.current !== null && Date.now() - pollStartRef.current > maxMs) {
        window.clearInterval(id);
        return;
      }
      void fetchReports();
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [needsAnalysisPolling, fetchReports]);

  const parseApiErrorMessage = (data: unknown): string | null => {
    if (!data || typeof data !== "object" || !("error" in data)) return null;
    const err = (data as { error: Record<string, unknown> }).error;
    if (typeof err.message === "string") return err.message;
    if (Array.isArray(err.details)) {
      return (err.details as { msg?: string }[])
        .map((d) => d.msg)
        .filter(Boolean)
        .join(" ");
    }
    return null;
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploadError(null);
    setUploadSuccess(null);

    const patientId = getPatientIdFromStorage();
    if (!patientId) {
      setUploadError("Please log in again.");
      return;
    }
    if (!uploadTitle.trim()) {
      setUploadError("Please enter a report title.");
      return;
    }

    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("title", uploadTitle.trim());
      fd.append("report_type", uploadReportType);
      if (uploadNotes.trim()) {
        fd.append("content", uploadNotes.trim());
      }
      if (uploadFile) {
        fd.append("file", uploadFile);
      }

      await apiClient.post(`/reports/${patientId}/upload`, fd, { timeout: 240_000 });

      setUploadSuccess(
        "Report saved. AI analysis is running in the background—expand the report or refresh in a few seconds for results."
      );
      setUploadTitle("");
      setUploadReportType("lab");
      setUploadNotes("");
      setUploadFile(null);
      await fetchReports();
      [2000, 8000, 20000, 45000].forEach((ms) => {
        window.setTimeout(() => {
          void fetchReports();
        }, ms);
      });
    } catch (err: unknown) {
      let msg = "Upload failed. Please try again.";
      if (
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { data?: unknown } }).response?.data
      ) {
        const parsed = parseApiErrorMessage(
          (err as { response: { data: unknown } }).response.data
        );
        if (parsed) msg = parsed;
      }
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadFile = async (report: MedicalReport) => {
    setActionError(null);
    const patientId = getPatientIdFromStorage();
    if (!patientId) return;
    if (!report.file_url) return;

    if (report.file_url.startsWith("http")) {
      window.open(report.file_url, "_blank", "noopener,noreferrer");
      return;
    }

    setDownloadingId(report.id);
    try {
      const res = await apiClient.get(
        `/reports/${patientId}/${report.id}/file`,
        { responseType: "blob" }
      );
      const blob = res.data as Blob;
      const cd = res.headers["content-disposition"] as string | undefined;
      let filename = `${report.title.slice(0, 60) || "report"}.pdf`;
      if (cd) {
        const match = /filename\*?=(?:UTF-8'')?("?)([^";]+)\1/.exec(cd);
        if (match?.[2]) {
          try {
            filename = decodeURIComponent(match[2].replace(/['"]/g, ""));
          } catch {
            filename = match[2].replace(/['"]/g, "");
          }
        }
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setActionError("Could not download the file. Try again later.");
    } finally {
      setDownloadingId(null);
    }
  };

  /** Text-only or notes-only reports: download title, notes, and AI summary as .txt */
  const downloadTextExport = (report: MedicalReport) => {
    setActionError(null);
    const lines: string[] = [
      report.title,
      `Type: ${report.report_type}`,
      `Saved: ${new Date(report.created_at).toLocaleString()}`,
      "",
    ];
    if (report.content?.trim()) {
      lines.push("Notes", report.content.trim(), "");
    }
    if (report.ai_summary?.trim()) {
      lines.push("--- AI summary ---", "", report.ai_summary.trim());
    }
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const safe = `${report.title.slice(0, 80).replace(/[/\\?%*:|"<>]/g, "-") || "report"}.txt`;
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = safe;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  };

  const handleDeleteReport = async (report: MedicalReport) => {
    if (
      !window.confirm(
        `Delete "${report.title}"? This removes the report and any attached file from your account. This cannot be undone.`
      )
    ) {
      return;
    }
    setActionError(null);
    const patientId = getPatientIdFromStorage();
    if (!patientId) {
      setActionError("Please log in again.");
      return;
    }
    setDeletingId(report.id);
    try {
      await apiClient.delete(`/reports/${patientId}/${report.id}`);
      if (expandedId === report.id) {
        setExpandedId(null);
      }
      await fetchReports();
    } catch {
      setActionError("Could not delete the report. Try again.");
    } finally {
      setDeletingId(null);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const handleRefreshList = async () => {
    setListRefreshing(true);
    try {
      await fetchReports();
    } finally {
      setListRefreshing(false);
    }
  };

  /** Runs analysis synchronously on the server (can take several minutes). */
  const handleRetryAnalysis = async (report: MedicalReport) => {
    const patientId = getPatientIdFromStorage();
    if (!patientId) {
      setActionError("Please log in again.");
      return;
    }
    setActionError(null);
    setAnalysisRetryId(report.id);
    try {
      await apiClient.post(`/reports/${patientId}/${report.id}/analyze`, {}, { timeout: 240_000 });
      await fetchReports();
    } catch {
      setActionError(
        "Analysis did not complete. Ensure the backend has EURI_API_KEY set, then try again or contact support."
      );
    } finally {
      setAnalysisRetryId(null);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-foreground">Medical Reports</h1>
          <p className="mt-1 text-muted-foreground">
            View your medical reports and AI-generated analysis summaries.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
          <span className="text-sm text-muted-foreground">
            {reports.length} report{reports.length !== 1 ? "s" : ""}
          </span>
          <button
            type="button"
            onClick={() => void handleRefreshList()}
            disabled={listRefreshing || loading}
            className="rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {listRefreshing ? "Refreshing…" : "Refresh list"}
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Upload a report</h2>
        <form onSubmit={handleUploadSubmit} className="mt-4 space-y-4">
          {uploadSuccess && (
            <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-800 dark:bg-green-950/40 dark:text-green-200">
              {uploadSuccess}
            </p>
          )}
          {uploadError && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{uploadError}</p>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="upload-title" className="text-sm font-medium text-foreground">
                Title <span className="text-destructive">*</span>
              </label>
              <input
                id="upload-title"
                type="text"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                placeholder="e.g. Annual blood panel — March 2026"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="upload-type" className="text-sm font-medium text-foreground">
                Report type
              </label>
              <select
                id="upload-type"
                value={uploadReportType}
                onChange={(e) => setUploadReportType(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {REPORT_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <label htmlFor="upload-notes" className="text-sm font-medium text-foreground">
              Notes <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <textarea
              id="upload-notes"
              value={uploadNotes}
              onChange={(e) => setUploadNotes(e.target.value)}
              rows={3}
              placeholder="Anything your care team should know about this document"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="space-y-2">
            <input
              id="upload-file"
              type="file"
              aria-label="Attach report document"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.gif,.tif,.tiff,.heic,.bmp,application/pdf,image/*"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-primary-foreground"
            />
            {uploadFile && (
              <p className="text-xs text-muted-foreground">Selected: {uploadFile.name}</p>
            )}
          </div>
          <button
            type="submit"
            disabled={uploading}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading ? "Uploading & analyzing…" : "Submit report"}
          </button>
        </form>
      </div>

      {loading ? (
        <div className="rounded-lg border border-border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">Loading reports...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-border bg-card p-12 text-center">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      ) : reports.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
          <div className="flex flex-col items-center justify-center py-12">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <span className="text-2xl font-bold text-muted-foreground">R</span>
            </div>
            <h3 className="mt-4 text-lg font-semibold text-foreground">No Reports Yet</h3>
            <p className="mt-2 max-w-sm text-center text-sm text-muted-foreground">
              Your medical reports and lab results will appear here once uploaded. AI-powered
              analysis will provide plain-language summaries of your results.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/20 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              After uploading, open a report and use <strong className="font-medium text-foreground">Run AI analysis now</strong> if the status stays
              pending or processing.
            </p>
            <button
              type="button"
              onClick={() => void handleRefreshList()}
              disabled={listRefreshing || loading}
              className="shrink-0 self-start rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-50 sm:self-auto"
            >
              {listRefreshing ? "Refreshing…" : "Refresh list"}
            </button>
          </div>
          {actionError && (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {actionError}
            </p>
          )}
          {reports.map((report) => {
            const canDownloadFile = Boolean(report.file_url);
            const canDownloadText =
              !canDownloadFile &&
              Boolean(
                (report.content && report.content.trim()) ||
                  (report.ai_summary && report.ai_summary.trim())
              );

            return (
            <div
              key={report.id}
              className="rounded-lg border border-border bg-card shadow-sm"
            >
              <div className="flex items-stretch">
                <button
                  type="button"
                  onClick={() => toggleExpand(report.id)}
                  className="flex min-w-0 flex-1 items-center justify-between px-4 py-4 text-left hover:bg-muted/30 transition-colors sm:px-6"
                >
                  <div className="flex min-w-0 items-center gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted">
                      <span className="text-sm font-bold text-muted-foreground">
                        {report.report_type.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-foreground">{report.title}</h3>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            reportTypeBadge[report.report_type] ?? reportTypeBadge.other
                          }`}
                        >
                          {report.report_type}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {new Date(report.created_at).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                        })}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 pl-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        statusBadge[report.status] ?? "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {report.status}
                    </span>
                    <span className="text-muted-foreground" aria-hidden>
                      {expandedId === report.id ? "\u25B2" : "\u25BC"}
                    </span>
                  </div>
                </button>

                <div
                  className="flex shrink-0 flex-col justify-center gap-1 border-l border-border py-2 pl-2 pr-3 sm:flex-row sm:items-center sm:gap-2 sm:pr-4"
                  role="group"
                  aria-label="Report actions"
                >
                  {canDownloadFile && (
                    <button
                      type="button"
                      onClick={() => void handleDownloadFile(report)}
                      disabled={downloadingId === report.id}
                      aria-label={
                        report.file_url?.startsWith("http")
                          ? `Open attached file for ${report.title}`
                          : `Download file for ${report.title}`
                      }
                      className="whitespace-nowrap rounded-md px-2 py-1.5 text-xs font-medium text-primary hover:bg-muted/80 disabled:cursor-not-allowed disabled:opacity-50 sm:text-sm"
                    >
                      {downloadingId === report.id
                        ? "…"
                        : report.file_url?.startsWith("http")
                          ? "Open file"
                          : "Download"}
                    </button>
                  )}
                  {canDownloadText && (
                    <button
                      type="button"
                      onClick={() => downloadTextExport(report)}
                      aria-label={`Download notes and summary as text for ${report.title}`}
                      className="whitespace-nowrap rounded-md px-2 py-1.5 text-xs font-medium text-primary hover:bg-muted/80 sm:text-sm"
                    >
                      Download text
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleDeleteReport(report)}
                    disabled={deletingId === report.id}
                    aria-label={`Delete report ${report.title}`}
                    className="whitespace-nowrap rounded-md px-2 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-50 sm:text-sm"
                  >
                    {deletingId === report.id ? "…" : "Delete"}
                  </button>
                </div>
              </div>

              {expandedId === report.id && (
                <div className="border-t border-border px-6 py-4">
                  {hasDisplayableAiContent(report) ? (
                    <ReportAiPatientView report={report} />
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm text-muted-foreground italic">
                        {report.status === "pending" || report.status === "processing"
                          ? "AI analysis usually finishes in a few minutes. If it stays stuck, refresh the list or run analysis again from here."
                          : "No AI analysis available for this report."}
                      </p>
                      {(report.status === "pending" || report.status === "processing") && (
                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={() => void handleRetryAnalysis(report)}
                            disabled={analysisRetryId === report.id}
                            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {analysisRetryId === report.id ? "Running analysis…" : "Run AI analysis now"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleRefreshList()}
                            disabled={listRefreshing}
                            className="rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted/50 disabled:opacity-50"
                          >
                            Refresh list
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {report.content && (
                    <div className="mt-3">
                      <h4 className="text-sm font-medium text-foreground">Report Content</h4>
                      <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">
                        {report.content}
                      </p>
                    </div>
                  )}

                  {report.reviewed_by && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Reviewed on{" "}
                      {report.reviewed_at
                        ? new Date(report.reviewed_at).toLocaleDateString()
                        : "N/A"}
                    </p>
                  )}
                </div>
              )}
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
