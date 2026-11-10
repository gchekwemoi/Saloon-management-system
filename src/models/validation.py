"""Small validation helpers shared by the salon models."""

from decimal import Decimal, InvalidOperation


def validate_text(value: str, label: str) -> None:
    """Require text with at least one non-whitespace character."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text.")


def to_decimal(value: Decimal | int | float | str, label: str) -> Decimal:
    """Convert numeric input to a finite Decimal with a clear error."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        raise ValueError(f"{label} must be a finite number.")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{label} must be a finite number.") from error
    if not number.is_finite():
        raise ValueError(f"{label} must be a finite number.")
    return number
