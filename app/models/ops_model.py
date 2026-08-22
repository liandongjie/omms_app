# -*- coding: utf-8 -*-
from sqlalchemy import BigInteger, Column, Index, Integer, String, Text

from app.models.database import Base


class OpsLog(Base):
    """Ops log records, append-only."""

    __tablename__ = "ops_log"

    __table_args__ = (
        # 覆盖日志查询主路径：按日期过滤 + 机器/级别筛选 + log_id 倒序分页
        Index("idx_ops_log_date_machine_level", "date", "machine_tag", "level", "log_id"),
        # 连续覆盖按日期和级别筛选，并支持单级别下按 log_id 倒序分页。
        Index("idx_ops_log_date_level_log_id", "date", "level", "log_id"),
    )

    log_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    event_id = Column(String(64), nullable=True, unique=True)
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

    __table_args__ = (
        # 覆盖配置查询主路径：type + status + group 过滤
        Index("idx_ops_cfg_type_status_group", "type", "status", "group"),
    )

    type = Column(String(8), primary_key=True)
    machine_tag = Column(String(32), primary_key=True)
    group_name = Column("group", String(32), primary_key=True)
    cfg_key = Column("key", String(128), primary_key=True)
    value = Column(Text, primary_key=True)
    work_time = Column(Text, nullable=True)
    status = Column(Integer, nullable=True)
