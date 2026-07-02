from app.config.base import BaseConfig
from pydantic import Field


class ProductionConfig(BaseConfig):
    """生产环境配置"""
    environment: str = "production"  # 显式定义 environment
    host: str = "0.0.0.0"  # 显式定义 host

    # 数据库配置 - 添加.env.production中定义的数据库连接字段
    db_host: str = Field(default="", alias="DB_HOST")
    db_port: str = Field(default="", alias="DB_PORT")
    db_name: str = Field(default="", alias="DB_NAME")
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")

    # 覆盖基础配置中的某些值
    LOG_LEVEL: str = "WARNING"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # 生产环境特有配置
    DEBUG: bool = False
    RELOAD: bool = False

    # CORS配置
    allowed_origins: str = Field(default="https://example.com")

    class Config:
        env_file = ".env.production"
