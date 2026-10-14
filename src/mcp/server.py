import json
import logging
import sys
from pathlib import Path

from mcp.server import MCPServer

logging.basicConfig(
    level =  logging.INFO,
    stream= sys.stderr,
    format= "%(asctime)s %(levelname)s %(message)s",)
    
logger = logging.getLogger(__name__)
mcp =  MCPServer("expense-audit")
PROJECT_ROOT= Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT/"data"/"audit_claims_db.json"


VALID_STATUSES = {
    "PENDING",
    "APPROVED",
    "ADJUSTED",
    "REJECTED",
    "ESCALATED",
    "REQUEST_MORE_INFO",
}

def load_claims():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"database not found:{DB_PATH}")
    
    data = json.loads(DB_PATH.read_text(encoding = "utf-8"))

    if not isinstance(data,list):
        raise ValueError("Database must contain a JSON list")

    return data

def find_claim(claims, claim_id):
    wanted_id = claim_id.strip().upper()
    for claim in claims:
        if claim.get("claim_id","").upper()== wanted_id:
            return claim

    return None

def save_claims(claims):
    DB_PATH.write_text(
        json.dumps(claims, ensure_ascii=False, indent=2),
        encoding = "utf-8",
    )

@mcp.tool()
def get_claim_details(claim_id: str)-> str:
    """ Read the full expense claim by its claim ID."""
    try:
        claims =  load_claims()
        claim = find_claim(claims, claim_id)
        if claim is None:
            return f"Error: claim'{claim_id}' was not found."
        return json.dumps(claim, ensure_ascii=False, indent=2)
    except(OSError, ValueError, TypeError) as error:
        logger.exception("Could not read claim %s", claim_id)
        return f"Error: could not read claim database: {error}"

@mcp.tool()
def submit_audit_decision(
    claim_id: str,
    status: str,
    notes: str,
    approved_amount: float |None= None,
) -> str:
    """ save an audit decision for a claim"""
    normalized_status = status.strip().upper()
    if normalized_status == "REQUEST_INFO":
        normalized_status = "REQUEST_MORE_INFO"
    if normalized_status not in VALID_STATUSES:
        return f"Error: invalid status'{status}'."
    if approved_amount is not None and approved_amount<0:
        return"Error: approved_amount cannot be negative."
    
    try:
        claims = load_claims()
        claim = find_claim(claims, claim_id)
        if claim is None:
            return f"Error: claim'{claim_id}' was not found."
        claim["status"] = normalized_status
        claim["notes"] = notes.strip()
        if approved_amount is not None:
            claim["approved_amount"] = round(approved_amount, 2)

        save_claims(claims)
        logger.info("Saved decision %s for %s", normalized_status, claim_id)
        return(
            f"Decision saved for {claim_id}: {normalized_status}."
            "call get_claim_status to verify."
        )
    except (OSError, ValueError, TypeError) as error:
        logger.exception("Could not save decision for &s", claim_id)
        return f"Error: could not save decision: {error}"
     
@mcp.tool()
def get_claim_status(claim_id:str)-> str:
    """Read the saved audit status to verify a decision."""
    try:
        claims = load_claims()
        claim = find_claim(claims, claim_id)
        if claim is None:
            return f"Error: claim'{claim_id}' was not found."
        status_info = {
            "claim_id": claim.get("claim_id"),
            "status": claim.get("status", "UNKNOWN"),
            "approved_amount": claim.get("approved_amount"),
            "notes": claim.get("notes",""),
        }
        return json.dumps(status_info, ensure_ascii=False, indent=2)
    except (OSError, ValueError, TypeError) as error:
            logger.exception("Could not save decision for &s", claim_id)
            return f"Error: could not save decision: {error}"
    
if __name__ == "__main__":
    mcp.run(transport="stdio")
 