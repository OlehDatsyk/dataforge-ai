"""
DataForge AI - SQLAlchemy ORM models.

Design note: we do NOT store full datasets in SQLite. Datasets live as
files on disk (data/uploads for the original, data/working for the
cleaned/working copy). The database stores metadata, profiles (as JSON),
analysis history, cleaning history, reports, AI call logs, and settings.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, default=gen_id)
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)   # original, sanitized, on disk
    working_filename = Column(String, nullable=False)  # working copy, on disk
    file_type = Column(String, nullable=False)          # csv / xlsx / xls / json / tsv
    file_size_bytes = Column(Integer, default=0)
    row_count = Column(Integer, default=0)
    column_count = Column(Integer, default=0)
    columns_json = Column(JSON, default=list)            # list of column names (working)
    dtypes_json = Column(JSON, default=dict)              # column -> detected type
    status = Column(String, default="ready")              # uploading/loading/profiling/analysing/ready/error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profiles = relationship("DatasetProfile", back_populates="dataset", cascade="all, delete-orphan")
    analysis_runs = relationship("AnalysisRun", back_populates="dataset", cascade="all, delete-orphan")
    cleaning_ops = relationship("CleaningOperation", back_populates="dataset", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="dataset", cascade="all, delete-orphan")


class DatasetProfile(Base):
    __tablename__ = "dataset_profiles"

    id = Column(String, primary_key=True, default=gen_id)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    profile_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="profiles")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(String, primary_key=True, default=gen_id)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    analysis_type = Column(String, nullable=False)   # descriptive/missing/outliers/correlation/group/timeseries/kpi/ask/insights/explain_chart
    parameters_json = Column(JSON, default=dict)
    result_json = Column(JSON, default=dict)
    ai_provider = Column(String, nullable=True)
    processing_time_ms = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="analysis_runs")


class CleaningOperation(Base):
    __tablename__ = "cleaning_operations"

    id = Column(String, primary_key=True, default=gen_id)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    operation = Column(String, nullable=False)
    column = Column(String, nullable=True)
    params_json = Column(JSON, default=dict)
    rows_before = Column(Integer, default=0)
    rows_after = Column(Integer, default=0)
    columns_before = Column(JSON, default=list)
    columns_after = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="cleaning_ops")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=gen_id)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=True)
    report_type = Column(String, nullable=False)
    title = Column(String, default="")
    content_markdown = Column(Text, default="")
    content_json = Column(JSON, default=dict)
    ai_provider = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="reports")


class AILog(Base):
    __tablename__ = "ai_logs"

    id = Column(String, primary_key=True, default=gen_id)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=True)
    operation = Column(String, nullable=False)
    success = Column(Boolean, default=False)
    fallback_used = Column(Boolean, default=False)
    error_category = Column(String, nullable=True)
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class SettingRecord(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
