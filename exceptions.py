"""Custom exception hierarchy for Boteco Dashboard.

Usage:
    from exceptions import DataValidationError, ReportGenerationError

    raise DataValidationError("net_total must be <= gross_total")
"""


class BotecoError(Exception):
    """Base exception for all Boteco Dashboard errors."""


class DataValidationError(BotecoError):
    """Raised when uploaded data fails validation checks."""


class DatabaseError(BotecoError):
    """Raised when a database operation fails."""


class AuthenticationError(BotecoError):
    """Raised when authentication or authorization fails."""


class ReportGenerationError(BotecoError):
    """Raised when PNG/PDF report generation fails."""
