from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ExpenseItem:
    category: str
    amount: float
    has_receipt: bool=True
@dataclass
class ExpenseClaim:
    claim_id: str
    employee_name: str
    department: str
    trip_days: int
    expenses: list[ExpenseItem] = field(default_factory=list)
    team_lead_signed: bool = False
    department_head_signed: bool = False
    trip_end_date: Optional[str] = None
    submitted_date: Optional[str] = None
    explanation_signed: bool = False
    status: str = "PENDING"
    notes: str = ""
    def compute_total_claimed(self)-> float:
        return sum(item.amount for item in self.expenses)
@dataclass
class AuditDecision: 
    claim_id: str
    status: str
    notes: str
    approved_amount: Optional[float]= None