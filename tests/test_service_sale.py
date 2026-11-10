"""Sale-level validation and historical wage regression tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from src.models.employee import Employee
from src.models.service import PricingType, Service
from src.models.service_assignment import ServiceAssignment
from src.models.service_sale import ServiceSale


@pytest.fixture
def sale():
    return ServiceSale(
        sale_id="SALE1",
        service=Service("S1", "Braiding", "Hair", PricingType.VARIABLE),
        sale_date=date(2026, 11, 10),
        agreed_price="10000",
        assignments=(
            ServiceAssignment(Employee("E1", "Grace", "Hair"), 60, 30),
            ServiceAssignment(Employee("E2", "Alex", "Hair"), 40, 20),
        ),
    )


@pytest.mark.parametrize("price", [None, "12.50", 12.5, Decimal("12.50")])
def test_fixed_price_resolution(sale, price):
    service = Service("S2", "Cut", "Hair", PricingType.FIXED, "12.50")
    result = replace(sale, service=service, agreed_price=price)
    assert result.agreed_price == Decimal("12.50")
    assert isinstance(result.agreed_price, Decimal)


def test_fixed_price_mismatch(sale):
    service = Service("S2", "Cut", "Hair", PricingType.FIXED, 10)
    with pytest.raises(ValueError, match="match"):
        replace(sale, service=service, agreed_price=11)


@pytest.mark.parametrize("price", [None, True, False, 0, -1, "", "bad", [],
                                  object(), "NaN", "sNaN", "Infinity",
                                  "-Infinity", float("nan"), float("inf"),
                                  Decimal("NaN"), Decimal("sNaN")])
@pytest.mark.parametrize("fixed", [False, True])
def test_invalid_prices(sale, price, fixed):
    if fixed:
        sale = replace(sale, service=Service(
            "S2", "Cut", "Hair", PricingType.FIXED, 10000
        ))
        if price is None:  # Omission is valid only for fixed pricing.
            assert replace(sale, agreed_price=None).agreed_price == Decimal("10000")
            return
    with pytest.raises(ValueError):
        replace(sale, agreed_price=price)


@pytest.mark.parametrize("price", ["10.10", Decimal("10.10"), 10.1, 10])
def test_variable_prices_are_decimal(sale, price):
    result = replace(sale, agreed_price=price)
    assert result.agreed_price == Decimal(str(price))
    assert isinstance(result.agreed_price, Decimal)
    assert result.service.fixed_price is None


@pytest.mark.parametrize("shares", [(50, 40), (60, 50), (99, ),
                                   (Decimal("60"), Decimal("39.999"))])
def test_percentages_must_total_100(sale, shares):
    assignments = tuple(
        replace(assignment, percentage=share)
        for assignment, share in zip(sale.assignments, shares)
    )
    with pytest.raises(ValueError, match="100"):
        replace(sale, assignments=assignments)


def test_fractional_percentages_and_no_rounding(sale):
    assignments = (replace(sale.assignments[0], percentage="33.3"),
                   replace(sale.assignments[1], percentage="66.7"))
    result = replace(sale, agreed_price="10.10", assignments=assignments)
    assert result.calculate_employee_contribution("E1") == Decimal("3.3633")
    assert result.calculate_employee_expected_wage("E1") == Decimal("1.00899")
    assert sum((result.calculate_employee_contribution(a.employee.employee_id)
                for a in assignments), Decimal("0")) == result.agreed_price


def test_duplicate_employee_ids(sale):
    duplicate = replace(sale.assignments[1], employee=Employee("E1", "Other", "Nails"))
    with pytest.raises(ValueError, match="once"):
        replace(sale, assignments=(sale.assignments[0], duplicate))


@pytest.mark.parametrize("assignments", [None, [], (), "bad", 123, {},
                                        [None], ["E1"], [object()]])
def test_invalid_assignments(sale, assignments):
    with pytest.raises(ValueError):
        replace(sale, assignments=assignments)


def test_individual_and_total_wages(sale):
    assert sale.calculate_employee_contribution("E1") == Decimal("6000")
    assert sale.calculate_employee_contribution("E2") == Decimal("4000")
    assert sale.calculate_employee_expected_wage("E1") == Decimal("1800")
    assert sale.calculate_employee_expected_wage("E2") == Decimal("800")
    assert sale.calculate_total_expected_wage() == Decimal("2600")
    assert isinstance(sale.calculate_total_expected_wage(), Decimal)


@pytest.mark.parametrize("rate", [0, 100])
def test_single_assignment_wage_boundaries(sale, rate):
    assignment = replace(sale.assignments[0], percentage=100, wage_rate=rate)
    result = replace(sale, assignments=(assignment,))
    assert result.calculate_total_expected_wage() == Decimal("10000") * rate / 100


def test_historical_wage_rates_and_list_isolation(sale):
    original = list(sale.assignments)
    recorded = replace(sale, assignments=original)
    original[0] = replace(original[0], wage_rate=50)
    original.clear()
    assert isinstance(recorded.assignments, tuple)
    assert recorded.assignments[0].wage_rate == Decimal("30")
    assert recorded.calculate_total_expected_wage() == Decimal("2600")
    newer = replace(recorded, assignments=(
        replace(recorded.assignments[0], wage_rate=50), recorded.assignments[1]
    ))
    assert newer.calculate_total_expected_wage() == Decimal("3800")
    assert recorded.calculate_total_expected_wage() == Decimal("2600")
    with pytest.raises(FrozenInstanceError):
        recorded.assignments[0].wage_rate = Decimal("50")


@pytest.mark.parametrize("field,value", [
    ("sale_id", ""), ("sale_id", " \t"), ("sale_id", None), ("sale_id", 1),
    ("service", None), ("service", "S1"), ("service", object()),
    ("sale_date", None), ("sale_date", "2026-11-10"), ("sale_date", True),
    ("sale_date", datetime(2026, 11, 10)),
    ("service_description", 123), ("service_description", True),
    ("service_description", []),
])
def test_invalid_fields(sale, field, value):
    with pytest.raises(ValueError):
        replace(sale, **{field: value})


@pytest.mark.parametrize("description", [None, "", " ", "Knotless braids, small, waist length"])
def test_optional_description_does_not_set_price(sale, description):
    result = replace(sale, service_description=description)
    assert result.service_description == description
    assert result.service.fixed_price is None
    assert result.agreed_price == Decimal("10000")
    with pytest.raises(ValueError):
        replace(result, agreed_price=None)


@pytest.mark.parametrize("method", ["calculate_employee_contribution",
                                   "calculate_employee_expected_wage"])
@pytest.mark.parametrize("employee_id", ["unknown", "", " ", None, 123])
def test_unknown_or_invalid_employee_lookup(sale, method, employee_id):
    with pytest.raises(ValueError):
        getattr(sale, method)(employee_id)


def test_sale_is_frozen(sale):
    for field in sale.__dataclass_fields__:
        with pytest.raises(FrozenInstanceError):
            setattr(sale, field, None)
        with pytest.raises(FrozenInstanceError):
            delattr(sale, field)


def test_inactive_and_other_department_employees_remain_allowed(sale):
    employee = replace(sale.assignments[0].employee, active=False, department="Nails")
    assignment = replace(sale.assignments[0], employee=employee, percentage=100)
    result = replace(sale, assignments=(assignment,))
    assert result.calculate_employee_expected_wage(employee.employee_id) == Decimal("3000")


def test_recorded_price_survives_catalog_replacement(sale):
    service = Service("S2", "Cut", "Hair", PricingType.FIXED, 10000)
    recorded = replace(sale, service=service, agreed_price=None)
    updated_service = replace(service, fixed_price=12000)
    assert updated_service.fixed_price == Decimal("12000")
    assert recorded.agreed_price == Decimal("10000")
