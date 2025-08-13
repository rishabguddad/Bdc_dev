from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from ..db import get_pool, run_db
import re

router = APIRouter()

def fetch_call_sql_sync(conn, script_name: str) -> Optional[str]:
    cur = conn.cursor()
    # pg8000 paramstyle is %s
    cur.execute(
        """
        SELECT COALESCE(NULLIF(call_statements_rishab, ''), call_statements) AS sql
        FROM bdc_schema_dev.test_app_info
        WHERE script_name = %s
        LIMIT 1
        """,
        (script_name,),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return None
    parts = [p.strip() for p in row[0].split("|") if p.strip()]
    return parts[0] if parts else None

@router.get("/run")
async def run_report(
    script: str = Query(..., description="Report script name, e.g., 'Location Level'"),
    state: str = Query(..., description="State name"),
    counties: Optional[List[str]] = Query(None, description="List of county FIPS or names; use 'All' or omit for all"),
):
    pool = get_pool()

    def _run():
        conn = pool.getconn()
        try:
            call_sql = fetch_call_sql_sync(conn, script)
            if not call_sql:
                raise HTTPException(status_code=404, detail="No SQL found for script")

            cur = conn.cursor()
            cur.execute("SELECT LOWER(state_name::text), LOWER(state_abbr::text) FROM bdc_schema_dev.dim_states_detail")
            rows = cur.fetchall()
            abbr_map = {name: abbr for name, abbr in rows}
            abbr_map.update({abbr: abbr for _, abbr in rows})
            abbr = abbr_map.get(state.strip().lower(), state.strip().upper())

            def replace_with_state_abbr(m: re.Match) -> str:
                quote = m.group(1)
                return f"{quote}{abbr}{quote}"
            prepared_sql = re.sub(r"(['\"])\w+_[a-z]{2}\1", replace_with_state_abbr, call_sql)

            if counties and counties != ["All"]:
                joined = "'" + ",".join(counties) + "'"
                prepared_sql = prepared_sql.replace("null", joined)

            cur.execute(prepared_sql)
            data = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return {"columns": columns, "rows": data}
        finally:
            pool.putconn(conn)

    return await run_db(_run)
