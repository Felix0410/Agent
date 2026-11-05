import pytest

from minideerflow.tools.calculator import CalculatorError, calculate, safe_calculate


@pytest.mark.parametrize(
    ("expression", "result"),
    [
        ("(12+8)*3", "60"),
        ("-2 + +3 * 4", "10"),
        ("0.5/2", "0.25"),
        (" 6 / 3 ", "2"),
        ("0.1+0.2", "0.30000000000000004"),
    ],
)
def test_calculate(expression: str, result: str) -> None:
    assert safe_calculate(expression) == result


@pytest.mark.parametrize(
    ("expression", "code"),
    [
        ("1/0", "CALC_DIV_ZERO"),
        ("x", "CALC_INVALID_EXPRESSION"),
        ("__import__('os')", "CALC_INVALID_EXPRESSION"),
        ("2**3", "CALC_INVALID_EXPRESSION"),
        ("1//2", "CALC_INVALID_EXPRESSION"),
        ("1%2", "CALC_INVALID_EXPRESSION"),
        ("True", "CALC_INVALID_EXPRESSION"),
        ("'3'", "CALC_INVALID_EXPRESSION"),
        ("[]", "CALC_INVALID_EXPRESSION"),
        ("1<2", "CALC_INVALID_EXPRESSION"),
        ("", "CALC_INVALID_EXPRESSION"),
        ("1" * 129, "CALC_TOO_LONG"),
        ("1e309", "CALC_OUT_OF_RANGE"),
        ("1000000000000+1", "CALC_OUT_OF_RANGE"),
        ("1000000000001-1", "CALC_OUT_OF_RANGE"),
    ],
)
def test_invalid(expression: str, code: str) -> None:
    with pytest.raises(CalculatorError) as error:
        safe_calculate(expression)
    assert error.value.code == code


def test_tool_error() -> None:
    assert calculate.invoke({"expression": "1/0"}).startswith("ERROR[CALC_DIV_ZERO]")
