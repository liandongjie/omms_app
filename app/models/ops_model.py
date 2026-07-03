# -*- coding: utf-8 -*-
from sqlalchemy import BigInteger, Column, Integer, String, Text

from app.models.database import Base


class OpsLog(Base):
    """Ops log records, append-only."""

    __tablename__ = "ops_log"

    log_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    date = Column(String(16), nullable=True)
    machine_tag = Column(String(32), nullable=True, index=True)
    log_name = Column(String(255), nullable=True)
    level = Column(String(8), nullable=True, index=True)
    log = Column(Text, nullable=True)
    update_time = Column(String(32), nullable=True)


class OpsState(Base):
    """Latest ops state records, overwritten by upstream service."""

    __tablename__ = "ops_state"

    date = Column(String(16), primary_key=True)
    type = Column(String(8), primary_key=True)
    machine_tag = Column(String(32), primary_key=True)
    state_key = Column("key", String(128), primary_key=True)
    value = Column(String(255), primary_key=True)
    update_time = Column(String(32), nullable=True)
    dat = Column(Text, nullable=True)


class OpsCfg(Base):
    """Readonly ops monitor configuration.

    The physical table has no database primary key, so the ORM uses a logical
    composite key to make SQLAlchemy mapping possible.
    """

    __tablename__ = "ops_cfg"

    type = Column(String(8), primary_key=True)
    machine_tag = Column(String(32), primary_key=True)
    group_name = Column("group", String(32), primary_key=True)
    cfg_key = Column("key", String(128), primary_key=True)
    value = Column(Text, primary_key=True)
    work_time = Column(Text, nullable=True)
    status = Column(Integer, nullable=True)
