"""A completed service sale and its employee revenue allocation."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from .service import Service
from .service_assignment import ServiceAssignment
from .validation import to_decimal, validate_text


@dataclass(frozen=True)
class ServiceSale:
    """Record one service sale with its price and employee wage rates."""

    sale_id: str
    service: Service
    sale_date: date
    assignments: tuple[ServiceAssignment, ...]
    agreed_price: Decimal | None = None
    service_description: str | None = None

    def __post_init__(self) -> None:
        """Validate a complete sale before it can be used."""
        validate_text(self.sale_id, "Sale ID")
        if not isinstance(self.service, Service):
            raise ValueError("Sale service must be a Service.")
        if not isinstance(self.sale_date, date) or isinstance(self.sale_date, datetime):
            raise ValueError("Sale date must be a date without a time.")
        if self.service_description is not None and not isinstance(
            self.service_description, str
        ):
            raise ValueError("Service description must be text or None.")

        price = self.agreed_price
        if price is None:
            if self.service.requires_agreed_price():
                raise ValueError("A variable-price sale needs an agreed price.")
            price = self.service.fixed_price
        price = to_decimal(price, "Agreed price")
        if price <= 0:
            raise ValueError("Agreed price must be positive.")
        if not self.service.requires_agreed_price() and price != self.service.fixed_price:
            raise ValueError("Agreed price must match the service's fixed price.")
        object.__setattr__(self, "agreed_price", price)

        if not isinstance(self.assignments, (list, tuple)) or not self.assignments:
            raise ValueError("A sale needs a non-empty list or tuple of assignments.")
        assignments = tuple(self.assignments)
        employee_ids = set()
        total_percentage = Decimal("0")
        for assignment in assignments:
            if not isinstance(assignment, ServiceAssignment):
                raise ValueError("Each assignment must be a ServiceAssignment.")
            employee_id = assignment.employee.employee_id
            if employee_id in employee_ids:
                raise ValueError("An employee can only be assigned once per sale.")
            employee_ids.add(employee_id)
            total_percentage += assignment.percentage
        if total_percentage != Decimal("100"):
            raise ValueError("Contribution percentages must total exactly 100%.")
        # Assignments are already frozen, including their recorded wage rates.
        object.__setattr__(self, "assignments", assignments)

    def _find_assignment(self, employee_id: str) -> ServiceAssignment:
        """Find an employee's share, reporting unknown IDs clearly."""
        validate_text(employee_id, "Employee ID")
        for assignment in self.assignments:
            if assignment.employee.employee_id == employee_id:
                return assignment
        raise ValueError("Employee is not assigned to this sale.")

    def calculate_employee_contribution(self, employee_id: str) -> Decimal:
        """Return the employee's share of the sale revenue."""
        return self._find_assignment(employee_id).calculate_contribution(self.agreed_price)

    def calculate_employee_expected_wage(self, employee_id: str) -> Decimal:
        """Use the employee's wage rate recorded in this sale."""
        return self._find_assignment(employee_id).calculate_expected_wage(self.agreed_price)

    def calculate_total_expected_wage(self) -> Decimal:
        """Sum expected wages without adding currency rounding."""
        return sum(
            (assignment.calculate_expected_wage(self.agreed_price)
             for assignment in self.assignments),
            Decimal("0"),
        )
