import os

from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    """基础配置类，所有环境共享的配置"""

    # 应用信息
    VERSION: str = "0.1.0"
    PROJECT_NAME: str = "alpha app"

    # 数据库连接池配置
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", 10))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", 30))
    DATABASE_POOL_TIMEOUT: int = int(os.getenv("DATABASE_POOL_TIMEOUT", 30))
    DATABASE_POOL_RECYCLE: int = int(os.getenv("DATABASE_POOL_RECYCLE", 3600))

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Ops monitor thresholds and pagination defaults
    OPS_OFFLINE_TIMEOUT_MINUTES: int = 3
    OPS_CPU_ALARM_THRESHOLD: int = 100
    OPS_MEM_ALARM_THRESHOLD: int = 90
    OPS_DISK_ALARM_THRESHOLD: int = 90
    OPS_DEFAULT_PAGE_NO: int = 1
    OPS_DEFAULT_PAGE_SIZE: int = 10
    OPS_MAX_PAGE_SIZE: int = 100
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"