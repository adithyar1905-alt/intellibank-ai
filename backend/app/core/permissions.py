from enum import StrEnum

from app.core.authorization import require_permissions, require_roles


class RoleName(StrEnum):
    SUPER_ADMIN = "Super Admin"
    BANK_ADMIN = "Bank Admin"
    BRANCH_MANAGER = "Branch Manager"
    BANK_EMPLOYEE = "Bank Employee"
    LOAN_OFFICER = "Loan Officer"
    RISK_ANALYST = "Risk Analyst"
    CUSTOMER = "Customer"


DEFAULT_ROLE_NAMES = tuple(role.value for role in RoleName)

__all__ = ["DEFAULT_ROLE_NAMES", "RoleName", "require_permissions", "require_roles"]