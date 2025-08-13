from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import Response
from typing import List, Optional, Tuple, Dict, Any
from ..db import get_pool, run_db
import csv
import io

router = APIRouter()

# Schema name for BDC data; adjust via env or constant in one place
SCHEMA_NAME = "bdc_schema_dev"

def _get_state_abbr(conn, state: str) -> str:
    """Resolve input state (name or USPS abbr) to lowercase USPS abbr.

    Accepts either full state name or abbreviation. Queries once and builds
    in-memory maps for normalization.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT LOWER(state_name::text), LOWER(state_abbr::text)
        FROM bdc_schema_dev.dim_states_detail
        """
    )
    rows = cur.fetchall()
    name_to_abbr = {name: abbr for name, abbr in rows}
    abbr_to_abbr = {abbr: abbr for _, abbr in rows}
    key = state.strip().lower()
    abbr = name_to_abbr.get(key) or abbr_to_abbr.get(key)
    if not abbr:
        raise HTTPException(status_code=400, detail="Unknown state")
    return abbr

def _get_columns_for_table(conn, schema: str, table: str) -> List[str]:
    """Return ordered column names for the given table."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )
    return [r[0] for r in cur.fetchall()]

def _quote_ident(ident: str) -> str:
    """Safely quote SQL identifiers (tables/columns)."""
    return '"' + ident.replace('"', '""') + '"'

def _detect_county_column(available_columns: List[str]) -> Optional[str]:
    """Best-effort detection of a county name column on the state table.

    Keeps the list short and readable; falls back to any column containing
    the substring 'county' to cover minor naming variations.
    """
    candidates = [
        "county",
        "county_name",
        "official_name_county",
        "official_county_name",
        "county_nm",
        "cnty",
        "cnty_name",
    ]
    cols_lower = {c.lower(): c for c in available_columns}
    for c in candidates:
        if c in cols_lower:
            return cols_lower[c]
    # Fallback: any column containing the substring 'county'
    for name_lower, original in cols_lower.items():
        if "county" in name_lower:
            return original
    # Last resort: common abbreviations
    for name_lower, original in cols_lower.items():
        if name_lower.startswith("cnty") or name_lower.endswith("_cnty"):
            return original
    return None

def _detect_block_geoid_column(available_columns: List[str]) -> Optional[str]:
    """Detect the block GEOID column for county join fallback."""
    candidates = [
        "block_geoid",
        "geoid_block",
        "geoid",
    ]
    cols_lower = {c.lower(): c for c in available_columns}
    for c in candidates:
        if c in cols_lower:
            return cols_lower[c]
    return None

def _table_exists(conn, schema: str, table: str) -> bool:
    """Check if a table exists (used for choosing the county lookup)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        LIMIT 1
        """,
        (schema, table),
    )
    return cur.fetchone() is not None

def _get_columns(conn, schema: str, table: str) -> List[str]:
    """Convenience to fetch column list (used in lookup detection)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )
    return [r[0] for r in cur.fetchall()]

def _find_county_lookup_source(conn) -> Optional[Dict[str, Any]]:
    """Find a county lookup table to support filtering by county names.

    Prefers dim_county_details, then dim_county. Requires a county name column
    and a county FIPS/GEOID column; optionally uses a state column if present.
    """
    candidates = ["dim_county_details", "dim_county"]
    name_candidates = ["county", "county_name", "official_county_name"]
    fips_candidates = ["geo_id", "geoid", "county_geo_id", "county_fips", "county_fips_code", "countyfp", "fips"]
    state_candidates = ["state_usps", "state", "official_name_state", "state_abbr", "state_name"]
    for table in candidates:
        if not _table_exists(conn, SCHEMA_NAME, table):
            continue
        cols = _get_columns(conn, SCHEMA_NAME, table)
        cols_lower = {c.lower(): c for c in cols}
        name_col = next((cols_lower[c] for c in name_candidates if c in cols_lower), None)
        fips_col = next((cols_lower[c] for c in fips_candidates if c in cols_lower), None)
        state_col = next((cols_lower[c] for c in state_candidates if c in cols_lower), None)
        if name_col and fips_col:
            return {
                "table": table,
                "name_col": name_col,
                "fips_col": fips_col,
                "state_col": state_col,
            }
    return None

def _find_county_lookup_source_broad(conn) -> Optional[Dict[str, Any]]:
    """Last-resort: search other tables in schema for county and geo columns."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT table_name
        FROM information_schema.columns
        WHERE table_schema = %s AND (column_name ILIKE '%%county%%')
        """,
        (SCHEMA_NAME,),
    )
    tables = [r[0] for r in cur.fetchall()]
    for table in tables:
        cols = _get_columns(conn, SCHEMA_NAME, table)
        cols_lower = {c.lower(): c for c in cols}
        name_col = next((orig for low, orig in cols_lower.items() if 'county' in low), None)
        fips_col = None
        for cand in ("geo_id", "geoid", "county_geo_id", "county_fips", "county_fips_code", "countyfp", "fips"):
            if cand in cols_lower:
                fips_col = cols_lower[cand]
                break
        state_col = None
        for cand in ("state_usps", "state", "official_name_state", "state_abbr", "state_name"):
            if cand in cols_lower:
                state_col = cols_lower[cand]
                break
        if name_col and fips_col:
            return {"table": table, "name_col": name_col, "fips_col": fips_col, "state_col": state_col}
    return None

@router.get("/attributes", response_model=List[str])
async def list_attributes(state: str = Query(..., description="State name or abbr")):
    pool = get_pool()
    def _run():
        conn = pool.getconn()
        try:
            abbr = _get_state_abbr(conn, state)
            table = f"bdc_{abbr}"
            cols = _get_columns_for_table(conn, SCHEMA_NAME, table)
            if not cols:
                raise HTTPException(status_code=404, detail="No columns found for table")
            return cols
        finally:
            pool.putconn(conn)
    return await run_db(_run)

@router.post("/csv")
async def export_csv(
    state: str = Body(..., embed=True),
    counties: Optional[List[str]] = Body(None, embed=True),
    attributes: List[str] = Body(..., embed=True),
):
    if not attributes:
        raise HTTPException(status_code=400, detail="attributes is required")
    pool = get_pool()

    def _run() -> Tuple[bytes, str]:
        conn = pool.getconn()
        try:
            abbr = _get_state_abbr(conn, state)
            table = f"bdc_{abbr}"
            available = _get_columns_for_table(conn, SCHEMA_NAME, table)
            if not available:
                raise HTTPException(status_code=404, detail="Table has no columns")

            # Whitelist requested attributes against available columns
            allowed = {c.lower(): c for c in available}
            selected: List[str] = []
            for a in attributes:
                key = a.strip().lower()
                if key in allowed:
                    selected.append(allowed[key])
            if not selected:
                raise HTTPException(status_code=400, detail="No valid attributes selected")

            county_col = _detect_county_column(available)
            block_geoid_col = _detect_block_geoid_column(available)

            # Build SQL safely using quoted identifiers
            select_list = ", ".join(_quote_ident(c) for c in selected)
            full_table = f"{_quote_ident(SCHEMA_NAME)}.{_quote_ident(table)}"
            sql = f"SELECT {select_list} FROM {full_table}"
            params: List[object] = []
            if counties:
                if county_col:
                    # Case-insensitive compare, normalize whitespace
                    # Prepare variants with and without ' county' suffix
                    norm: List[str] = []
                    for c in counties:
                        v = c.strip().lower()
                        norm.append(v)
                        if v.endswith(" county"):
                            norm.append(v[:-7].strip())
                        else:
                            norm.append(f"{v} county")
                    norm = list(dict.fromkeys(norm))
                    placeholders = ",".join(["%s"] * len(norm))
                    sql += f" WHERE LOWER(TRIM({_quote_ident(county_col)})) IN ({placeholders})"
                    params.extend(norm)
                elif block_geoid_col:
                    # Fall back to county name filter via JOIN using block_geoid prefix
                    source = _find_county_lookup_source(conn) or _find_county_lookup_source_broad(conn)
                    if not source:
                        raise HTTPException(status_code=400, detail="County filter unsupported: no county or fips column available")

                    name_col = source["name_col"]
                    fips_col = source["fips_col"]

                    # Build normalized county name list
                    norm: List[str] = []
                    for c in counties:
                        v = c.strip().lower()
                        norm.append(v)
                        if v.endswith(" county"):
                            norm.append(v[:-7].strip())
                        else:
                            norm.append(f"{v} county")
                    norm = list(dict.fromkeys(norm))

                    name_ph = ",".join(["%s"] * len(norm))

                    # Switch to joined filtering
                    from_clause = f"{full_table} AS b JOIN { _quote_ident(SCHEMA_NAME) }.{ _quote_ident(source['table']) } AS c ON LEFT(b.{_quote_ident(block_geoid_col)}, 5) = c.{_quote_ident(fips_col)}"
                    where_clause = f"LOWER(TRIM(c.{_quote_ident(name_col)})) IN ({name_ph})"
                    sql = f"SELECT {select_list} FROM {from_clause} WHERE {where_clause}"
                    params.extend(norm)

            cur = conn.cursor()
            cur.execute(sql, params if params else None)
            rows = cur.fetchall()

            # Build CSV
            buf = io.StringIO()
            writer = csv.writer(buf, lineterminator='\n')
            writer.writerow(selected)
            for row in rows:
                writer.writerow(row)
            data = buf.getvalue().encode("utf-8")
            filename = f"export_{abbr}.csv"
            return data, filename
        finally:
            pool.putconn(conn)

    data, filename = await run_db(_run)
    return Response(content=data, media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })


