"""One merchandise sale line with its recorded selling price."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from .validation import to_decimal, validate_text


@dataclass(frozen=True)
class ProductSale:
    """Record a product sale without requiring a catalogue entry."""

    sale_id: str
    sale_date: date
    product_description: str
    quantity: int
    unit_selling_price: Decimal
    product_id: str | None = None

    def __post_init__(self) -> None:
        """Validate the line and store its price as a Decimal."""
        validate_text(self.sale_id, "Sale ID")
        validate_text(self.product_description, "Product description")
        if self.product_id is not None:
            validate_text(self.product_id, "Product ID")
        if not isinstance(self.sale_date, date) or isinstance(self.sale_date, datetime):
            raise ValueError("Sale date must be a date without a time.")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, int)
            or self.quantity <= 0
        ):
            raise ValueError("Quantity must be a positive integer.")

        price = to_decimal(self.unit_selling_price, "Unit selling price")
        if price <= 0:
            raise ValueError("Unit selling price must be positive.")
        object.__setattr__(self, "unit_selling_price", price)

    def calculate_total(self) -> Decimal:
        """Calculate line revenue using the price recorded at sale time."""
        return self.unit_selling_price * self.quantity
