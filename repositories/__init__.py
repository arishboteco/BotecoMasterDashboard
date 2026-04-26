"""Repository interfaces and implementations."""

from repositories.sales_repository import (
    DatabaseSalesRepository,
    SalesRepository,
    get_sales_repository,
)

__all__ = ["SalesRepository", "DatabaseSalesRepository", "get_sales_repository"]
