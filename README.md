# OMMS 运维监控系统

OMMS 是一个面向内部运维场景的前后端一体化监控系统，当前主要提供：

- 监控总览；
- OS 资源与在线状态；
- 关键进程状态；
- 最近日志查询；
- 按配置分组筛选。

后端从 MySQL 中读取 `ops_cfg`、`ops_state`、`ops_log`，计算监控状态并通过 `/api_omms` 接口提供给前端；前端优先通过 WebSocket 接收实时刷新事件，连接异常时自动回退到 5 秒轮询。

工程化与性能增强（已完成）：

- 统一异常处理与请求日志中间件（method / path / status / duration）；
- Redis 旁路缓存（TTL 3 秒，Redis 不可用时自动降级直查数据库）；
- RabbitMQ 消费端 + 模拟生产者，数据链路“上游 → MQ → 消费端 → MySQL → API → 前端”完整可控；
- WebSocket 实时推送（`/ws/monitor`）与轮询兜底；
- `ops_log` / `ops_cfg` 复合索引，指定分组时状态查询下推；
- `/health` 健康检查；MySQL 不可用时启动即失败（fail-fast），不再静默降级 SQLite。

## 技术栈

### 后端

- Python 3.11+
- FastAPI
- SQLAlchemy
- Pydantic
- PyMySQL / MySQL
- Uvicorn
- pytest

### 前端

- Vue 3
- TypeScript
- Vite
- Ant Design Vue
- Axios

## 项目结构

```text
omms_app/
├─ app/
│  ├─ config/          # 环境配置、监控阈值和分页配置
│  ├─ controllers/     # 请求参数适配、返回字段转换、排序和分页
│  ├─ models/          # SQLAlchemy 数据库模型
│  ├─ routes/          # FastAPI 路由
│  ├─ schemas/         # Pydantic 请求、响应和领域模型
│  ├─ services/        # 核心业务逻辑
│  ├─ utils/           # 数据库、时间和字段解析工具
│  └─ main.py          # FastAPI 应用入口
├─ frontend/
│  ├─ src/             # Vue 页面、API 和组件
│  ├─ package.json     # 前端命令和依赖
│  └─ vite.config.ts   # 开发服务器及 API 代理
├─ docs/
│  └─ api_omms_monitor_overview.md
├─ tests/
│  ├─ test_monitor_overview_compat.py
│  ├─ test_ops_parse.py
│  └─ test_ops_service.py
├─ main.py             # 后端启动脚本
├─ requirements.txt
├─ pytest.ini
└─ .env.*.example      # 环境变量示例
```

## 核心数据表

| 表 | 作用 |
|---|---|
| `ops_cfg` | 启用的监控配置、分组和工作时间 |
| `ops_state` | 按日期、类型和机器保存的最新状态 |
| `ops_log` | 追加保存的日志记录 |

数据库没有通过外键维护三张表的关系，关联和状态判断由 `app/services/ops_service.py` 完成。

## 后端本地开发

以下命令以 Windows PowerShell 和项目路径 `D:\omms_app` 为例。

### 1. 进入项目目录

```powershell
cd D:\omms_app
```

### 2. 创建虚拟环境

```powershell
python -m venv .venv
```

可以激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

也可以不激活，后续直接调用虚拟环境中的 Python。

### 3. 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. 配置开发环境

复制示例文件：

```powershell
Copy-Item .env.development.example .env.development
```

然后填写实际数据库配置：

```dotenv
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8004

DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=omms_app
DB_USER=root
DB_PASSWORD=your_password
```

不要把真实密码提交到 Git。

### 5. 启动后端

推荐使用：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

开发时需要自动重载，可以追加：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8004
```

也可以运行根目录启动脚本：

```powershell
.\.venv\Scripts\python.exe main.py
```

启动后可访问：

- Swagger UI：`http://127.0.0.1:8004/docs`
- ReDoc：`http://127.0.0.1:8004/redoc`

## 前端本地开发

另开一个 PowerShell 窗口：

```powershell
cd D:\omms_app\frontend
```

首次安装依赖：

```powershell
npm ci
```

启动前端：

```powershell
npm run dev -- --host 0.0.0.0 --port 5173
```

当前 Vite 开发服务器会把 `/api_omms` 代理到：

```text
http://127.0.0.1:8004
```

因此本地联调时，后端需要在同一台电脑的 `8004` 端口运行。

## 局域网访问

后端和前端都使用：

```text
--host 0.0.0.0
```

表示监听本机所有网络接口，允许局域网中的其他电脑访问。

如果只监听：

```text
127.0.0.1
```

则只有本机可以访问。

Vite 启动后通常会显示：

```text
Local:   http://localhost:5173/
Network: http://192.168.1.23:5173/
```

将实际显示的 `Network` 地址发给局域网内的访问者，例如：

```text
http://192.168.1.23:5173/
```

如无法访问，请检查：

- 两台电脑是否位于可互通的局域网；
- Windows 防火墙是否允许 Python、Node.js 或对应端口；
- `5173` 和 `8004` 端口是否被其他进程占用；
- 前端所在电脑是否能够访问本机后端 `127.0.0.1:8004`。

## Docker 基础设施

根目录 `docker-compose.yml` 提供 MySQL / Redis / RabbitMQ 三个服务：

```powershell
docker compose up -d
```

- MySQL：`127.0.0.1:3307`，首次启动自动建库并导入示例数据；
- Redis：`127.0.0.1:6380`（缓存层，不可用时自动降级；外部端口避开本地 6379）；
- RabbitMQ：`127.0.0.1:5672`（AMQP），管理台 `http://127.0.0.1:15672`（omms / omms_dev）。

后端启动前把 `.env.docker.example` 复制为 `.env`，并设置 `ENVIRONMENT=docker`（或按需修改连接参数）。

## 数据生成与模拟生产者

```powershell
# 生成 5 万状态 + 5 万日志 + 50 台机器的压测基线（清空重建，可重复执行）
.\.venv\Scripts\python.exe -m scripts.generate_data --states 50000 --logs 50000 --machines 50 --truncate

# 模拟上游生产者：向 RabbitMQ 发布消息（配合消费端演示完整链路）
.\.venv\Scripts\python.exe -m scripts.mq_producer --count 1000 --rate 20
```

## 测试与构建

### 后端测试

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### 前端类型检查和生产构建

```powershell
cd frontend
npm run build
```

当前 `build` 命令会依次执行 TypeScript 类型检查和 Vite 生产构建。

## 当前接口

当前正式注册的接口为：

```text
GET  /api_omms/monitor/overview/total
GET  /api_omms/monitor/group/list
POST /api_omms/monitor/overview/os/list
POST /api_omms/monitor/overview/process/list
POST /api_omms/monitor/overview/log/list
GET  /health                                    # 健康检查
WS   /ws/monitor                                # 实时推送（事件驱动刷新）
```

详细请求参数、返回字段和统计口径见：

- [`docs/api_omms_monitor_overview.md`](docs/api_omms_monitor_overview.md)

## 开发注意事项

- 当前 `app/main.py` 注册 `/api_omms`、`/health`、`/ws/monitor` 和 `/api_test`；不要仅凭文件存在认定其他路由已经生效。
- OS、进程的状态不是数据库直接存储的最终值，而是后端根据配置、上报时间和指标动态计算。
- 修改监控统计、匹配或分页逻辑时，应同时检查 Service、Controller、Schema、前端展示和相关测试。
- 不要提交 `.env.development`、数据库密码、令牌或其他真实凭据。
