"""Canonical dataclasses for core dashboard domain objects.

These models are intentionally permissive so they can map to the existing
mixed dictionary shapes used across database, parsing, and reporting modules
without behavior changes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Location:
    """Restaurant/outlet location metadata."""

    id: Optional[int] = None
    name: Optional[str] = None
    target_monthly_sales: Optional[float] = None
    target_daily_sales: Optional[float] = None
    seat_count: Optional[int] = None
    created_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CategorySale:
    """Category-level sales aggregate."""

    category_name: Optional[str] = None
    amount: Optional[float] = None
    location_id: Optional[int] = None
    date: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "CategorySale":
        """Create a CategorySale from legacy dict payloads."""
        payload = data or {}
        known = {
            "category_name",
            "amount",
            "location_id",
            "date",
            "category",
            "total",
        }
        return cls(
            category_name=payload.get("category_name") or payload.get("category"),
            amount=payload.get("amount")
            if payload.get("amount") is not None
            else payload.get("total"),
            location_id=payload.get("location_id"),
            date=payload.get("date"),
            extra={k: v for k, v in payload.items() if k not in known},
        )


@dataclass
class ServiceSale:
    """Service-period sales aggregate (e.g., Lunch/Dinner)."""

    service_type: Optional[str] = None
    amount: Optional[float] = None
    location_id: Optional[int] = None
    date: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ServiceSale":
        """Create a ServiceSale from legacy dict payloads."""
        payload = data or {}
        known = {
            "service_type",
            "type",
            "amount",
            "location_id",
            "date",
            "total",
        }
        return cls(
            service_type=payload.get("service_type") or payload.get("type"),
            amount=payload.get("amount")
            if payload.get("amount") is not None
            else payload.get("total"),
            location_id=payload.get("location_id"),
            date=payload.get("date"),
            extra={k: v for k, v in payload.items() if k not in known},
        )


@dataclass
class UploadHistoryRecord:
    """One upload/audit trail row."""

    id: Optional[int] = None
    location_id: Optional[int] = None
    date: Optional[str] = None
    filename: Optional[str] = None
    file_type: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DailySummary:
    """Daily KPI snapshot plus optional detail lists."""

    id: Optional[int] = None
    location_id: Optional[int] = None
    date: Optional[str] = None
    covers: Optional[int] = None
    lunch_covers: Optional[int] = None
    dinner_covers: Optional[int] = None
    order_count: Optional[int] = None
    turns: Optional[float] = None
    gross_total: Optional[float] = None
    net_total: Optional[float] = None
    cash_sales: Optional[float] = None
    card_sales: Optional[float] = None
    gpay_sales: Optional[float] = None
    zomato_sales: Optional[float] = None
    other_sales: Optional[float] = None
    service_charge: Optional[float] = None
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    discount: Optional[float] = None
    complimentary: Optional[float] = None
    apc: Optional[float] = None
    target: Optional[float] = None
    pct_target: Optional[float] = None
    mtd_total_covers: Optional[int] = None
    mtd_net_sales: Optional[float] = None
    mtd_discount: Optional[float] = None
    mtd_avg_daily: Optional[float] = None
    mtd_target: Optional[float] = None
    mtd_pct_target: Optional[float] = None
    categories: List[Dict[str, Any]] = field(default_factory=list)
    services: List[Dict[str, Any]] = field(default_factory=list)
    top_items: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DailySummary":
        """Create a DailySummary from current dictionary payloads."""
        payload = data or {}
        model_fields = set(cls.__dataclass_fields__.keys())
        extra = {k: v for k, v in payload.items() if k not in model_fields}

        return cls(
            id=payload.get("id"),
            location_id=payload.get("location_id"),
            date=payload.get("date"),
            covers=payload.get("covers"),
            lunch_covers=payload.get("lunch_covers"),
            dinner_covers=payload.get("dinner_covers"),
            order_count=payload.get("order_count"),
            turns=payload.get("turns"),
            gross_total=payload.get("gross_total"),
            net_total=payload.get("net_total"),
            cash_sales=payload.get("cash_sales"),
            card_sales=payload.get("card_sales"),
            gpay_sales=payload.get("gpay_sales"),
            zomato_sales=payload.get("zomato_sales"),
            other_sales=payload.get("other_sales"),
            service_charge=payload.get("service_charge"),
            cgst=payload.get("cgst"),
            sgst=payload.get("sgst"),
            discount=payload.get("discount"),
            complimentary=payload.get("complimentary"),
            apc=payload.get("apc"),
            target=payload.get("target"),
            pct_target=payload.get("pct_target"),
            mtd_total_covers=payload.get("mtd_total_covers"),
            mtd_net_sales=payload.get("mtd_net_sales"),
            mtd_discount=payload.get("mtd_discount"),
            mtd_avg_daily=payload.get("mtd_avg_daily"),
            mtd_target=payload.get("mtd_target"),
            mtd_pct_target=payload.get("mtd_pct_target"),
            categories=list(payload.get("categories") or []),
            services=list(payload.get("services") or []),
            top_items=list(payload.get("top_items") or []),
            created_at=payload.get("created_at"),
            extra=extra,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict while preserving unknown passthrough fields."""
        data = asdict(self)
        extra = data.pop("extra", {}) or {}
        data.update(extra)
        return data
