from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Date,
    DateTime
)

from sqlalchemy.orm import relationship

from datetime import datetime

from app.database import Base


# =========================
# USER MODEL
# =========================

class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, index=True)

    password = Column(String)

    readings = relationship(
        "Reading",
        back_populates="user"
    )

    api_keys = relationship(
        "APIKey",
        back_populates="user"
    )


# =========================
# READING MODEL
# =========================

class Reading(Base):

    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    reading_date = Column(Date)

    units = Column(Float)

    user = relationship(
        "User",
        back_populates="readings"
    )


# =========================
# API KEY MODEL
# =========================

class APIKey(Base):

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)

    api_key = Column(
        String,
        unique=True
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    user = relationship(
        "User",
        back_populates="api_keys"
    )


# =========================
# API LOG MODEL
# =========================


class APILog(Base):
    __tablename__ = "api_logs"

    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String)
    endpoint = Column(String)
    method = Column(String)
    status_code = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
class API(Base):

    __tablename__ = "apis"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(String)

    route = Column(
        String,
        unique=True
    )

    upstream_url = Column(String)

    owner_id = Column(
        Integer,
        ForeignKey("users.id")
    )


class UsageLog(Base):

    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)

    api_key = Column(String)

    endpoint = Column(String)

    method = Column(String)

    status_code = Column(Integer)

    timestamp = Column(DateTime, default=datetime.utcnow)
class Billing(Base):

    __tablename__ = "billing"

    id = Column(Integer, primary_key=True, index=True)

    api_key = Column(String)

    total_requests = Column(Integer, default=0)

    total_cost = Column(Float, default=0.0)

    plan = Column(String, default="free")
class Subscription(Base):

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer)

    plan_name = Column(String)

    price = Column(Float)

    request_limit = Column(Integer)

    status = Column(String, default="Active")