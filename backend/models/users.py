from pydantic import BaseModel, EmailStr, Field

from backend.models._base import ReadModel


class UserBase(BaseModel):
    email: EmailStr
    display_name: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase, ReadModel):
    """Public user shape — never carries ``password_hash``."""

    is_active: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
