from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .schemas import AdvisorReview, ProspectSubmission

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "finab_abf.sqlite3"
SESSION_HOURS = 24 * 14
PLAN_PRICE_USD = 199
TRIAL_DAYS = 3
PAID_STATUSES = {"active", "trialing"}

DEFAULT_ORG = {
    "name": "FINAB Solution",
    "slug": "finab",
    "advisor_name": "KOFFI ABRAHAM AKPOBI",
    "advisor_phone": "4383345252",
    "advisor_email": "KOFFI.AKPOBI@MYGREATWAY.CA",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = _hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(candidate, digest)


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            advisor_name TEXT NOT NULL,
            advisor_phone TEXT,
            advisor_email TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'advisor',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(organization_id) REFERENCES organizations(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prospects (
            id TEXT PRIMARY KEY,
            organization_id TEXT,
            advisor_slug TEXT NOT NULL,
            client_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(organization_id) REFERENCES organizations(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS abf_documents (
            id TEXT PRIMARY KEY,
            prospect_id TEXT NOT NULL,
            organization_id TEXT,
            output_path TEXT NOT NULL,
            report_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(prospect_id) REFERENCES prospects(id),
            FOREIGN KEY(organization_id) REFERENCES organizations(id)
        )
        """
    )
    _ensure_column(conn, "prospects", "organization_id", "TEXT")
    _ensure_column(conn, "abf_documents", "organization_id", "TEXT")
    _ensure_column(conn, "users", "is_active", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "users", "plan", "TEXT NOT NULL DEFAULT 'finab_pro'")
    _ensure_column(conn, "users", "subscription_status", "TEXT NOT NULL DEFAULT 'incomplete'")
    _ensure_column(conn, "users", "trial_ends_at", "TEXT")
    _ensure_column(conn, "users", "current_period_end", "TEXT")
    _ensure_column(conn, "users", "stripe_customer_id", "TEXT")
    _ensure_column(conn, "users", "stripe_subscription_id", "TEXT")
    _ensure_column(conn, "users", "last_payment_status", "TEXT")
    conn.commit()
    _bootstrap_default_account(conn)
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    base = base.strip("-") or "finab-client"
    return base[:48]


def _unique_slug(conn: sqlite3.Connection, value: str) -> str:
    slug = _slugify(value)
    candidate = slug
    counter = 2
    while conn.execute("SELECT id FROM organizations WHERE slug=?", (candidate,)).fetchone():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _require_owner(user: dict) -> None:
    if user.get("role") != "owner":
        raise PermissionError("Accès super administrateur requis")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _subscription_state(row: sqlite3.Row | dict) -> dict:
    role = row["role"]
    plan = row["plan"] or "finab_pro"
    status = row["subscription_status"] or "incomplete"
    trial_end = _parse_dt(row["trial_ends_at"])
    period_end = _parse_dt(row["current_period_end"])
    now = datetime.now(timezone.utc)
    is_owner = role == "owner"
    in_trial = status == "trialing" and bool(trial_end and trial_end > now)
    active_paid = plan != "free" and status == "active" and (period_end is None or period_end > now)
    has_access = is_owner or in_trial or active_paid
    return {
        "plan": plan,
        "status": "owner_access" if is_owner else status,
        "effective_status": "active" if has_access else "inactive",
        "access_label": _access_label(is_owner, plan, status, period_end, now),
        "has_access": has_access,
        "in_trial": in_trial,
        "trial_ends_at": row["trial_ends_at"],
        "current_period_end": row["current_period_end"],
        "stripe_customer_id": row["stripe_customer_id"],
        "stripe_subscription_id": row["stripe_subscription_id"],
        "last_payment_status": row["last_payment_status"],
        "price_usd": PLAN_PRICE_USD,
        "trial_days": TRIAL_DAYS,
    }


def _access_label(is_owner: bool, plan: str, status: str, period_end: datetime | None, now: datetime) -> str:
    if is_owner:
        return "Super administrateur — accès illimité"
    if plan == "free" or status != "active":
        return "Accès non activé"
    if period_end is None:
        return "Abonnement illimité"
    if period_end > now:
        return f"Abonnement actif jusqu'au {period_end.date().isoformat()}"
    return "Abonnement expiré"


def _ensure_organization(
    conn: sqlite3.Connection,
    *,
    organization_id: str | None = None,
    name: str = "",
    slug: str = "",
    advisor_name: str = "",
    advisor_phone: str = "",
    advisor_email: str = "",
) -> str:
    if organization_id:
        existing = conn.execute("SELECT id FROM organizations WHERE id=?", (organization_id,)).fetchone()
        if existing:
            return existing["id"]

    ts = now_iso()
    clean_name = name.strip() or f"Compte {advisor_name or advisor_email or 'FINAB'}"
    org_slug = _unique_slug(conn, slug or clean_name)
    org_id = uuid4().hex
    conn.execute(
        """
        INSERT INTO organizations (id, name, slug, advisor_name, advisor_phone, advisor_email, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            org_id,
            clean_name,
            org_slug,
            advisor_name or clean_name,
            advisor_phone,
            advisor_email,
            ts,
            ts,
        ),
    )
    return org_id


def _bootstrap_default_account(conn: sqlite3.Connection) -> None:
    ts = now_iso()
    org = conn.execute("SELECT * FROM organizations WHERE slug=?", (DEFAULT_ORG["slug"],)).fetchone()
    if not org:
        org_id = uuid4().hex
        conn.execute(
            """
            INSERT INTO organizations (id, name, slug, advisor_name, advisor_phone, advisor_email, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                org_id,
                DEFAULT_ORG["name"],
                DEFAULT_ORG["slug"],
                DEFAULT_ORG["advisor_name"],
                DEFAULT_ORG["advisor_phone"],
                DEFAULT_ORG["advisor_email"],
                ts,
                ts,
            ),
        )
    else:
        org_id = org["id"]

    conn.execute(
        "UPDATE prospects SET organization_id=? WHERE organization_id IS NULL AND advisor_slug=?",
        (org_id, DEFAULT_ORG["slug"]),
    )
    conn.execute(
        """
        UPDATE abf_documents
        SET organization_id=(SELECT organization_id FROM prospects WHERE prospects.id=abf_documents.prospect_id)
        WHERE organization_id IS NULL
        """
    )

    default_email = os.getenv("FINAB_ADMIN_EMAIL", DEFAULT_ORG["advisor_email"]).strip().lower()
    default_password = os.getenv("FINAB_ADMIN_PASSWORD", "Finab-ABF-2026!")
    user = conn.execute("SELECT id FROM users WHERE email=?", (default_email,)).fetchone()
    if not user:
        conn.execute(
            """
            INSERT INTO users (id, organization_id, email, password_hash, full_name, role, subscription_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                org_id,
                default_email,
                _hash_password(default_password),
                DEFAULT_ORG["advisor_name"],
                "owner",
                "active",
                ts,
                ts,
            ),
        )
    conn.commit()


def get_organization_by_slug(slug: str) -> dict:
    conn = connect()
    row = conn.execute("SELECT * FROM organizations WHERE slug=?", (slug,)).fetchone()
    if not row:
        raise KeyError(slug)
    return _row_to_org(row)


def list_organizations() -> list[dict]:
    conn = connect()
    rows = conn.execute("SELECT * FROM organizations ORDER BY name").fetchall()
    return [_row_to_org(row) for row in rows]


def authenticate(email: str, password: str) -> dict | None:
    conn = connect()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if not row or not row["is_active"] or not _verify_password(password, row["password_hash"]):
        return None
    token = secrets.token_urlsafe(32)
    ts = now_iso()
    expires = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).isoformat()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, row["id"], expires, ts),
    )
    conn.commit()
    user = _row_to_user(row)
    user["organization"] = get_organization(row["organization_id"])
    return {"token": token, "expires_at": expires, "user": user}


def register_account(email: str, password: str, full_name: str, organization_name: str = "", advisor_phone: str = "") -> dict:
    conn = connect()
    clean_email = email.strip().lower()
    if conn.execute("SELECT id FROM users WHERE email=?", (clean_email,)).fetchone():
        raise ValueError("Ce courriel possède déjà un compte")
    org_id = _ensure_organization(
        conn,
        name=organization_name or f"FINAB - {full_name.strip()}",
        advisor_name=full_name.strip(),
        advisor_phone=advisor_phone.strip(),
        advisor_email=clean_email,
    )
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO users (id, organization_id, email, password_hash, full_name, role, is_active, subscription_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (uuid4().hex, org_id, clean_email, _hash_password(password), full_name.strip(), "advisor", 1, "incomplete", ts, ts),
    )
    conn.commit()
    result = authenticate(clean_email, password)
    if not result:
        raise RuntimeError("Compte créé mais connexion impossible")
    return result


def list_users(owner: dict) -> list[dict]:
    _require_owner(owner)
    conn = connect()
    rows = conn.execute(
        """
        SELECT users.*, organizations.name AS organization_name, organizations.slug AS organization_slug
        FROM users
        JOIN organizations ON organizations.id=users.organization_id
        ORDER BY users.created_at DESC
        """
    ).fetchall()
    return [_row_to_admin_user(row) for row in rows]


def create_user_by_owner(owner: dict, payload: dict) -> dict:
    _require_owner(owner)
    conn = connect()
    clean_email = payload["email"].strip().lower()
    org_id = _ensure_organization(
        conn,
        organization_id=payload.get("organization_id"),
        name=payload.get("organization_name") or payload.get("full_name") or clean_email,
        slug=payload.get("organization_slug") or "",
        advisor_name=payload.get("full_name") or clean_email,
        advisor_phone=payload.get("advisor_phone") or "",
        advisor_email=clean_email,
    )
    role = payload.get("role") if payload.get("role") in {"owner", "admin", "advisor"} else "advisor"
    plan = payload.get("plan") if payload.get("plan") in {"free", "finab_pro", "enterprise"} else "finab_pro"
    subscription_status = payload.get("subscription_status") if payload.get("subscription_status") in {"incomplete", "trialing", "active", "past_due", "canceled"} else "active"
    current_period_end = payload.get("current_period_end") or None
    last_payment_status = "admin_grant" if subscription_status == "active" else None
    ts = now_iso()
    existing = conn.execute("SELECT id FROM users WHERE email=?", (clean_email,)).fetchone()
    if existing:
        user_id = existing["id"]
        conn.execute(
            """
            UPDATE users
            SET organization_id=?, password_hash=?, full_name=?, role=?, is_active=1,
                plan=?, subscription_status=?, current_period_end=?, last_payment_status=?, updated_at=?
            WHERE id=?
            """,
            (
                org_id,
                _hash_password(payload["password"]),
                payload["full_name"].strip(),
                role,
                plan,
                subscription_status,
                current_period_end,
                last_payment_status,
                ts,
                user_id,
            ),
        )
    else:
        user_id = uuid4().hex
        conn.execute(
            """
            INSERT INTO users (id, organization_id, email, password_hash, full_name, role, is_active, plan, subscription_status, current_period_end, last_payment_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                org_id,
                clean_email,
                _hash_password(payload["password"]),
                payload["full_name"].strip(),
                role,
                1,
                plan,
                subscription_status,
                current_period_end,
                last_payment_status,
                ts,
                ts,
            ),
        )
    conn.commit()
    return get_admin_user(owner, user_id)


def get_admin_user(owner: dict, user_id: str) -> dict:
    _require_owner(owner)
    conn = connect()
    row = conn.execute(
        """
        SELECT users.*, organizations.name AS organization_name, organizations.slug AS organization_slug
        FROM users
        JOIN organizations ON organizations.id=users.organization_id
        WHERE users.id=?
        """,
        (user_id,),
    ).fetchone()
    if not row:
        raise KeyError(user_id)
    return _row_to_admin_user(row)


def update_user_by_owner(owner: dict, user_id: str, payload: dict) -> dict:
    _require_owner(owner)
    conn = connect()
    if user_id == owner["id"] and payload.get("is_active") is False:
        raise ValueError("Impossible de désactiver votre propre super compte")
    allowed: list[str] = []
    params: list[object] = []
    if payload.get("full_name") is not None:
        allowed.append("full_name=?")
        params.append(payload["full_name"].strip())
    if payload.get("role") is not None:
        role = payload["role"] if payload["role"] in {"owner", "admin", "advisor"} else "advisor"
        allowed.append("role=?")
        params.append(role)
    if payload.get("is_active") is not None:
        allowed.append("is_active=?")
        params.append(1 if payload["is_active"] else 0)
    if payload.get("organization_id") is not None:
        allowed.append("organization_id=?")
        params.append(payload["organization_id"])
    if payload.get("plan") is not None:
        plan = payload["plan"] if payload["plan"] in {"free", "finab_pro", "enterprise"} else "finab_pro"
        allowed.append("plan=?")
        params.append(plan)
    if payload.get("subscription_status") is not None:
        status = payload["subscription_status"] if payload["subscription_status"] in {"incomplete", "trialing", "active", "past_due", "canceled"} else "incomplete"
        allowed.append("subscription_status=?")
        params.append(status)
    if "trial_ends_at" in payload:
        allowed.append("trial_ends_at=?")
        params.append(payload.get("trial_ends_at") or None)
    if "current_period_end" in payload:
        allowed.append("current_period_end=?")
        params.append(payload.get("current_period_end") or None)
    if payload.get("last_payment_status") is not None:
        allowed.append("last_payment_status=?")
        params.append(payload["last_payment_status"])
    if not allowed:
        return get_admin_user(owner, user_id)
    allowed.append("updated_at=?")
    params.extend([now_iso(), user_id])
    conn.execute(f"UPDATE users SET {', '.join(allowed)} WHERE id=?", params)
    conn.commit()
    return get_admin_user(owner, user_id)


def delete_user_by_owner(owner: dict, user_id: str) -> None:
    _require_owner(owner)
    if user_id == owner["id"]:
        raise ValueError("Impossible de supprimer votre propre super compte")
    conn = connect()
    conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise KeyError(user_id)


def admin_overview(owner: dict) -> dict:
    _require_owner(owner)
    conn = connect()
    visible_prospects = list_prospects()
    visible_ids = {prospect["id"] for prospect in visible_prospects}
    documents = conn.execute("SELECT * FROM abf_documents").fetchall()
    plan_rows = conn.execute(
        "SELECT plan, subscription_status, COUNT(*) AS c FROM users GROUP BY plan, subscription_status"
    ).fetchall()
    return {
        "organizations": conn.execute("SELECT COUNT(*) AS c FROM organizations").fetchone()["c"],
        "users": conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"],
        "active_users": conn.execute("SELECT COUNT(*) AS c FROM users WHERE is_active=1").fetchone()["c"],
        "admins": conn.execute("SELECT COUNT(*) AS c FROM users WHERE role IN ('owner','admin')").fetchone()["c"],
        "unlimited_users": conn.execute("SELECT COUNT(*) AS c FROM users WHERE (role='owner' OR subscription_status='active') AND current_period_end IS NULL AND COALESCE(plan, 'finab_pro')!='free'").fetchone()["c"],
        "plan_distribution": [dict(row) for row in plan_rows],
        "prospects": len(visible_prospects),
        "documents": sum(1 for document in documents if document["prospect_id"] in visible_ids),
        "recent_prospects": visible_prospects,
    }


def get_session_user(token: str) -> dict | None:
    if not token:
        return None
    conn = connect()
    row = conn.execute(
        """
        SELECT users.* FROM sessions
        JOIN users ON users.id=sessions.user_id
        WHERE sessions.token=? AND sessions.expires_at>?
        """,
        (token, now_iso()),
    ).fetchone()
    if not row:
        return None
    user = _row_to_user(row)
    user["organization"] = get_organization(row["organization_id"])
    return user


def get_user_by_id(user_id: str) -> dict:
    conn = connect()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise KeyError(user_id)
    user = _row_to_user(row)
    user["organization"] = get_organization(row["organization_id"])
    return user


def set_stripe_customer(user_id: str, customer_id: str) -> dict:
    conn = connect()
    conn.execute(
        "UPDATE users SET stripe_customer_id=?, updated_at=? WHERE id=?",
        (customer_id, now_iso(), user_id),
    )
    conn.commit()
    return get_user_by_id(user_id)


def update_subscription_by_user(
    user_id: str,
    *,
    status: str,
    stripe_subscription_id: str | None = None,
    trial_ends_at: str | None = None,
    current_period_end: str | None = None,
    last_payment_status: str | None = None,
) -> dict:
    conn = connect()
    conn.execute(
        """
        UPDATE users
        SET subscription_status=?, stripe_subscription_id=COALESCE(?, stripe_subscription_id),
            trial_ends_at=?, current_period_end=?, last_payment_status=?, updated_at=?
        WHERE id=?
        """,
        (status, stripe_subscription_id, trial_ends_at, current_period_end, last_payment_status, now_iso(), user_id),
    )
    conn.commit()
    return get_user_by_id(user_id)


def update_subscription_by_customer(
    customer_id: str,
    *,
    status: str,
    stripe_subscription_id: str | None = None,
    trial_ends_at: str | None = None,
    current_period_end: str | None = None,
    last_payment_status: str | None = None,
) -> dict | None:
    conn = connect()
    row = conn.execute("SELECT id FROM users WHERE stripe_customer_id=?", (customer_id,)).fetchone()
    if not row:
        return None
    return update_subscription_by_user(
        row["id"],
        status=status,
        stripe_subscription_id=stripe_subscription_id,
        trial_ends_at=trial_ends_at,
        current_period_end=current_period_end,
        last_payment_status=last_payment_status,
    )


def revoke_session(token: str) -> None:
    conn = connect()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()


def get_organization(organization_id: str) -> dict:
    conn = connect()
    row = conn.execute("SELECT * FROM organizations WHERE id=?", (organization_id,)).fetchone()
    if not row:
        raise KeyError(organization_id)
    return _row_to_org(row)


def create_prospect(advisor_slug: str, prospect: ProspectSubmission) -> dict:
    conn = connect()
    org_row = conn.execute("SELECT * FROM organizations WHERE slug=?", (advisor_slug,)).fetchone()
    if not org_row:
        org_row = conn.execute("SELECT * FROM organizations WHERE slug=?", (DEFAULT_ORG["slug"],)).fetchone()
        advisor_slug = DEFAULT_ORG["slug"]
    pid = uuid4().hex
    ts = now_iso()
    payload = prospect.model_dump(mode="json")
    conn.execute(
        """
        INSERT INTO prospects (id, organization_id, advisor_slug, client_name, phone, email, status, payload_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pid,
            org_row["id"],
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
    return get_prospect(pid, organization_id=org_row["id"])


def list_prospects(advisor_slug: str | None = None, organization_id: str | None = None) -> list[dict]:
    conn = connect()
    clauses: list[str] = []
    params: list[str] = []
    if organization_id:
        clauses.append("organization_id=?")
        params.append(organization_id)
    if advisor_slug:
        clauses.append("advisor_slug=?")
        params.append(advisor_slug)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM prospects{where} ORDER BY created_at DESC", params).fetchall()
    if os.getenv("FINAB_SHOW_SAMPLE_DATA", "").lower() not in {"1", "true", "yes"}:
        rows = [row for row in rows if not _is_internal_sample_prospect(row)]
    return [_row_to_prospect(row, include_payload=False) for row in rows]


def get_prospect(prospect_id: str, organization_id: str | None = None) -> dict:
    conn = connect()
    if organization_id:
        row = conn.execute(
            "SELECT * FROM prospects WHERE id=? AND organization_id=?", (prospect_id, organization_id)
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if not row:
        raise KeyError(prospect_id)
    return _row_to_prospect(row, include_payload=True)


def prospect_submission(prospect_id: str, organization_id: str | None = None) -> ProspectSubmission:
    record = get_prospect(prospect_id, organization_id=organization_id)
    return ProspectSubmission.model_validate(record["payload"])


def update_status(prospect_id: str, status: str) -> None:
    conn = connect()
    conn.execute(
        "UPDATE prospects SET status=?, updated_at=? WHERE id=?",
        (status, now_iso(), prospect_id),
    )
    conn.commit()


def save_abf_document(prospect_id: str, output_path: str, report: dict, organization_id: str | None = None) -> dict:
    conn = connect()
    if organization_id is None:
        row = conn.execute("SELECT organization_id FROM prospects WHERE id=?", (prospect_id,)).fetchone()
        organization_id = row["organization_id"] if row else None
    doc_id = uuid4().hex
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO abf_documents (id, prospect_id, organization_id, output_path, report_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (doc_id, prospect_id, organization_id, output_path, json.dumps(report, ensure_ascii=False), ts),
    )
    conn.commit()
    update_status(prospect_id, "abf_generated")
    return {"id": doc_id, "prospect_id": prospect_id, "output_path": output_path, "report": report, "created_at": ts}


def list_documents(prospect_id: str, organization_id: str | None = None) -> list[dict]:
    conn = connect()
    if organization_id:
        rows = conn.execute(
            """
            SELECT * FROM abf_documents
            WHERE prospect_id=? AND organization_id=?
            ORDER BY created_at DESC
            """,
            (prospect_id, organization_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM abf_documents WHERE prospect_id=? ORDER BY created_at DESC", (prospect_id,)
        ).fetchall()
    return [
        {
            "id": row["id"],
            "prospect_id": row["prospect_id"],
            "organization_id": row["organization_id"],
            "output_path": row["output_path"],
            "report": json.loads(row["report_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def default_review(prospect: ProspectSubmission, organization: dict | None = None) -> AdvisorReview:
    organization = organization or DEFAULT_ORG
    return AdvisorReview(
        reviewed_by_advisor=True,
        advisor_name=organization.get("advisor_name") or DEFAULT_ORG["advisor_name"],
        advisor_phone=organization.get("advisor_phone") or DEFAULT_ORG["advisor_phone"],
        advisor_email=organization.get("advisor_email") or DEFAULT_ORG["advisor_email"],
        replacement_years=10,
        final_recommended_coverage=0,
        recommendation_1_budget=prospect.goals.acceptable_monthly_budget,
        recommendation_2_budget=prospect.goals.acceptable_monthly_budget * 1.5,
        client_preference_budget=prospect.goals.acceptable_monthly_budget,
    )


def _row_to_org(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "advisor_name": row["advisor_name"],
        "advisor_phone": row["advisor_phone"],
        "advisor_email": row["advisor_email"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_user(row: sqlite3.Row) -> dict:
    data = {
        "id": row["id"],
        "organization_id": row["organization_id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    data["subscription"] = _subscription_state(row)
    return data


def _row_to_admin_user(row: sqlite3.Row) -> dict:
    data = _row_to_user(row)
    data["organization"] = {
        "id": row["organization_id"],
        "name": row["organization_name"],
        "slug": row["organization_slug"],
    }
    return data


def _row_to_prospect(row: sqlite3.Row, include_payload: bool) -> dict:
    data = {
        "id": row["id"],
        "organization_id": row["organization_id"],
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


def _is_internal_sample_prospect(row: sqlite3.Row) -> bool:
    """Hide obvious local/demo records from advisor-facing dashboards.

    Historical sample rows remain available in the database for development and PDF regression
    checks, but the live workspace should only show real client records unless explicitly enabled.
    """
    text = " ".join(
        str(row[key] or "")
        for key in ("client_name", "phone", "email", "advisor_slug", "status")
    ).lower()
    sample_markers = (
        " test",
        "test ",
        "demo",
        "démo",
        "sample",
        "fake",
        "mock",
        "placeholder",
        "example.com",
    )
    return any(marker in f" {text} " for marker in sample_markers)
