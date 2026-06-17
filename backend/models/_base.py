from datetime import datetime

from pydantic import BaseModel


class ReadModel(BaseModel):
    """Mixin for read models: the surrogate id and timestamps every row carries.

    Domain read models inherit ``(XBase, ReadModel)`` so these three fields live
    in one place instead of being repeated on each ``*Read`` class.
    """

    id: str
    created_at: datetime
    updated_at: datetime
