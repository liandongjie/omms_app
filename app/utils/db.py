import logging
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

# 配置日志
logger = logging.getLogger(__name__)

# 获取数据库配置
settings = get_settings()

# 当前运行环境（development / testing / production；docker 走 development 配置）
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def build_mysql_url(s) -> str:
    """
    构建MySQL数据库连接URL
    Args:
        s: 包含数据库连接信息的配置对象
    Returns:
        str: 格式化的MySQL连接URL
    """
    # 使用urllib.parse.quote_plus更安全地处理密码中的特殊字符
    password = quote_plus(s.db_password)

    # 构建标准MySQL连接URL
    mysql_url = (
        f"mysql+pymysql://{s.db_user}:{password}@{s.db_host}:{s.db_port}/{s.db_name}"
        "?charset=utf8mb4&sql_mode=STRICT_TRANS_TABLES"
    )
    return mysql_url


def create_db_engine():
    """
    创建并配置MySQL数据库引擎
    Returns:
        sqlalchemy.engine.Engine: 配置好的数据库引擎实例
    Raises:
        SQLAlchemyError: 当数据库连接失败时抛出
    """
    # 构建MySQL连接URL
    mysql_url = build_mysql_url(settings)

    # 检查并记录连接池配置
    _log_pool_config()

    # 创建数据库引擎（此处不会真正连接，首次使用时才建立连接）
    return create_engine(
        mysql_url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,  # 连接前检查连接是否有效
        echo=False,  # 生产环境设置为False，开发环境可以设置为True进行调试
        connect_args={
            "connect_timeout": 300,  # 连接超时时间（秒）
            "read_timeout": 300,  # 读取超时时间（秒）
            "write_timeout": 300,  # 写入超时时间（秒）
            "charset": "utf8mb4",  # 字符集
        },
    )


def _log_pool_config():
    """记录数据库连接池配置信息"""
    logger.info(
        f"数据库连接池配置: pool_size={settings.DATABASE_POOL_SIZE}, "
        f"max_overflow={settings.DATABASE_MAX_OVERFLOW}, "
        f"pool_timeout={settings.DATABASE_POOL_TIMEOUT}s, "
        f"pool_recycle={settings.DATABASE_POOL_RECYCLE}s"
    )


def _create_environment_engine():
    """按运行环境创建数据库引擎。

    测试环境不连接 MySQL：单测通过 Fake 服务注入数据，路由测试通过依赖覆盖注入，
    因此测试环境保留内存 SQLite 即可，不会掩盖真实环境的连接问题。
    其他环境（development / docker / production）一律 fail-fast：
    MySQL 配置错误时直接抛出异常，禁止静默降级到 SQLite，避免出现
    “服务看似正常但接口返回空数据”的假象。
    """
    if ENVIRONMENT == "testing":
        logger.info("测试环境：使用内存 SQLite 引擎，不连接 MySQL")
        return create_engine("sqlite:///:memory:", poolclass=NullPool)
    return create_db_engine()


# 创建数据库引擎：非测试环境失败即抛出，阻断应用启动
try:
    engine = _create_environment_engine()
except SQLAlchemyError:
    logger.error("数据库引擎创建失败（fail-fast）：请检查数据库连接配置", exc_info=True)
    raise

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # 提交后不自动过期对象
)


def check_database_connection() -> None:
    """启动时主动探测数据库连接，失败立即抛出（fail-fast）。

    仅用于应用启动和 /health 探测；测试环境的内存 SQLite 无需真正连接。
    """
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def get_db():
    """
    获取数据库会话，用于依赖注入
    Yields:
        sqlalchemy.orm.session.Session: 数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
        # 会话正常结束时自动提交
        db.commit()
    except SQLAlchemyError as e:
        # 发生SQL错误时回滚
        logger.error(f"数据库会话错误: {str(e)}", exc_info=True)
        db.rollback()
        raise
    except Exception as e:
        # 捕获其他异常并记录
        logger.error(f"会话处理异常: {str(e)}", exc_info=True)
        db.rollback()
        raise
    finally:
        # 确保会话总是被关闭
        try:
            db.close()
            logger.debug("数据库会话已关闭")
        except Exception as e:
            logger.error(f"关闭数据库会话时出错: {str(e)}")
