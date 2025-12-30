"""Manuscript Kernel for Project Vyasa.

Handles block-level document synthesis, versioning, and citation validation.
"""

from .service import ManuscriptService
from ..shared.schema import ManuscriptBlock, PatchObject

__all__ = ["ManuscriptService", "ManuscriptBlock", "PatchObject"]

