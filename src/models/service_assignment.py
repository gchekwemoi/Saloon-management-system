
"""Employee revenue contribution and expected wage calculations."""

from dataclasses import dataclass
from decimal import Decimal

from .employee import Employee
from .validation import to_decimal


@dataclass(frozen=True)
class ServiceAssignment:
    employee: Employee
    percentage: Decimal
    wage_rate: Decimal = Decimal("30")

    def __post_init__(self) -> None:
        """Validate contribution and wage percentages."""

        if not isinstance(self.employee, Employee):
            raise ValueError("Assignment employee must be an Employee.")
        percentage = to_decimal(self.percentage, "Contribution percentage")
        wage_rate = to_decimal(self.wage_rate, "Wage rate")
        object.__setattr__(self, "percentage", percentage)
        object.__setattr__(self, "wage_rate", wage_rate)

        if not 0 < self.percentage <= 100:
            raise ValueError("Contribution must be between 0 and 100%.")

        if not 0 <= self.wage_rate <= 100:
            raise ValueError("Wage rate must be between 0 and 100%.")

    def calculate_contribution(self, agreed_price: Decimal | int | float | str) -> Decimal:
        """Calculate revenue attributed to the employee."""

        price = to_decimal(agreed_price, "Agreed price")

        if price <= 0:
            raise ValueError("Agreed price must be positive.")

        return price * self.percentage / Decimal("100")

    def calculate_expected_wage(self, agreed_price: Decimal | int | float | str) -> Decimal:
        """Calculate expected wage from attributed revenue."""

        contribution = self.calculate_contribution(agreed_price)

        return contribution * self.wage_rate / Decimal("100")
