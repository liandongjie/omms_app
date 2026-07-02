from app.config.base import BaseConfig
from pydantic import Field


class TestingConfig(BaseConfig):
    """测试环境配置"""
    environment: str = "testing"  # 显式定义 environment
    host: str = "0.0.0.0"  # 显式定义 host

    # 数据库配置 - 添加.env.development中定义的数据库连接字段
    db_host: str = Field(default="", alias="DB_HOST")
    db_port: str = Field(default="", alias="DB_PORT")
    db_name: str = Field(default="", alias="DB_NAME")
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")


    # 测试环境特有配置
    TESTING: bool = True

    # CORS配置
    allowed_origins: str = Field(default="http://localhost:3000")

    class Config:
        env_file = ".env.testing"
