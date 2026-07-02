# omms app

omms app 运维管理后端应用

## 项目结构

项目采用分层架构设计，主要包含以下几个部分：

- `app/`: 核心应用代码
  - `app/models/`: SQLAlchemy 数据库模型
  - `app/schemas/`: Pydantic 数据模型（用于请求和响应验证）
  - `app/services/`: 业务逻辑层
  - `app/controllers/`: 控制器层，处理请求逻辑
  - `app/routes/`: API 路由定义
  - `app/utils/`: 工具函数（数据库连接、安全验证等）
  - `app/config/`: 配置管理
  - `app/main.py`: FastAPI 应用入口
- `main.py`: 项目启动脚本
- `requirements.txt`: Python 依赖配置文件
- `.env.development.example`: 开发环境配置文件
- `.env.production.example`: 生产环境配置文件
- `.env.testing.example`: 测试环境配置文件
- `tests/`: 测试脚本和工具
- `test_db.py`: 数据库表创建测试脚本

## 技术栈

- Python 3.11+
- FastAPI (Web 框架)
- SQLAlchemy (ORM 数据库访问)
- Pydantic (数据验证)
- Uvicorn (ASGI 服务器)
- PyMySQL (MySQL 数据库驱动)
- python-jose (JWT 令牌处理)
- passlib (密码哈希)

## 安装指南

### 1. 克隆项目

### 2. 创建虚拟环境

```bash
python -m venv .venv
# Windows 激活
.venv\Scripts\activate
# Linux/Mac 激活
source .venv/bin/activate
```

### 3. 安装依赖

安装所有项目依赖：

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

项目已包含三个环境的配置文件，请根据需要修改相应配置：

- `.env.development`: 开发环境配置
- `.env.testing`: 测试环境配置
- `.env.production`: 生产环境配置

主要配置项包括数据库连接信息、JWT 密钥等。

## 运行项目

### 开发环境

```bash
python main.py
```

这将以开发模式启动服务器（启用自动重载）。

### 直接使用 Uvicorn

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API 文档

项目启动后，可以访问以下地址查看自动生成的 API 文档：

- Swagger UI: http://localhost:8004/docs
- ReDoc: http://localhost:8004/redoc

