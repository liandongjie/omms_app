import logging
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

# 配置日志
logger = logging.getLogger(__name__)

# 获取数据库配置
settings = get_settings()


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
    try:
        # 构建MySQL连接URL
        mysql_url = build_mysql_url(settings)

        # 检查并记录连接池配置
        _log_pool_config()

        # 创建数据库引擎
        db_engine = create_engine(
            mysql_url,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=True,  # 连接前检查连接是否有效
            echo=False,  # 生产环境设置为False，开发环境可以设置为True进行调试
            connect_args={
                'connect_timeout': 300,  # 连接超时时间（秒）
                'read_timeout': 300,  # 读取超时时间（秒）
                'write_timeout': 300,  # 写入超时时间（秒）
                'charset': 'utf8mb4',  # 字符集
            }
        )

        return db_engine

    except SQLAlchemyError as e:
        logger.error(f"数据库连接错误: {str(e)}", exc_info=True)
        raise


def _log_pool_config():
    """记录数据库连接池配置信息"""
    logger.info(
        f"数据库连接池配置: pool_size={settings.DATABASE_POOL_SIZE}, "
        f"max_overflow={settings.DATABASE_MAX_OVERFLOW}, "
        f"pool_timeout={settings.DATABASE_POOL_TIMEOUT}s, "
        f"pool_recycle={settings.DATABASE_POOL_RECYCLE}s"
    )


# 创建数据库引擎
try:
    engine = create_db_engine()
except SQLAlchemyError:
    # 连接失败时使用空池作为后备方案
    logger.warning("使用空连接池作为后备方案")
    engine = create_engine("sqlite:///:memory:", poolclass=NullPool)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # 提交后不自动过期对象
)


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
