
"""Employee revenue contribution and expected wage calculations."""

from dataclasses import dataclass
from decimal import Decimal

from .employee import Employee


@dataclass
class ServiceAssignment:
    employee: Employee
    percentage: Decimal
    wage_rate: Decimal = Decimal("30")

    def __post_init__(self):
        """Validate contribution and wage percentages."""

        self.percentage = Decimal(str(self.percentage))
        self.wage_rate = Decimal(str(self.wage_rate))

        if not self.percentage.is_finite():
            raise ValueError("Contribution percentage must be finite.")

        if not self.wage_rate.is_finite():
            raise ValueError("Wage rate must be finite.")

        if not 0 < self.percentage <= 100:
            raise ValueError("Contribution must be between 0 and 100%.")

        if not 0 <= self.wage_rate <= 100:
            raise ValueError("Wage rate must be between 0 and 100%.")

    def calculate_contribution(self, agreed_price):
        """Calculate revenue attributed to the employee."""

        price = Decimal(str(agreed_price))

        if not price.is_finite() or price <= 0:
            raise ValueError("Agreed price must be positive.")

        return price * self.percentage / Decimal("100")

    def calculate_expected_wage(self, agreed_price):
        """Calculate expected wage from attributed revenue."""

        contribution = self.calculate_contribution(agreed_price)

        return contribution * self.wage_rate / Decimal("100")
