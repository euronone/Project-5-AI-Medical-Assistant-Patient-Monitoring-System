"""Report service — business logic for medical reports and lab values."""

import base64
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import structlog
from flask import current_app, has_request_context
from sqlalchemy import select
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.report import LabValue, MedicalReport

# Stored uploads: backend/data/report_uploads/<report_id>.<ext>
REPORT_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "report_uploads"

_IMAGE_EXT_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".heic": "image/heic",
}

_MAX_TEXT_CONTEXT = 18_000
_MAX_IMAGE_BYTES = 3_500_000

logger = structlog.get_logger(__name__)


def _extract_json_text_from_llm(raw: str) -> str:
    """Strip markdown fences so json.loads works on gateway output."""
    s = (raw or "").strip()
    if not s:
        return s
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if m:
        return m.group(1).strip()
    return s


def _extract_pdf_text(path: Path, max_chars: int) -> str | None:
    """Extract readable text from a PDF; returns None if no text is available."""
    try:
        from pypdf import PdfReader
    except Exception:
        return None

    try:
        reader = PdfReader(str(path))
    except Exception:
        return None

    chunks: list[str] = []
    total = 0
    for page in reader.pages[:12]:
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        if not text:
            continue
        remaining = max_chars - total
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining]
        chunks.append(text)
        total += len(text)
        if total >= max_chars:
            break

    if not chunks:
        return None
    return "\n\n".join(chunks)

_ALLOWED_REPORT_EXT = frozenset({
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".txt",
    ".gif",
    ".tif",
    ".tiff",
    ".heic",
    ".bmp",
})
from app.schemas.report_schema import (
    CreateLabValueRequest,
    CreateReportRequest,
    LabValueResponse,
    ReportResponse,
)


class ReportService:
    """Handles creating, querying, and managing medical reports and lab values."""

    def create_report(
        self,
        patient_id: uuid.UUID,
        data: CreateReportRequest,
        created_by: uuid.UUID,
    ) -> ReportResponse:
        """Create a new medical report for a patient.

        Args:
            patient_id: UUID of the patient.
            data: Validated report data.
            created_by: UUID of the user creating the report.

        Returns:
            ReportResponse with the created report.
        """
        report = MedicalReport(
            patient_id=patient_id,
            report_type=data.report_type,
            title=data.title,
            content=data.content,
            file_url=data.file_url,
            file_type=data.file_type,
            status="pending",
            created_by=created_by,
        )
        db.session.add(report)
        db.session.commit()
        return self._to_response(report)

    def get_report(self, report_id: uuid.UUID) -> ReportResponse | None:
        """Get a single report by ID.

        Args:
            report_id: UUID of the report.

        Returns:
            ReportResponse if found, None otherwise.
        """
        stmt = select(MedicalReport).where(MedicalReport.id == report_id)
        report = db.session.execute(stmt).scalar_one_or_none()
        if report is None:
            return None
        return self._to_response(report)

    def get_patient_reports(
        self,
        patient_id: uuid.UUID,
        report_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReportResponse]:
        """Get reports for a patient with optional filtering.

        Args:
            patient_id: UUID of the patient.
            report_type: Optional filter by report type.
            status: Optional filter by status.
            limit: Maximum number of reports to return.
            offset: Number of reports to skip.

        Returns:
            List of ReportResponse matching the criteria.
        """
        stmt = select(MedicalReport).where(MedicalReport.patient_id == patient_id)

        if report_type:
            stmt = stmt.where(MedicalReport.report_type == report_type)
        if status:
            stmt = stmt.where(MedicalReport.status == status)

        stmt = stmt.order_by(MedicalReport.created_at.desc()).offset(offset).limit(limit)
        reports = db.session.execute(stmt).scalars().all()
        return [self._to_response(r) for r in reports]

    def ensure_report_upload_dir(self) -> Path:
        """Return upload directory, creating it if needed."""
        REPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return REPORT_UPLOAD_DIR

    def save_uploaded_file_for_report(
        self, report_id: uuid.UUID, file_storage: FileStorage
    ) -> tuple[str, str] | None:
        """Persist an uploaded file for a report. Returns (file_url, file_type) or None."""
        orig = secure_filename(file_storage.filename or "") or "upload"
        ext = Path(orig).suffix.lower()
        if ext not in _ALLOWED_REPORT_EXT:
            ext = ".bin"
        rel_name = f"{report_id}{ext}"
        dest = self.ensure_report_upload_dir() / rel_name
        file_storage.save(str(dest))
        mime = (file_storage.mimetype or ext.lstrip("."))[:20]
        return rel_name, mime

    def update_report_file_fields(
        self, report_id: uuid.UUID, file_url: str | None, file_type: str | None
    ) -> ReportResponse | None:
        """Update stored file metadata for a report."""
        stmt = select(MedicalReport).where(MedicalReport.id == report_id)
        report = db.session.execute(stmt).scalar_one_or_none()
        if report is None:
            return None
        report.file_url = file_url
        report.file_type = file_type
        db.session.commit()
        return self._to_response(report)

    def get_report_file_path(self, report_id: uuid.UUID) -> Path | None:
        """Resolve on-disk path for a user-uploaded report file, if any."""
        stmt = select(MedicalReport).where(MedicalReport.id == report_id)
        report = db.session.execute(stmt).scalar_one_or_none()
        if report is None or not report.file_url or report.file_url.startswith("http"):
            return None
        path = REPORT_UPLOAD_DIR / report.file_url
        return path if path.is_file() else None

    def delete_report(self, report_id: uuid.UUID) -> bool:
        """Delete a report by ID.

        Args:
            report_id: UUID of the report to delete.

        Returns:
            True if deleted, False if not found.
        """
        stmt = select(MedicalReport).where(MedicalReport.id == report_id)
        report = db.session.execute(stmt).scalar_one_or_none()
        if report is None:
            return False
        if report.file_url and not report.file_url.startswith("http"):
            path = REPORT_UPLOAD_DIR / report.file_url
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass
        db.session.delete(report)
        db.session.commit()
        return True

    def _build_llm_context(self, report: MedicalReport) -> tuple[str, tuple[str, str] | None]:
        """Build text context and optional (mime, base64) for vision models."""
        lines = [
            f"Report type: {report.report_type}",
            f"Title: {report.title}",
        ]
        vision: tuple[str, str] | None = None

        if report.content:
            body = report.content.strip()
            if len(body) > _MAX_TEXT_CONTEXT:
                body = body[:_MAX_TEXT_CONTEXT] + "\n…(truncated)"
            lines.append("Notes / extracted text from patient:\n" + body)

        if report.file_url and not report.file_url.startswith("http"):
            path = REPORT_UPLOAD_DIR / report.file_url
            if path.is_file():
                ext = path.suffix.lower()
                if ext == ".txt":
                    try:
                        txt = path.read_text(encoding="utf-8", errors="replace").strip()
                        if len(txt) > _MAX_TEXT_CONTEXT:
                            txt = txt[:_MAX_TEXT_CONTEXT] + "\n…(truncated)"
                        lines.append("Attached text file contents:\n" + txt)
                    except OSError:
                        lines.append("Attached text file could not be read.")
                elif ext == ".pdf":
                    pdf_text = _extract_pdf_text(path, _MAX_TEXT_CONTEXT)
                    if pdf_text:
                        lines.append("Attached PDF extracted text:\n" + pdf_text)
                    else:
                        lines.append(
                            "Attached PDF appears scanned or has no extractable text; "
                            "summarize from title/type/notes only."
                        )
                elif ext in _IMAGE_EXT_MIME:
                    try:
                        raw = path.read_bytes()
                        if len(raw) <= _MAX_IMAGE_BYTES:
                            mime = _IMAGE_EXT_MIME[ext]
                            b64 = base64.standard_b64encode(raw).decode("ascii")
                            vision = (mime, b64)
                            lines.append(
                                "An image file is attached; use the image together with the metadata above."
                            )
                        else:
                            lines.append(
                                "An image file is attached but is too large for automatic vision analysis."
                            )
                    except OSError:
                        lines.append("Attached image could not be read.")
                else:
                    lines.append(
                        f"An attached file ({ext or 'unknown'}) is stored but was not sent as text or image; "
                        "summarize from title, type, and any notes only."
                    )

        return "\n\n".join(lines), vision

    def _run_ai_analysis_on_report(
        self,
        report_id: uuid.UUID,
        api_key_override: str | None = None,
    ) -> ReportResponse | None:
        """Generate ai_summary / ai_analysis via LLM (or fallback).

        api_key_override: optional key from X-Euri-Api-Key (browser); else server EURI_API_KEY.
        """
        from app.config import BaseConfig
        from app.integrations.openai_client import OpenAIClient, OpenAIClientError

        stmt = select(MedicalReport).where(MedicalReport.id == report_id)
        report = db.session.execute(stmt).scalar_one_or_none()
        if report is None:
            return None

        now = datetime.now(timezone.utc)
        override = (api_key_override or "").strip()
        # Client key (portal) first, then server .env
        api_key = override or (os.getenv("EURI_API_KEY") or BaseConfig.EURI_API_KEY or "").strip()
        if not api_key:
            report.ai_summary = (
                "Automatic AI analysis is not available because no EURI API key was provided. "
                "Open the AI key dialog in the portal (top bar), save your EURI key, then try "
                "“Run AI analysis now” or upload again. Your report is still saved—share it with "
                "your clinician for professional interpretation."
            )
            report.ai_analysis = {"source": "fallback", "reason": "no_api_key"}
            report.status = "completed"
            report.updated_at = now
            db.session.commit()
            return self._to_response(report)

        # Fresh client per run so EURI_API_KEY from the environment is always used (singleton can be stale).
        llm_client = OpenAIClient(api_key=api_key, timeout=120)

        try:
            ctx_text, vision = self._build_llm_context(report)
            system = (
                "You assist patients in understanding medical paperwork (labs, imaging reports, visit summaries). "
                "Write at a 7th-grade reading level. Never diagnose, prescribe medication, or replace a clinician. "
                "Recommendations must be general wellness and care-navigation only (e.g. follow up with your doctor, "
                "ask your clinician about a specific finding, keep copies of results)—never urgent medical commands "
                "unless the user text clearly describes an emergency, in which case say to seek emergency care. "
                "Output one JSON object with exactly these keys: "
                "summary (string, 2-5 sentences plain-language overview), "
                "key_points (array of up to 6 short strings of important findings or themes), "
                "recommendations (array of 4-8 short actionable strings for the patient: questions to ask their doctor, "
                "lifestyle or follow-up themes that are safe and non-specific, when to contact a clinician), "
                "limitations (string: what you could not verify from the document), "
                "disclaimer (string, one sentence that this is informational only)."
            )
            user_text = (
                "Analyze the following medical report information for a patient-facing summary.\n\n" + ctx_text
            )

            messages: list[dict]
            if vision:
                mime, b64 = vision
                messages = [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        ],
                    },
                ]
            else:
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_text},
                ]

            llm_timeout = 180.0 if vision else 90.0
            # Many OpenAI-compatible gateways (EURI, etc.) reject response_format=json_object or hang.
            # Default: rely on prompt + plain JSON text. Set REPORT_AI_USE_JSON_RESPONSE_FORMAT=1 for official OpenAI.
            use_json_mode = os.getenv("REPORT_AI_USE_JSON_RESPONSE_FORMAT", "").lower() in (
                "1",
                "true",
                "yes",
            )
            fmt = {"type": "json_object"} if use_json_mode else None
            logger.info(
                "report_ai_llm_request",
                report_id=str(report_id),
                vision=bool(vision),
                json_response_format=use_json_mode,
                timeout_s=llm_timeout,
            )
            try:
                out = llm_client.chat_completion(
                    messages,
                    temperature=0.2,
                    max_tokens=1800,
                    response_format=fmt,
                    request_timeout=llm_timeout,
                )
            except OpenAIClientError as first_exc:
                # If strict JSON mode was on and the gateway rejects it, retry without response_format
                if fmt is not None:
                    logger.warning(
                        "report_ai_retry_without_json_response_format",
                        report_id=str(report_id),
                        error=str(first_exc)[:300],
                    )
                    out = llm_client.chat_completion(
                        messages,
                        temperature=0.2,
                        max_tokens=1800,
                        response_format=None,
                        request_timeout=llm_timeout,
                    )
                else:
                    raise
            raw = _extract_json_text_from_llm((out.content or "").strip())
            parsed: dict | None = None
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, dict) and isinstance(parsed.get("summary"), str):
                summary = parsed["summary"].strip()
                kps = parsed.get("key_points")
                bullets = ""
                if isinstance(kps, list) and kps:
                    bullets = "\n\nKey points:\n" + "\n".join(
                        f"• {str(x).strip()}" for x in kps[:6] if str(x).strip()
                    )
                recs = parsed.get("recommendations")
                rec_block = ""
                if isinstance(recs, list) and recs:
                    rec_block = "\n\nRecommendations:\n" + "\n".join(
                        f"• {str(x).strip()}" for x in recs[:8] if str(x).strip()
                    )
                disc = parsed.get("disclaimer")
                disc_txt = f"\n\n{disc}" if isinstance(disc, str) and disc.strip() else ""
                report.ai_summary = (summary + bullets + rec_block + disc_txt).strip()
                keep = (
                    "summary",
                    "key_points",
                    "recommendations",
                    "limitations",
                    "disclaimer",
                )
                report.ai_analysis = {k: v for k, v in parsed.items() if k in keep}
            else:
                report.ai_summary = raw or "AI returned an empty response."
                report.ai_analysis = {"source": "raw", "raw": raw[:2000]}

            report.status = "completed"
        except OpenAIClientError as e:
            report.ai_summary = (
                "AI analysis could not be completed. Your file is still stored. "
                f"Details: {str(e)[:220]}"
            )
            report.ai_analysis = {"source": "error", "message": str(e)[:800]}
            report.status = "completed"
        except Exception as e:  # pragma: no cover — defensive
            report.ai_summary = f"AI analysis failed unexpectedly: {str(e)[:200]}"
            report.ai_analysis = {"source": "error", "message": str(e)[:800]}
            report.status = "completed"

        report.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info(
            "report_ai_persisted",
            report_id=str(report_id),
            status=report.status,
            has_summary=bool((report.ai_summary or "").strip()),
        )
        return self._to_response(report)

    def enqueue_ai_analysis(
        self,
        report_id: uuid.UUID,
        api_key_override: str | None = None,
    ) -> ReportResponse | None:
        """Set status to processing and run LLM analysis in a background thread (non-blocking).

        Use after uploads so the HTTP client returns quickly while vision/LLM work continues.
        api_key_override: X-Euri-Api-Key from the client; captured in the worker closure.
        """
        stmt = select(MedicalReport).where(MedicalReport.id == report_id)
        report = db.session.execute(stmt).scalar_one_or_none()
        if report is None:
            return None
        report.status = "processing"
        report.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        db.session.refresh(report)

        client_key = (api_key_override or "").strip() or None

        # Same-request analysis (blocks HTTP until done). Use when background threads fail on SQLite/dev.
        sync = os.getenv("REPORT_AI_SYNC", "").lower() in ("1", "true", "yes")
        if sync:
            return self._run_ai_analysis_on_report(report_id, api_key_override=client_key)

        if not has_request_context():
            return self._run_ai_analysis_on_report(report_id, api_key_override=client_key)

        app = current_app._get_current_object()

        def worker() -> None:
            with app.app_context():
                db.session.remove()
                try:
                    self._run_ai_analysis_on_report(report_id, api_key_override=client_key)
                except Exception:
                    logger.exception(
                        "background_report_analysis_failed",
                        report_id=str(report_id),
                    )
                    try:
                        stmt = select(MedicalReport).where(MedicalReport.id == report_id)
                        r2 = db.session.execute(stmt).scalar_one_or_none()
                        if r2 is not None and r2.status == "processing":
                            r2.ai_summary = (
                                "AI analysis stopped due to a server error. Your file is still saved—"
                                "refresh this page later or contact support if it persists."
                            )
                            r2.ai_analysis = {
                                "source": "error",
                                "message": "Background analysis failed",
                            }
                            r2.status = "completed"
                            r2.updated_at = datetime.now(timezone.utc)
                            db.session.commit()
                    except Exception:
                        logger.exception(
                            "background_report_analysis_recovery_failed",
                            report_id=str(report_id),
                        )
                        db.session.rollback()

        # daemon=False so analysis is not dropped when the dev server replaces worker processes
        threading.Thread(target=worker, daemon=False, name=f"report-ai-{report_id}").start()
        return self._to_response(report)

    def trigger_analysis(
        self,
        report_id: uuid.UUID,
        api_key_override: str | None = None,
    ) -> ReportResponse | None:
        """Mark report as processing, run LLM analysis, then persist summary (or fallback).

        Args:
            report_id: UUID of the report.
            api_key_override: optional X-Euri-Api-Key from the client.

        Returns:
            Updated ReportResponse, or None if not found.
        """
        stmt = select(MedicalReport).where(MedicalReport.id == report_id)
        report = db.session.execute(stmt).scalar_one_or_none()
        if report is None:
            return None
        report.status = "processing"
        report.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        client_key = (api_key_override or "").strip() or None
        return self._run_ai_analysis_on_report(report_id, api_key_override=client_key)

    def add_lab_value(
        self,
        report_id: uuid.UUID,
        patient_id: uuid.UUID,
        data: CreateLabValueRequest,
    ) -> LabValueResponse:
        """Add a lab value to a report.

        Args:
            report_id: UUID of the report.
            patient_id: UUID of the patient.
            data: Validated lab value data.

        Returns:
            LabValueResponse with the created lab value.
        """
        lab_value = LabValue(
            report_id=report_id,
            patient_id=patient_id,
            test_name=data.test_name,
            value=Decimal(str(data.value)) if data.value is not None else None,
            unit=data.unit,
            reference_min=Decimal(str(data.reference_min)) if data.reference_min is not None else None,
            reference_max=Decimal(str(data.reference_max)) if data.reference_max is not None else None,
            is_abnormal=data.is_abnormal,
            loinc_code=data.loinc_code,
            collected_at=data.collected_at,
        )
        db.session.add(lab_value)
        db.session.commit()
        return self._lab_to_response(lab_value)

    def get_report_lab_values(self, report_id: uuid.UUID) -> list[LabValueResponse]:
        """Get all lab values for a report.

        Args:
            report_id: UUID of the report.

        Returns:
            List of LabValueResponse for the report.
        """
        stmt = (
            select(LabValue)
            .where(LabValue.report_id == report_id)
            .order_by(LabValue.created_at.asc())
        )
        lab_values = db.session.execute(stmt).scalars().all()
        return [self._lab_to_response(lv) for lv in lab_values]

    def _to_response(self, report: MedicalReport) -> ReportResponse:
        """Convert a MedicalReport model to a ReportResponse schema."""
        return ReportResponse(
            id=str(report.id),
            patient_id=str(report.patient_id),
            report_type=report.report_type,
            title=report.title,
            content=report.content,
            file_url=report.file_url,
            file_type=report.file_type,
            ai_summary=report.ai_summary,
            ai_analysis=report.ai_analysis,
            status=report.status,
            reviewed_by=str(report.reviewed_by) if report.reviewed_by else None,
            reviewed_at=report.reviewed_at,
            created_by=str(report.created_by),
            created_at=report.created_at,
            updated_at=report.updated_at,
        )

    def _lab_to_response(self, lab_value: LabValue) -> LabValueResponse:
        """Convert a LabValue model to a LabValueResponse schema."""
        return LabValueResponse(
            id=str(lab_value.id),
            report_id=str(lab_value.report_id),
            patient_id=str(lab_value.patient_id),
            test_name=lab_value.test_name,
            value=float(lab_value.value) if lab_value.value is not None else None,
            unit=lab_value.unit,
            reference_min=float(lab_value.reference_min) if lab_value.reference_min is not None else None,
            reference_max=float(lab_value.reference_max) if lab_value.reference_max is not None else None,
            is_abnormal=lab_value.is_abnormal,
            loinc_code=lab_value.loinc_code,
            collected_at=lab_value.collected_at,
            created_at=lab_value.created_at,
        )


# Module-level instance for use by routes
report_service = ReportService()
