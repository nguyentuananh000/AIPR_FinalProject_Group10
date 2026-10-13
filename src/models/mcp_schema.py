from dataclasses import dataclass
from typing import Optional

@dataclass
class GetClaimDetailsParams:
    claim_id: str
@dataclass
class GetClaimStatusParams:
    claim_id: str
@dataclass
class SubmitAuditDecisionParams:
    claim_id: str
    status: str
    notes: str
    approved_amount: Optional[float] = None
