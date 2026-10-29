
"""Service model for the salon management system."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class PricingType(Enum):
    """Define the two ways salon services are priced."""

    FIXED = "fixed"
    VARIABLE = "variable"


@dataclass
class Service:
    """Represent a service offered by the salon."""

    service_id: str
    name: str
    department: str
    pricing_type: PricingType
    fixed_price: Decimal | None = None

    def __post_init__(self) -> None:
        """Validate service details."""

        if not self.service_id.strip():
            raise ValueError("Service ID is required.")

        if not self.name.strip():
            raise ValueError("Service name is required.")

        if not self.department.strip():
            raise ValueError("Department is required.")

        if not isinstance(self.pricing_type, PricingType):
            raise ValueError("Invalid pricing type.")

        if self.pricing_type == PricingType.FIXED:
            if self.fixed_price is None:
                raise ValueError("A fixed-price service needs a price.")

            if self.fixed_price <= 0:
                raise ValueError("The price must be positive.")

        elif self.fixed_price is not None:
            raise ValueError(
                "Variable-price services must not have a fixed price."
            )

    def requires_agreed_price(self) -> bool:
        """Check whether the cashier must enter a price."""
        return self.pricing_type == PricingType.VARIABLE
