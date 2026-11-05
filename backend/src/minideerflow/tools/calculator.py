import ast
import math
import operator

from langchain_core.tools import tool


class CalculatorError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def safe_calculate(expression: str) -> str:
    if len(expression) > 128:
        raise CalculatorError("CALC_TOO_LONG", "expression exceeds 128 characters")

    def checked(value: float) -> int | float:
        if not math.isfinite(value) or abs(value) > 10**12:
            raise CalculatorError("CALC_OUT_OF_RANGE", "number exceeds allowed range")
        return value

    def visit(node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return checked(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return checked(value if isinstance(node.op, ast.UAdd) else -value)
        operations = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise CalculatorError("CALC_DIV_ZERO", "division by zero")
            return checked(operations[type(node.op)](left, right))
        raise CalculatorError("CALC_INVALID_EXPRESSION", "unsupported expression")

    try:
        value = visit(ast.parse(expression.strip(), mode="eval").body)
    except (SyntaxError, ValueError, RecursionError) as exc:
        if isinstance(exc, CalculatorError):
            raise
        raise CalculatorError("CALC_INVALID_EXPRESSION", "invalid expression") from None
    return str(int(value)) if value == int(value) else str(value)


@tool
def calculate(expression: str) -> str:
    """Calculate arithmetic using numbers, parentheses, +, -, *, and /."""
    try:
        return safe_calculate(expression)
    except CalculatorError as exc:
        return f"ERROR[{exc.code}]: {exc.message}"
