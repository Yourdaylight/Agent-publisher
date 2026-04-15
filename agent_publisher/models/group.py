"""Permission group models: UserGroup and UserGroupMember."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class UserGroup(Base):
    """A named permission group. Members can see each other's articles."""

    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[str] = mapped_column(String(200), default="")  # admin email
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list["UserGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UserGroup id={self.id} name={self.name!r}>"


class UserGroupMember(Base):
    """Association between a user (email) and a UserGroup."""

    __tablename__ = "user_group_members"
    __table_args__ = (UniqueConstraint("group_id", "email", name="uq_group_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("user_groups.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(200), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped["UserGroup"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return f"<UserGroupMember group_id={self.group_id} email={self.email!r}>"
