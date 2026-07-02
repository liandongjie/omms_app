from app.config.base import BaseConfig
from pydantic import Field


class DevelopmentConfig(BaseConfig):
    """开发环境配置"""
    environment: str = "development"  # 显式定义 environment
    host: str = "0.0.0.0"  # 显式定义 host

    # 服务器配置 - 使用int类型的默认值，与.env.development保持一致
    PORT: int = Field(ge=1024, le=65535, default=8000)

    # 数据库配置 - 添加.env.development中定义的数据库连接字段
    db_host: str = Field(default="", alias="DB_HOST")
    db_port: str = Field(default="", alias="DB_PORT")
    db_name: str = Field(default="", alias="DB_NAME")
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")

    LOG_LEVEL: str = "DEBUG"

    # 开发环境特有配置
    DEBUG: bool = True
    RELOAD: bool = True

    # CORS配置
    allowed_origins: str = Field(default="http://localhost:3000")

    class Config:
        env_file = ".env.development"