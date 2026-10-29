
"""Employee model for the salon management system."""

from dataclasses import dataclass


@dataclass
class Employee:
    """Represent a salon employee whose productivity is tracked."""

    employee_id: str
    name: str
    department: str
    active: bool = True

    def __post_init__(self) -> None:
        """Validate employee details when an object is created."""

        if not self.employee_id.strip():
            raise ValueError("Employee ID is required.")

        if not self.name.strip():
            raise ValueError("Employee name is required.")

        if not self.department.strip():
            raise ValueError("Department is required.")
