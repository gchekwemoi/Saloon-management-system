
"""Employee contribution to a salon service."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .employee import Employee


@dataclass
class ServiceAssignment:
    """Represent one employee's percentage contribution."""

    employee: Employee
    percentage: Decimal

    def __post_init__(self) -> None:
        """Validate the assigned contribution percentage."""

        if not isinstance(self.employee, Employee):
            raise TypeError("A valid Employee is required.")

        try:
            self.percentage = Decimal(str(self.percentage))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Invalid percentage.") from exc

        if not self.percentage.is_finite():
            raise ValueError("Percentage must be finite.")

        if not 0 < self.percentage <= 100:
            raise ValueError(
                "Employee percentage must be above 0 and at most 100."
            )

    def calculate_contribution(self, agreed_price: Decimal) -> Decimal:
        """Calculate employee revenue using the agreed service price."""

        price = Decimal(str(agreed_price))

        if not price.is_finite() or price <= 0:
            raise ValueError("Agreed price must be positive.")

        return price * self.percentage / Decimal("100")
