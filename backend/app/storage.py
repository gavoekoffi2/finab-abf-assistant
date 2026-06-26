from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .schemas import AdvisorReview, ProspectSubmission

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "finab_abf.sqlite3"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prospects (
            id TEXT PRIMARY KEY,
            advisor_slug TEXT NOT NULL,
            client_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS abf_documents (
            id TEXT PRIMARY KEY,
            prospect_id TEXT NOT NULL,
            output_path TEXT NOT NULL,
            report_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(prospect_id) REFERENCES prospects(id)
        )
        """
    )
    conn.commit()
    return conn


def create_prospect(advisor_slug: str, prospect: ProspectSubmission) -> dict:
    conn = connect()
    pid = uuid4().hex
    ts = now_iso()
    payload = prospect.model_dump(mode="json")
    conn.execute(
        """
        INSERT INTO prospects (id, advisor_slug, client_name, phone, email, status, payload_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pid,
            advisor_slug,
            prospect.identity.full_name,
            prospect.contact.phone,
            prospect.contact.email,
            "new",
            json.dumps(payload, ensure_ascii=False),
            ts,
            ts,
        ),
    )
    conn.commit()
    return get_prospect(pid)


def list_prospects(advisor_slug: str | None = None) -> list[dict]:
    conn = connect()
    if advisor_slug:
        rows = conn.execute(
            "SELECT * FROM prospects WHERE advisor_slug=? ORDER BY created_at DESC", (advisor_slug,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM prospects ORDER BY created_at DESC").fetchall()
    return [_row_to_prospect(row, include_payload=False) for row in rows]


def get_prospect(prospect_id: str) -> dict:
    conn = connect()
    row = conn.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if not row:
        raise KeyError(prospect_id)
    return _row_to_prospect(row, include_payload=True)


def prospect_submission(prospect_id: str) -> ProspectSubmission:
    record = get_prospect(prospect_id)
    return ProspectSubmission.model_validate(record["payload"])


def update_status(prospect_id: str, status: str) -> None:
    conn = connect()
    conn.execute(
        "UPDATE prospects SET status=?, updated_at=? WHERE id=?",
        (status, now_iso(), prospect_id),
    )
    conn.commit()


def save_abf_document(prospect_id: str, output_path: str, report: dict) -> dict:
    conn = connect()
    doc_id = uuid4().hex
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO abf_documents (id, prospect_id, output_path, report_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (doc_id, prospect_id, output_path, json.dumps(report, ensure_ascii=False), ts),
    )
    conn.commit()
    update_status(prospect_id, "abf_generated")
    return {"id": doc_id, "prospect_id": prospect_id, "output_path": output_path, "report": report, "created_at": ts}


def list_documents(prospect_id: str) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM abf_documents WHERE prospect_id=? ORDER BY created_at DESC", (prospect_id,)
    ).fetchall()
    return [
        {
            "id": row["id"],
            "prospect_id": row["prospect_id"],
            "output_path": row["output_path"],
            "report": json.loads(row["report_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def default_review(prospect: ProspectSubmission) -> AdvisorReview:
    return AdvisorReview(
        reviewed_by_advisor=True,
        replacement_years=10,
        final_recommended_coverage=0,
        recommendation_1_budget=prospect.goals.acceptable_monthly_budget,
        recommendation_2_budget=prospect.goals.acceptable_monthly_budget * 1.5,
        client_preference_budget=prospect.goals.acceptable_monthly_budget,
    )


def _row_to_prospect(row: sqlite3.Row, include_payload: bool) -> dict:
    data = {
        "id": row["id"],
        "advisor_slug": row["advisor_slug"],
        "client_name": row["client_name"],
        "phone": row["phone"],
        "email": row["email"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_payload:
        data["payload"] = json.loads(row["payload_json"])
    return data
