"""Regression tests for model validation and financial calculations."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from src.models.employee import Employee
from src.models.service import PricingType, Service
from src.models.service_assignment import ServiceAssignment


@pytest.fixture
def employee():
    return Employee("E1", "Grace", "Hair")


@pytest.mark.parametrize("model, field", [
    (Employee, "employee_id"), (Employee, "name"), (Employee, "department"),
    (Service, "service_id"), (Service, "name"), (Service, "department"),
])
@pytest.mark.parametrize("invalid", ["", " \t\n", None, 123, True])
def test_required_text(model, field, invalid):
    values = dict(name="Grace", department="Hair")
    if model is Employee:
        values["employee_id"] = "E1"
    else:
        values.update(service_id="S1", pricing_type=PricingType.VARIABLE)
    values[field] = invalid
    with pytest.raises(ValueError):
        model(**values)


@pytest.mark.parametrize("invalid", [None, 0, 1, "yes"])
def test_active_requires_boolean(invalid):
    with pytest.raises(ValueError):
        Employee("E1", "Grace", "Hair", active=invalid)


INVALID_NUMBERS = [None, True, False, "bad", "", object(), [],
                   "NaN", "sNaN", "Infinity", "-Infinity",
                   float("nan"), float("inf"), Decimal("NaN"),
                   Decimal("sNaN"), Decimal("Infinity")]


@pytest.mark.parametrize("price", INVALID_NUMBERS + [0, -1, "-0.01"])
def test_fixed_price_rejects_invalid_money(price):
    with pytest.raises(ValueError):
        Service("S1", "Cut", "Hair", PricingType.FIXED, price)


@pytest.mark.parametrize("price", [Decimal("12.50"), "12.50", 12.5, 12])
def test_fixed_price_is_decimal(price):
    service = Service("S1", "Cut", "Hair", PricingType.FIXED, price)
    assert service.fixed_price == Decimal(str(price))
    assert isinstance(service.fixed_price, Decimal)
    assert not service.requires_agreed_price()


def test_variable_pricing_rules():
    assert Service("S1", "Style", "Hair", PricingType.VARIABLE).requires_agreed_price()
    with pytest.raises(ValueError):
        Service("S1", "Style", "Hair", PricingType.VARIABLE, Decimal("10"))


@pytest.mark.parametrize("pricing_type", ["fixed", "variable", None, 1])
def test_pricing_type_requires_enum(pricing_type):
    with pytest.raises(ValueError):
        Service("S1", "Cut", "Hair", pricing_type, Decimal("10"))


@pytest.mark.parametrize("invalid", [None, "E1", object()])
def test_assignment_requires_employee(invalid):
    with pytest.raises(ValueError):
        ServiceAssignment(invalid, Decimal("100"))


@pytest.mark.parametrize("field", ["percentage", "wage_rate"])
@pytest.mark.parametrize("invalid", INVALID_NUMBERS + [-1, 101])
def test_invalid_rates(employee, field, invalid):
    values = dict(employee=employee, percentage=100, wage_rate=30)
    values[field] = invalid
    with pytest.raises(ValueError):
        ServiceAssignment(**values)


def test_rate_boundaries_and_default(employee):
    with pytest.raises(ValueError):
        ServiceAssignment(employee, 0)
    assert ServiceAssignment(employee, 100).wage_rate == Decimal("30")
    for wage_rate in (0, 100):
        assignment = ServiceAssignment(employee, "100", wage_rate)
        assert assignment.calculate_expected_wage("10") == Decimal(wage_rate) / 10
        assert isinstance(assignment.percentage, Decimal)
        assert isinstance(assignment.wage_rate, Decimal)


@pytest.mark.parametrize("method", ["calculate_contribution", "calculate_expected_wage"])
@pytest.mark.parametrize("price", INVALID_NUMBERS + [0, -1])
def test_calculations_reject_invalid_prices(employee, method, price):
    with pytest.raises(ValueError):
        getattr(ServiceAssignment(employee, 100), method)(price)


@pytest.mark.parametrize("price", [Decimal("10.10"), "10.10", 10.1])
def test_exact_decimal_calculations(employee, price):
    assignment = ServiceAssignment(employee, 50, 30)
    assert assignment.calculate_contribution(price) == Decimal("5.05")
    assert assignment.calculate_expected_wage(price) == Decimal("1.515")
    assert isinstance(assignment.calculate_expected_wage(price), Decimal)


def test_validated_fields_cannot_be_overwritten(employee):
    service = Service("S1", "Cut", "Hair", PricingType.FIXED, 10)
    assignment = ServiceAssignment(employee, 100)
    for instance in (employee, service, assignment):
        for field in instance.__dataclass_fields__:
            with pytest.raises(FrozenInstanceError):
                setattr(instance, field, None)
            with pytest.raises(FrozenInstanceError):
                delattr(instance, field)


def test_valid_updates_create_revalidated_records(employee):
    assert replace(employee, active=False).active is False
    with pytest.raises(ValueError):
        replace(employee, name="")
    # Existing rules permit inactive employees and do not require department matching.
    inactive = replace(employee, active=False)
    assert ServiceAssignment(inactive, 100).employee is inactive


def test_valid_text_is_preserved():
    employee = Employee(" E1 ", " Grace ", " Hair ")
    assert (employee.employee_id, employee.name, employee.department) == (
        " E1 ", " Grace ", " Hair "
    )
