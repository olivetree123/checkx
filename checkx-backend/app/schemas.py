from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

Status = Literal["pending", "changes_requested", "approved"]


class Envelope[T](BaseModel):
    code: int = 0
    data: T | None = None
    message: str = "ok"


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class LoginInput(Input):
    email: EmailStr = Field(max_length=254)
    password: Annotated[
        str, StringConstraints(strip_whitespace=False, min_length=8, max_length=128)
    ]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class RegisterInput(LoginInput):
    display_name: str = Field(min_length=1, max_length=80)


Password = Annotated[str, StringConstraints(strip_whitespace=False, min_length=8, max_length=128)]


class AccountInput(Input):
    display_name: str = Field(min_length=1, max_length=80)
    email: EmailStr = Field(max_length=254)
    current_password: Password | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class PasswordInput(Input):
    current_password: Password
    new_password: Password


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str
    created_at: datetime


class ProjectInput(Input):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)


class ProjectOut(ProjectInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime
    page_count: int = 0
    design_count: int = 0
    pending_count: int = 0
    approved_count: int = 0
    changes_requested_count: int = 0
    cover_url: str | None = None


class PageOut(ProjectInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    design_count: int = 0


class DesignInput(Input):
    name: str = Field(min_length=1, max_length=180)
    notes: str = Field(default="", max_length=10000)


class ImageUpdateInput(Input):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    notes: str | None = Field(default=None, max_length=10000)
    expected_version: int | None = Field(default=None, ge=1)


class DesignOut(DesignInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    page_id: UUID
    original_name: str
    mime_type: str
    size: int
    width: int
    height: int
    version: int
    status: Status
    created_at: datetime
    updated_at: datetime
    image_url: str = ""


class ReviewFields(Input):
    content: str = Field(min_length=1, max_length=20000)
    status: Literal["changes_requested", "approved"]
    author_label: str = Field(default="", max_length=80)


class ReviewInput(ReviewFields):
    expected_version: int | None = Field(default=None, ge=1)


class ReviewOut(ReviewFields):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    design_id: UUID
    version: int
    created_at: datetime


class TokenInput(Input):
    name: str = Field(min_length=1, max_length=80)
    expires_days: int = Field(default=90, ge=1, le=365)


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    expires_at: datetime
    created_at: datetime


class TokenCreated(TokenOut):
    token: str


class ReviewResults(BaseModel):
    design: DesignOut
    reviews: list[ReviewOut]
