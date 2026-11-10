
"""Employee model for the salon management system."""

from dataclasses import dataclass

from .validation import validate_text


@dataclass(frozen=True)
class Employee:
    """Represent a salon employee whose productivity is tracked."""

    employee_id: str
    name: str
    department: str
    active: bool = True

    def __post_init__(self) -> None:
        """Validate employee details when an object is created."""

        validate_text(self.employee_id, "Employee ID")
        validate_text(self.name, "Employee name")
        validate_text(self.department, "Department")
        if not isinstance(self.active, bool):
            raise ValueError("Active must be a boolean.")
