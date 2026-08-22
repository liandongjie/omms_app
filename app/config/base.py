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

    # Redis / RabbitMQ 与监控缓存配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    RABBITMQ_URL: str = os.getenv(
        "RABBITMQ_URL", "amqp://omms:omms_dev@127.0.0.1:5672/%2F"
    )
    # 监控领域结果缓存 TTL：小于前端 5 秒轮询周期，保证缓存不比原轮询更旧
    OPS_CACHE_TTL_SECONDS: int = int(os.getenv("OPS_CACHE_TTL_SECONDS", 3))

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Ops monitor thresholds and pagination defaults
    OPS_OFFLINE_TIMEOUT_MINUTES: int = 3
    OPS_CPU_ALARM_THRESHOLD: float = 1
    OPS_MEM_ALARM_THRESHOLD: float = 0.9
    OPS_DISK_ALARM_THRESHOLD: float = 0.9
    OPS_DEFAULT_PAGE_NO: int = 1
    OPS_DEFAULT_PAGE_SIZE: int = 10
    OPS_MAX_PAGE_SIZE: int = 100
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"