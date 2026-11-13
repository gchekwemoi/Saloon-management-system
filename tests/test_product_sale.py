"""Validation, totals, and historical price tests for product sale lines."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from src.models.product_sale import ProductSale


@pytest.fixture
def sale():
    return ProductSale(
        sale_id="PS1",
        sale_date=date(2026, 11, 10),
        product_description="Black braids, colour 1, long pack",
        quantity=3,
        unit_selling_price="8000",
    )


def test_cashier_entered_product_without_catalogue(sale):
    assert sale.product_id is None
    assert sale.product_description == "Black braids, colour 1, long pack"
    assert sale.calculate_total() == Decimal("24000")
    assert isinstance(sale.calculate_total(), Decimal)


def test_optional_catalogue_reference(sale):
    registered = replace(sale, product_id="P1")
    assert registered.product_id == "P1"
    assert registered.calculate_total() == sale.calculate_total()
    assert replace(registered, product_id=None).product_id is None


@pytest.mark.parametrize("field", ["sale_id", "product_description", "product_id"])
@pytest.mark.parametrize("invalid", ["", " \t\n", 123, True, [], object()])
def test_invalid_text(sale, field, invalid):
    with pytest.raises(ValueError):
        replace(sale, **{field: invalid})


@pytest.mark.parametrize("field", ["sale_id", "product_description"])
def test_required_text_cannot_be_none(sale, field):
    with pytest.raises(ValueError):
        replace(sale, **{field: None})


@pytest.mark.parametrize("invalid", [None, "2026-11-10", True, 123,
                                    datetime(2026, 11, 10), object()])
def test_invalid_sale_date(sale, invalid):
    with pytest.raises(ValueError, match="Sale date"):
        replace(sale, sale_date=invalid)


@pytest.mark.parametrize("invalid", [0, -1, True, False, None, "3", 3.0, 1.5,
                                    Decimal("3"), [], float("nan"), float("inf")])
def test_quantity_requires_positive_integer(sale, invalid):
    with pytest.raises(ValueError, match="Quantity"):
        replace(sale, quantity=invalid)


@pytest.mark.parametrize("quantity", [1, 2, 1000])
def test_valid_quantities(sale, quantity):
    result = replace(sale, quantity=quantity)
    assert result.calculate_total() == Decimal("8000") * quantity


@pytest.mark.parametrize("invalid", [None, True, False, 0, -1, "-0.01", "-0",
                                    "", "bad", [], {}, object(), "NaN", "sNaN",
                                    "Infinity", "-Infinity", float("nan"),
                                    float("inf"), float("-inf"), Decimal("NaN"),
                                    Decimal("sNaN"), Decimal("Infinity"),
                                    Decimal("-Infinity")])
def test_invalid_unit_prices(sale, invalid):
    with pytest.raises(ValueError):
        replace(sale, unit_selling_price=invalid)


@pytest.mark.parametrize("price", [Decimal("10.10"), "10.10", 10.1, 10])
def test_price_conversion_and_exact_totals(sale, price):
    result = replace(sale, unit_selling_price=price)
    assert isinstance(result.unit_selling_price, Decimal)
    assert result.unit_selling_price == Decimal(str(price))
    assert result.calculate_total() == Decimal(str(price)) * 3


def test_calculations_do_not_add_rounding(sale):
    result = replace(sale, quantity=3, unit_selling_price="0.005")
    assert result.calculate_total() == Decimal("0.015")


def test_frozen_fields_cannot_be_assigned_or_deleted(sale):
    for field in sale.__dataclass_fields__:
        with pytest.raises(FrozenInstanceError):
            setattr(sale, field, None)
        with pytest.raises(FrozenInstanceError):
            delattr(sale, field)


def test_original_price_survives_new_sale_price(sale):
    original = replace(sale, product_id="P1")
    newer = replace(original, sale_id="PS2", unit_selling_price="9000")
    assert original.unit_selling_price == Decimal("8000")
    assert original.calculate_total() == Decimal("24000")
    assert newer.unit_selling_price == Decimal("9000")
    assert newer.calculate_total() == Decimal("27000")


def test_replacements_are_revalidated(sale):
    with pytest.raises(ValueError):
        replace(sale, quantity=0)
    with pytest.raises(ValueError):
        replace(sale, unit_selling_price="NaN")


def test_valid_text_is_preserved(sale):
    result = replace(sale, sale_id=" PS1 ", product_description=" Oil, 100 ml ",
                     product_id=" P1 ")
    assert result.sale_id == " PS1 "
    assert result.product_description == " Oil, 100 ml "
    assert result.product_id == " P1 "
