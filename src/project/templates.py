"""
Project Templates for Project Creation Wizard.

Provides pre-configured templates with suggested RQs, anti-scope, and rigor settings.
These templates can be managed server-side and extended without frontend changes.
"""

from typing import List
from pydantic import BaseModel


class ProjectTemplate(BaseModel):
    """Template definition for project creation."""
    
    id: str
    name: str
    description: str
    suggested_rqs: List[str]
    suggested_anti_scope: List[str]
    suggested_rigor: str  # "exploratory" or "conservative"
    example_thesis: str = ""


# Default templates (can be extended or loaded from DB/config file)
DEFAULT_TEMPLATES: List[ProjectTemplate] = [
    ProjectTemplate(
        id="security-analysis",
        name="Security Analysis",
        description="Analyze security vulnerabilities and mitigation strategies",
        suggested_rqs=[
            "What are the most common security vulnerabilities in this domain?",
            "How effective are existing mitigation strategies?",
            "What are the trade-offs between security and usability?",
        ],
        suggested_anti_scope=[
            "Hardware security",
            "Physical security",
            "Social engineering attacks",
        ],
        suggested_rigor="conservative",
        example_thesis="Modern web applications are vulnerable to injection attacks despite widespread awareness of the risks.",
    ),
    ProjectTemplate(
        id="performance-optimization",
        name="Performance Optimization",
        description="Investigate performance bottlenecks and optimization techniques",
        suggested_rqs=[
            "What are the primary performance bottlenecks in this system?",
            "Which optimization techniques provide the best ROI?",
            "How do different optimization strategies compare in practice?",
        ],
        suggested_anti_scope=[
            "Hardware upgrades",
            "Network infrastructure",
            "Third-party service dependencies",
        ],
        suggested_rigor="exploratory",
        example_thesis="Performance optimization requires a systematic approach to identify and address bottlenecks.",
    ),
    ProjectTemplate(
        id="ml-model-evaluation",
        name="ML Model Evaluation",
        description="Evaluate machine learning models and their real-world performance",
        suggested_rqs=[
            "How do different evaluation metrics reflect real-world performance?",
            "What are the limitations of current evaluation approaches?",
            "How can we improve model generalization?",
        ],
        suggested_anti_scope=[
            "Model training procedures",
            "Data collection methods",
            "Hardware requirements",
        ],
        suggested_rigor="conservative",
        example_thesis="Traditional evaluation metrics may not accurately reflect model performance in production environments.",
    ),
    ProjectTemplate(
        id="architecture-patterns",
        name="Architecture Patterns",
        description="Study software architecture patterns and their trade-offs",
        suggested_rqs=[
            "What are the key trade-offs between different architecture patterns?",
            "When should each pattern be applied?",
            "How do patterns evolve with scale?",
        ],
        suggested_anti_scope=[
            "Implementation details",
            "Specific frameworks",
            "Legacy system migration",
        ],
        suggested_rigor="exploratory",
        example_thesis="Architecture patterns provide reusable solutions but must be chosen based on specific context and constraints.",
    ),
    ProjectTemplate(
        id="data-quality",
        name="Data Quality Analysis",
        description="Analyze data quality issues and remediation strategies",
        suggested_rqs=[
            "What are the most common data quality issues?",
            "How do data quality issues impact downstream analysis?",
            "What are effective remediation strategies?",
        ],
        suggested_anti_scope=[
            "Data collection methods",
            "Storage infrastructure",
            "Real-time processing",
        ],
        suggested_rigor="conservative",
        example_thesis="Data quality issues can significantly impact the reliability of analytical results and decision-making.",
    ),
]


def get_all_templates() -> List[ProjectTemplate]:
    """Get all available project templates.
    
    Returns:
        List of ProjectTemplate objects.
        
    Note: In the future, this could load templates from a database or config file.
    """
    return DEFAULT_TEMPLATES.copy()


def get_template_by_id(template_id: str) -> ProjectTemplate | None:
    """Get a template by its ID.
    
    Args:
        template_id: The template identifier.
        
    Returns:
        ProjectTemplate if found, None otherwise.
    """
    templates = get_all_templates()
    return next((t for t in templates if t.id == template_id), None)

