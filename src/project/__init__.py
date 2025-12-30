"""Project Kernel (Intent Plane) for Project Vyasa.

Manages project configurations, research questions, and scope definitions.
"""

from .types import ProjectConfig, ProjectCreate, ProjectSummary
from .service import ProjectService

__all__ = ["ProjectConfig", "ProjectCreate", "ProjectSummary", "ProjectService"]

