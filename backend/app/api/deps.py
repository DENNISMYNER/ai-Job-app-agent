from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db

DB = Annotated[Session, Depends(get_db)]


class PageParams:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        self.page, self.page_size = page, page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
