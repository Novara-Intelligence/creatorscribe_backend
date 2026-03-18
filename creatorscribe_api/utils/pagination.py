import math
from typing import TypeVar, Generic, List, Any
from ninja import Schema

T = TypeVar('T')


class PaginationMeta(Schema):
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_previous: bool


def paginate(queryset, page: int = 1, limit: int = 15) -> dict:
    """
    Paginates a queryset and returns sliced data + meta.

    Usage:
        result = paginate(qs, page=page, limit=limit)
        result['data']  -> sliced queryset
        result['meta']  -> PaginationMeta dict
    """
    page = max(1, page)
    limit = max(1, limit)

    total = queryset.count()
    total_pages = math.ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit

    return {
        "data": queryset[offset: offset + limit],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
    }
