import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client, Client


def as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "y")


def iso_cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def get_supabase() -> Client:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY")
    return create_client(url, key)


def estimate_count(sb: Client, table: str, ts_col: str, cutoff: str) -> int:
    # head=True + count='exact' avoids loading row payload.
    res = sb.table(table).select("*", count="exact", head=True).lt(ts_col, cutoff).execute()
    return int(res.count or 0)


def purge_table(sb: Client, table: str, ts_col: str, cutoff: str, dry_run: bool):
    count = estimate_count(sb, table, ts_col, cutoff)
    print(f"[{table}] older_than={cutoff} count={count} dry_run={dry_run}")
    if dry_run or count == 0:
        return
    sb.table(table).delete().lt(ts_col, cutoff).execute()
    print(f"[{table}] deleted={count}")


def main():
    dry_run = as_bool(os.getenv("RETENTION_DRY_RUN", "true"), default=True)
    session_days = int(os.getenv("RETENTION_SESSION_DAYS", "30"))
    source_days = int(os.getenv("RETENTION_SOURCE_DAYS", "30"))
    report_days = int(os.getenv("RETENTION_REPORT_DAYS", "30"))

    session_cutoff = iso_cutoff(session_days)
    source_cutoff = iso_cutoff(source_days)
    report_cutoff = iso_cutoff(report_days)

    sb = get_supabase()

    # 1) Report-first cleanup
    purge_table(sb, "session_reports", "created_at", report_cutoff, dry_run)

    # 2) Session cleanup (cascade: audio_chunks -> signals -> evidence_candidates)
    purge_table(sb, "sessions", "created_at", session_cutoff, dry_run)

    # 3) Source cleanup (cascade: chunks)
    purge_table(sb, "sources", "created_at", source_cutoff, dry_run)

    print("Retention purge completed.")


if __name__ == "__main__":
    main()
