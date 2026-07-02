import os
from typing import Optional

from app.config.base import BaseConfig
from app.config.development import DevelopmentConfig
from app.config.production import ProductionConfig
from app.config.testing import TestingConfig

# 配置映射
config_classes = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig
}

# 全局配置实例
_config: Optional[BaseConfig] = None
_config_environment: Optional[str] = None

def get_settings() -> BaseConfig:
    """获取当前环境的配置实例"""
    global _config, _config_environment
    current_env = os.getenv("ENVIRONMENT", "development")
    
    # 如果配置未初始化或环境发生变化，重新创建配置实例
    if _config is None or _config_environment != current_env:
        config_class = config_classes.get(current_env, DevelopmentConfig)
        _config = config_class()
        _config_environment = current_env
    
    return _config