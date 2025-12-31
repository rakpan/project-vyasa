"""
Math sandbox utilities for The Logician (neuro-symbolic expert).
"""

from __future__ import annotations

from typing import Any, Dict

from latex2sympy2 import latex2sympy
from sympy import Eq, simplify


class MathSandbox:
    """Execute symbolic math derived from LLM LaTeX output."""

    def execute_symbolic(self, latex_str: str) -> Dict[str, Any]:
        """
        Parse LaTeX into a SymPy expression, simplify, and check balance if equation.

        Returns:
            {
              "input": latex_str,
              "parsed": str(sympy_expr),
              "simplified": str(simplified_expr),
              "is_equation": bool,
              "balanced": Optional[bool],  # only for equations
            }
        """
        expr = latex2sympy(latex_str)
        simplified = simplify(expr)

        is_equation = isinstance(expr, Eq)
        balanced = None
        if is_equation:
            balanced = bool(simplify(expr.lhs - expr.rhs) == 0)

        return {
            "input": latex_str,
            "parsed": str(expr),
            "simplified": str(simplified),
            "is_equation": is_equation,
            "balanced": balanced,
        }
