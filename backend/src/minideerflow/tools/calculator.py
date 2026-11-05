"""受限四则运算工具：AST 白名单校验与可控错误返回。"""

import ast
import math
import operator

from langchain_core.tools import tool


class CalculatorError(ValueError):
    """计算器的可识别业务错误，供 HTTP 接口和 Agent 工具分别转换。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def safe_calculate(expression: str) -> str:
    """只解析白名单算术表达式，不执行输入字符串中的 Python 代码。"""
    # 1. 先限制原始输入长度，避免将过长字符串交给语法解析器。
    if len(expression) > 128:
        raise CalculatorError("CALC_TOO_LONG", "expression exceeds 128 characters")

    def checked(value: float) -> int | float:
        """统一约束数字及每一步运算的中间结果。"""
        if not math.isfinite(value) or abs(value) > 10**12:
            raise CalculatorError("CALC_OUT_OF_RANGE", "number exceeds allowed range")
        return value

    def visit(node: ast.AST) -> int | float:
        """递归访问 AST，仅接受明确允许的节点与运算符。"""
        # 2. 分别处理数值、一元正负和四则运算；其它语法节点一律拒绝。
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

    # 3. 解析并计算表达式，将语法错误和不合法节点统一为稳定错误码。
    try:
        value = visit(ast.parse(expression.strip(), mode="eval").body)
    except (SyntaxError, ValueError, RecursionError) as exc:
        if isinstance(exc, CalculatorError):
            raise
        raise CalculatorError("CALC_INVALID_EXPRESSION", "invalid expression") from None
    return str(int(value)) if value == int(value) else str(value)


# 工具描述会作为模型看到的 Tool Schema，保持原英文契约不变。
# 这里将计算错误转换成 ToolMessage 可识别的文本，而非抛出堆栈。
@tool
def calculate(expression: str) -> str:
    """Calculate arithmetic using numbers, parentheses, +, -, *, and /."""
    try:
        return safe_calculate(expression)
    except CalculatorError as exc:
        return f"ERROR[{exc.code}]: {exc.message}"
