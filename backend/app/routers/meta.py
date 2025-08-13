from fastapi import APIRouter, HTTPException
from typing import List
from ..db import get_pool, run_db

router = APIRouter()

@router.get("/states", response_model=List[str])
async def get_states():
    """List all state names available for selection.

    Uses dim_states_detail to ensure consistent labeling on the frontend.
    """
    pool = get_pool()
    def _fetch():
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT state_name 
                FROM bdc_schema_dev.dim_states_detail 
                WHERE state_name IS NOT NULL 
                ORDER BY state_name
                """
            )
            return [r[0] for r in cur.fetchall()]
        finally:
            pool.putconn(conn)
    return await run_db(_fetch)

@router.get("/counties", response_model=List[str])
async def get_counties(state: str):
    """List counties for a given state name.

    The export uses county names to filter; expose the values from dim_county.
    """
    if not state:
        raise HTTPException(status_code=400, detail="state is required")
    pool = get_pool()
    def _fetch():
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            # pg8000 uses DB-API paramstyle "format" -> use %s placeholders
            cur.execute(
                """
                SELECT DISTINCT county 
                FROM bdc_schema_dev.dim_county 
                WHERE official_name_state = %s AND county IS NOT NULL 
                ORDER BY county
                """,
                (state,)
            )
            return [r[0] for r in cur.fetchall()]
        finally:
            pool.putconn(conn)
    return await run_db(_fetch)
