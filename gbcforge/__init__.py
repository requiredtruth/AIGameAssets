"""Local-AI content generation for small RPGs."""

from .models import ALLOWED_KINDS, ContentValidationError, GeneratedContent

__all__ = ["ALLOWED_KINDS", "ContentValidationError", "GeneratedContent"]
__version__ = "0.2.0"
