# OMMS 项目基线分析（Phase 0）

> 版本：1.0
> 日期：2026-08-21
> 适用基线分支：`main`（合并提交 `02a864a6`，当前工作分支 `ci/add-github-actions`，HEAD `0d73d9ce`）
> 编写依据：以 `main` 分支中实际注册、引用和执行的代码为准。文档与代码冲突时，以代码为准。
> 与 AGENTS.md 关系：本文档为 Phase 0 基线快照，AGENTS.md 为长期约束规范，两者互补。

## 1. 文档目的

依据软件工程 Baseline Management 原则，在任何重构或增强前明确项目当前状态，使后续各 Phase 的改进可量化、可对比、可回溯。本阶段不修改任何代码，仅产出本文档。

## 2. 项目定位

OMMS（Operation Monitoring Management System）是面向内部运维场景的前后端一体化监控系统。后端从 MySQL 读取 `ops_cfg`、`ops_state`、`ops_log`，动态计算监控状态并通过 `/api_omms` 接口提供给前端；前端每 5 秒轮询刷新展示。

当前业务范围：

- 监控总览（OS / 进程 / 日志统计卡片）；
- OS 资源与在线状态；
- 关键进程状态（含 AM/PM 盘次选择、algo00x 扩展指标）；
- 最近日志查询（数据库分页）；
- 按配置分组筛选。

## 3. 技术栈（以代码与锁文件为准）

### 3.1 后端

| 组件 | 版本 | 当前状态 |
|---|---|---|
| Python | 3.11（CI 固定） | ✅ 启用 |
| FastAPI | 0.116.1 | ✅ 启用 |
| SQLAlchemy | 2.0.43 | ✅ 启用 |
| Pydantic | 2.11.7 | ✅ 启用 |
| pydantic-settings | 2.2.1 | ✅ 启用 |
| PyMySQL | 1.1.2 | ✅ 启用 |
| uvicorn | 0.35.0 | ✅ 启用 |
| pytest | 8.4.2 | ✅ 启用 |
| httpx | 0.28.1 | ✅ 启用（测试） |
| dotenv | 0.9.9 | ✅ 启用（根 `main.py` 加载 .env） |
| pandas | 2.3.2 | ⚠️ 已安装，代码中未见使用 |
| pytz | 2025.2 | ⚠️ 已安装，代码中未见使用 |
| pika | 1.3.2 | ⚠️ 已安装，MQ 订阅逻辑已注释（`app/main.py` 中 `mq_controller = None`） |
| redis | 6.4.0 | ❌ 已安装未启用（对应 Phase 2） |
| websockets | 15.0.1 | ❌ 已安装未启用（对应 Phase 4） |
| python-jose | 3.5.0 | ❌ 已安装未启用（对应 Phase 6） |
| passlib | 1.7.4 | ❌ 已安装未启用（对应 Phase 6） |
| PyJWT | 2.10.1 | ❌ 已安装未启用（对应 Phase 6） |
| bcrypt | 3.2.0 | ❌ 已安装未启用（对应 Phase 6） |
| python-multipart | 0.0.20 | ❌ 已安装未启用 |
| email-validator | 2.3.0 | ❌ 已安装未启用 |

后端依赖共 20 项，其中实际启用 9 项，疑似未使用 3 项，明确为后续 Phase 预留未启用 8 项。

### 3.2 前端

| 组件 | 版本 | 当前状态 |
|---|---|---|
| Vue | ^3.5.13 | ✅ 启用 |
| TypeScript | ^5.7.2 | ✅ 启用 |
| Vite | ^6.0.5 | ✅ 启用 |
| **Ant Design Vue** | ^4.2.6 | ✅ 启用（**非 Element Plus**） |
| Axios | ^1.7.9 | ✅ 启用 |
| vue-tsc | ^2.2.0 | ✅ 启用（类型检查） |
| @vitejs/plugin-vue | ^5.2.1 | ✅ 启用 |

> ⚠️ **差异说明**：任务书前端技术栈写为 Element Plus，但代码实际使用 Ant Design Vue，且全部组件（OsStatusTable、ProcessStatusTable、AlgoProcessStatusTable、RecentLogTable、StatCard、SectionCard、GroupFilter、StatusTag）已基于 Ant Design Vue 实现。经确认，遵循不推翻架构原则，保持 Ant Design Vue，不迁移到 Element Plus。

## 4. 目录结构

```text
omms_app/
├─ app/                          # 后端应用
│  ├─ common/constants.py        # 公共常量
│  ├─ config/                    # 环境配置
│  │  ├─ __init__.py             # get_settings() 单例工厂
│  │  ├─ base.py                 # BaseConfig：DB 连接池、OPS 阈值、分页上限
│  │  ├─ development.py           # 开发环境
│  │  ├─ production.py           # 生产环境
│  │  └─ testing.py              # 测试环境
│  ├─ controllers/
│  │  ├─ base_controller.py      # 控制器抽象基类
│  │  ├─ monitor_overview_controller.py  # 兼容接口控制器（已注册）
│  │  ├─ ops_controller.py       # 旧控制器（未注册路由引用）
│  │  └─ test_controller.py      # 测试控制器（已注册 /api_test）
│  ├─ models/
│  │  ├─ database.py             # SQLAlchemy declarative_base
│  │  ├─ ops_model.py            # OpsCfg / OpsState / OpsLog ORM
│  │  └─ testModel.py            # 测试模型（遗留）
│  ├─ routes/
│  │  ├─ monitor_overview_route.py  # /api_omms 监控接口（已注册）
│  │  ├─ ops_route.py            # /api/ops/* 旧路由（未注册，死代码）
│  │  └─ test_route.py           # /api_test 测试路由（已注册）
│  ├─ schemas/
│  │  ├─ common.py               # ResponseModel / ErrorResponseModel
│  │  ├─ monitor_overview_schema.py  # 兼容接口请求/响应结构
│  │  ├─ ops_schema.py           # Service 层领域对象
│  │  └─ test.py                 # 测试 schema（遗留）
│  ├─ services/
│  │  ├─ base_service.py         # 服务基类
│  │  ├─ ops_service.py          # 核心业务逻辑（配置/状态匹配、状态判定、日志查询）
│  │  └─ test_service.py         # 测试服务（遗留）
│  ├─ utils/
│  │  ├─ db.py                   # MySQL Engine、SessionLocal、get_db
│  │  └─ ops_parse.py            # dat / 指标 / 时间 / 工作时间 / 进程参数解析
│  └─ main.py                    # FastAPI 应用入口、路由注册、lifespan
├─ frontend/
│  ├─ src/
│  │  ├─ api/omms.ts             # 接口类型与请求封装
│  │  ├─ views/OmmsDashboard.vue  # 主页面：状态、刷新、筛选、多页加载
│  │  ├─ components/             # 8 个展示组件
│  │  │  ├─ StatCard.vue         # 统计卡片
│  │  │  ├─ SectionCard.vue      # 区块容器
│  │  │  ├─ GroupFilter.vue      # 分组筛选
│  │  │  ├─ StatusTag.vue        # 状态标签
│  │  │  ├─ OsStatusTable.vue    # OS 表格
│  │  │  ├─ ProcessStatusTable.vue   # 普通进程表格
│  │  │  ├─ AlgoProcessStatusTable.vue  # algo00x 扩展进程表格
│  │  │  └─ RecentLogTable.vue   # 日志表格及分页
│  │  ├─ styles/global.css       # 全局样式
│  │  ├─ main.ts                 # Vue 应用入口
│  │  ├─ App.vue                 # 根组件（Antd 主题配置）
│  │  └─ vite-env.d.ts
│  ├─ package.json
│  └─ vite.config.ts             # 代理 /api_omms → 127.0.0.1:8004
├─ tests/
│  ├─ test_ops_service.py        # 核心领域与数据库查询逻辑
│  ├─ test_monitor_overview_compat.py  # Controller、兼容结构、排序、分页
│  └─ test_ops_parse.py          # 解析与时间工具
├─ docs/
│  ├─ api_omms_monitor_overview.md   # 监控接口文档
│  └─ project-baseline.md       # 本文档
├─ .github/workflows/ci.yml      # CI：后端 pytest + 前端 npm run build
├─ AGENTS.md                     # 代码代理约束规范
├─ README.md
├─ requirements.txt              # 后端依赖（20 项）
├─ pytest.ini                    # testpaths=tests
├─ main.py                       # 后端启动脚本（加载 .env + uvicorn）
├─ .env.development.example      # 开发环境变量示例
├─ .env.production.example
├─ .env.testing.example
└─ .gitignore
```

## 5. 系统架构

### 5.1 后端分层架构

```text
app/main.py                         FastAPI 应用、路由注册、lifespan
   │
   ├─ app/routes/                   路由层：参数接收、异常捕获、统一响应包装
   │   monitor_overview_route.py   注册 /api_omms 5 个端点
   │   test_route.py                注册 /api_test
   │   ops_route.py                 ❌ 未注册（遗留死代码）
   │
   ├─ app/controllers/              控制器层：请求归一化、领域对象→接口对象转换、排序、内存分页
   │   monitor_overview_controller.py  依赖注入 OpsService
   │   ops_controller.py            旧控制器（被 ops_route 引用，但路由未注册）
   │
   ├─ app/services/                 服务层：核心业务逻辑
   │   ops_service.py               配置/state 匹配、状态判定、日志查询、总览/分组/告警
   │   base_service.py              持有 db: Session
   │
   ├─ app/models/                   数据层：SQLAlchemy ORM
   │   ops_model.py                 OpsCfg / OpsState / OpsLog
   │   database.py                  declarative_base
   │
   └─ app/utils/                    工具层
       db.py                        MySQL Engine、SessionLocal、get_db 依赖
       ops_parse.py                 dat/指标/时间/工作时间/进程参数解析
```

依赖注入链：`get_db()` → `get_ops_service(db)` → `get_monitor_overview_controller(ops_service)` → 路由函数。

### 5.2 前端架构

```text
浏览器
  │  每 5 秒轮询
  ▼
frontend/src/api/omms.ts            axios 实例、类型定义、5 个请求封装
  │  requestData() 校验 code===200
  ▼
frontend/src/views/OmmsDashboard.vue  页面状态机
  │  ├─ 统计卡片（StatCard ×3）
  │  ├─ OS 表格（OsStatusTable）
  │  ├─ 进程表格（按分组动态渲染 ProcessStatusTable / AlgoProcessStatusTable）
  │  └─ 日志表格（RecentLogTable，分页）
  ▼
frontend/src/components/*.vue        8 个展示组件
```

Vite 开发服务器监听 `0.0.0.0:5173`，代理 `/api_omms` → `http://127.0.0.1:8004`。

### 5.3 数据流

```text
上游 MQ（pika，当前已注释）
   │  写入
   ▼
MySQL
   ├─ ops_cfg      启用监控配置（只读）
   ├─ ops_state    最新上报状态（被覆盖）
   └─ ops_log      追加式日志
   │  读取
   ▼
后端 OpsService
   │  配置/state 匹配 + 状态动态计算 + 日志过滤分页
   ▼
/api_omms JSON 接口
   │  每 5 秒轮询
   ▼
前端 OmmsDashboard
```

> 注意：上游 MQ 订阅逻辑在 `app/main.py` 的 `lifespan` 中已被注释（`mq_controller = None`），当前系统仅消费已存在于 MySQL 中的数据，不主动订阅 MQ。`pika` 依赖虽安装但未生效。

## 6. 请求链路（核心接口逐个标注）

当前 `app/main.py` 仅注册 2 个 router：

```python
app.include_router(test_route.router, prefix="/api_test", tags=["test"])
app.include_router(monitor_overview_route.router, tags=["monitor-overview"])
```

正式监控接口共 5 个，全部位于 `monitor_overview_route.py`：

| 方法 | 路径 | 调用链 | 分页/排序位置 |
|---|---|---|---|
| GET | `/api_omms/monitor/overview/total` | route → `controller.get_total()` → `ops_service.get_overview()` | 无分页；OS/进程统计复用明细查询 |
| GET | `/api_omms/monitor/group/list` | route → `controller.get_group_list()` → `ops_service.get_groups()` | 无分页；从 ops_cfg 提取去重分组 |
| POST | `/api_omms/monitor/overview/os/list` | route → `controller.get_os_list(req)` → `ops_service.get_os_states(group)` → ORM 查询 | **Controller 内存排序 + 内存分页**（先全量再切片） |
| POST | `/api_omms/monitor/overview/process/list` | route → `controller.get_process_list(req)` → `ops_service.get_process_states(group, include_state_only=True)` → ORM 查询 | **Controller 内存排序 + 内存分页** |
| POST | `/api_omms/monitor/overview/log/list` | route → `controller.get_log_list(req)` → `ops_service.get_logs(...)` → ORM 查询 | **数据库排序 + 数据库分页**（offset/limit） |

每个路由统一 `try/except` + `traceback.print_exc()` + 失败返回 `ErrorResponseModel`。成功返回 `ResponseModel(data=..., msg="success")`。

### 统一响应结构

```json
// 成功
{ "code": 200, "msg": "success", "data": { ... } }
// 业务异常
{ "code": 500, "msg": "error message", "errors": null }
```

> 差异点：`ErrorResponseModel` 默认 `code=500`，而 `ResponseModel` 默认 `code=200`；两者均无 HTTP 状态码区分（FastAPI 默认 200）。参数校验错误（如 `extra="forbid"` 的 schema 拒绝未知字段）由 FastAPI 自动返回 422，不经过上述 try/except。

## 7. 数据模型

三张表无数据库外键，跨表关联依赖字符串一致性（区分大小写、空格）。

### 7.1 ops_cfg（启用的监控配置，只读）

| 字段 | 类型 | 主键 | 索引 | 说明 |
|---|---|---|---|---|
| type | String(8) | ✅ PK | — | `os` / `process` |
| machine_tag | String(32) | ✅ PK | — | 机器标签 |
| group | String(32) | ✅ PK | — | 分组名（ORM 映射为 `group_name`） |
| key | String(128) | ✅ PK | — | 监控键（ORM 映射为 `cfg_key`） |
| value | Text | ✅ PK | — | 配置值（进程启动参数兜底） |
| work_time | Text | — | — | 工作时间段，如 `09:00:00-15:00:00` |
| status | Integer | — | — | 启用状态，1=启用 |

> 物理表无数据库主键。ORM 用 `type+machine_tag+group+key+value` 作逻辑复合键。重复配置和 ORM identity 合并是已知风险点。

### 7.2 ops_state（最新上报状态，被上游覆盖）

| 字段 | 类型 | 主键 | 索引 | 说明 |
|---|---|---|---|---|
| date | String(16) | ✅ PK | — | YYYYMMDD |
| type | String(8) | ✅ PK | — | `os` / `process` |
| machine_tag | String(32) | ✅ PK | — | 机器标签 |
| key | String(128) | ✅ PK | — | 状态键（ORM 映射为 `state_key`） |
| value | String(255) | ✅ PK | — | 状态值（进程参数） |
| update_time | String(32) | — | — | 上报时间 `YYYYMMDD HH:MM:SS` |
| dat | Text | — | — | JSON/字面量形式的指标数据 |

> 同一 `(machine_tag, key)` 多条 state 时，稳定选 `update_time` 最新记录。

### 7.3 ops_log（追加式日志）

| 字段 | 类型 | 主键 | 索引 | 说明 |
|---|---|---|---|---|
| log_id | BigInteger | ✅ PK | ✅ index | 自增主键 |
| date | String(16) | — | — | YYYYMMDD |
| machine_tag | String(32) | — | ✅ index | 机器标签 |
| log_name | String(255) | — | — | 日志名 |
| level | String(8) | — | ✅ index | `info`/`warn`/`error` |
| log | Text | — | — | 日志正文 |
| update_time | String(32) | — | — | 上报时间 |

> 日志按"行"统计，不按独立故障事件去重。`ops_log` 无 group 字段，按组筛选时从 `ops_cfg` 取该组 `machine_tag` 集合。

### 7.4 索引现状

| 表 | 已有索引 | 缺失索引（潜在优化点） |
|---|---|---|
| ops_cfg | 仅逻辑复合主键 | `group`、`status` 无独立索引 |
| ops_state | 仅逻辑复合主键 | `date`+`type` 联合索引、`(machine_tag, key)` 联合索引 |
| ops_log | `log_id`、`machine_tag`、`level` 单列索引 | `date`+`machine_tag` 联合、`date`+`level` 联合 |

## 8. 核心业务规则摘要

### 8.1 OS 状态判定（状态优先级不可打破）

```text
stale/offline   （工作时间内超时 / state-only 始终检查）
  ↓
parse/missing/unknown   （dat 非空但无法解析 / cpu/mem/disk 缺失）
  ↓
resource threshold/error   （cpu/mem/disk/disk_home 达阈值）
  ↓
normal
```

- `disk_home` 为可选指标：缺失不致 `unknown`，但达阈值判 `error`。
- 配置 OS 只在 `work_time` 内做 stale 判断；state-only OS 无 `work_time`，始终检查。
- 异常集合 `ABNORMAL_STATUSES = {warning, error, offline, unknown}`。

### 8.2 Process 匹配与盘次选择

- cfg/state 匹配条件（区分大小写）：`machine_tag` 相等 + `type` 相等 + `cfg.key ⊂ state.key` + (`cfg.value` 空 或 `cfg.value ⊂ state.value`)。
- 从 `state.value` 识别 `_am.yaml` / `_pm.yaml`；08:00（含）~18:00（不含）选 AM，其他选 PM。
- 目标盘次缺失时**不回退**到另一盘次或 generic。
- 所有属于配置的候选都标记已消费，避免误报为 state-only。
- `args` 优先级：有效 `state.value` → `cfg.value` → None。
- 配置进程 CPU/内存只展示，不参与阈值告警。

### 8.3 Log 过滤口径

- `date` 为空查服务器当天；`machine_tag` 精确过滤；`level` 大小写归一为小写。
- 显式 `level` 优先于 `only_error`；`only_error`（无 level 时）查 `warn+error`。
- 日志在数据库完成过滤、排序、分页；`total` 在分页前计算。
- 默认 `log_id desc`。

### 8.4 Group 规则

- 来自启用的 `ops_cfg.group`：去首尾空格、排除空值、排除界面保留名"全部"/"仅异常"、去重升序。
- `display_name` 当前等于原始 group。
- `op`、`algo00x` 等的正式业务定义不在代码中，未得业务确认前不得扩写。

### 8.5 统计口径的刻意不一致（必须保留）

| 维度 | OS | Process |
|---|---|---|
| 全部列表是否含 state-only | ✅ 含 | ✅ 含 |
| 总览 total 是否含 state-only | ✅ 含 | ❌ 不含 |

> Process 总览 total 不含 state-only，故可能小于全部分组的 Process 列表行数。这是当前实现，修改前必须明确业务口径。

## 9. 已有能力清单

| 能力域 | 功能项 | 实现位置 |
|---|---|---|
| 监控总览 | OS/进程/日志统计卡片 | `controller.get_total` + `OmmsDashboard.statCards` |
| 分组管理 | 分组列表（去重升序） | `service.get_groups` + `GroupFilter` |
| OS 状态 | CPU/内存/磁盘/磁盘2、状态判定、state-only 展示 | `service.get_os_states` + `OsStatusTable` |
| 进程状态 | AM/PM 盘次选择、algo00x 扩展指标、state-only 展示 | `service.get_process_states` + `ProcessStatusTable`/`AlgoProcessStatusTable` |
| 日志查询 | 数据库分页、级别过滤、分组过滤、复制内容 | `service.get_logs` + `RecentLogTable` |
| 排序 | OS/进程按字段排序 + 异常优先默认顺序 | `controller._sort_os_items` / `_sort_process_items` |
| 分页 | OS/进程内存分页、日志数据库分页 | Controller / Service |
| 前端交互 | 5 秒自动刷新、仅异常筛选、分组切换、多页加载合并 | `OmmsDashboard` |
| 进程告警聚合 | 内存合并 OS/进程/日志异常为告警列表（未持久化） | `service.get_alarms` |
| 持续集成 | 后端 pytest + 前端 vue-tsc + vite build | `.github/workflows/ci.yml` |
| 配置管理 | 四环境配置（dev/test/prod/base）+ 阈值可环境变量覆盖 | `app/config/` |
| 数据库连接池 | pool_size/max_overflow/timeout/recycle + pre_ping | `app/utils/db.py` |

## 10. 技术债务清单（按后续 Phase 分类）

> 风险等级：🔴 高 / 🟡 中 / 🟢 低。每项标注现状、影响与对应 Phase。

### 10.1 Phase 1 — 工程基础增强

| # | 债务项 | 现状 | 影响 | 等级 |
|---|---|---|---|---|
| 1.1 | 无全局异常处理 | 每个 route 各自 `try/except + traceback.print_exc()` | 异常处理分散、堆栈泄露到 stdout、无统一错误码体系 | 🟡 |
| 1.2 | 无请求日志中间件 | 无 access log / 请求耗时记录 | 排障困难、无 API 耗时基线 | 🟡 |
| 1.3 | 响应结构不统一 | `ResponseModel`(200) 与 `ErrorResponseModel`(500) 并存，HTTP 状态码恒 200 | 前端无法用 HTTP 状态码区分错误；422 校验错误与业务错误混杂 | 🟡 |
| 1.4 | 无容器化 | 无 Dockerfile / docker-compose.yml | 无法一键部署、本地环境与 CI/生产不一致 | 🟡 |
| 1.5 | DB 连接失败回退 sqlite | `db.py` 连接失败用 `sqlite:///:memory:` + NullPool | 生产环境静默降级为内存库，查询返回空但不报错 | 🔴 |
| 1.6 | .env 示例格式问题 | `.env.development.example` 中 `PORT=8004DB_HOST=127.0.0.1` 同行 | 复制示例后配置解析异常 | 🟢 |
| 1.7 | 根 main.py 格式问题 | `import osimport uvicorn` 等同行粘连 | 脚本无法直接运行（uvicorn 方式不受影响） | 🟢 |

### 10.2 Phase 2 — Redis 缓存优化

| # | 债务项 | 现状 | 影响 | 等级 |
|---|---|---|---|---|
| 2.1 | 无缓存层 | 每次请求直查 MySQL | 监控页 5 秒轮询重复查询，DB 压力随用户数线性增长 | 🟡 |
| 2.2 | OS/Process 全量加载 | `get_overview` 复用 `get_os_states`/`get_process_states` 全量计算 | 总览接口每次重算全部 OS/进程状态，未利用短期不变性 | 🟡 |
| 2.3 | Redis 依赖已装未用 | `redis==6.4.0` 在 requirements.txt | 预留但无 client/service 实现 | 🟢 |

### 10.3 Phase 3 — 数据库查询优化

| # | 债务项 | 现状 | 影响 | 等级 |
|---|---|---|---|---|
| 3.1 | ops_state 无联合索引 | 仅逻辑复合主键 | 按 `date`+`type` 查 state 全表扫描；`_get_states(type, date)` 每次全量加载当天全部 state | 🟡 |
| 3.2 | ops_log 无日期联合索引 | 仅 `machine_tag`/`level`/`log_id` 单列索引 | 按日期+机器或日期+级别查询无法走联合索引 | 🟡 |
| 3.3 | OS/Process 内存排序分页 | Controller 先 `get_os_states` 全量再 Python 排序切片 | 数据量大时单次请求内存与耗时上升；无法下推到 DB | 🟡 |
| 3.4 | get_alarms 日志取 200 条 | `get_alarms` 中 `get_logs(page_size=200)` 硬编码 | 告警日志可能截断；无分页遍历 | 🟢 |

### 10.4 Phase 4 — 实时监控升级

| # | 债务项 | 现状 | 影响 | 等级 |
|---|---|---|---|---|
| 4.1 | 仅轮询无推送 | 前端固定 5 秒轮询 5 个接口 | 状态变化有最长 5 秒延迟；空轮询浪费带宽 | 🟡 |
| 4.2 | 无 WebSocket 通道 | `websockets==15.0.1` 已装未用 | 无法主动推送状态变化 | 🟢 |

### 10.5 Phase 5 — 告警中心

| # | 债务项 | 现状 | 影响 | 等级 |
|---|---|---|---|---|
| 5.1 | 告警不持久化 | `get_alarms` 每次内存聚合，无 alarm/alarm_history 表 | 告警无生命周期（OPEN/PROCESSING/CLOSED）、无历史回溯、无确认闭环 | 🟡 |
| 5.2 | 告警日志截断 | `get_alarms` 只取日志第一页 200 条 | 告警日志统计可能不全 | 🟢 |

### 10.6 Phase 6 — 认证和权限

| # | 债务项 | 现状 | 影响 | 等级 |
|---|---|---|---|---|
| 6.1 | 无认证 | 所有接口匿名可访问 | 任何能访问 8004 端口的人可查看全部监控数据 | 🔴 |
| 6.2 | JWT/RBAC 依赖已装未用 | python-jose/passlib/PyJWT/bcrypt 均在 requirements | 预留但无 user/role/permission 实现 | 🟢 |

### 10.7 Phase 7 — 部署和可观测性

| # | 债务项 | 现状 | 影响 | 等级 |
|---|---|---|---|---|
| 7.1 | 无 Nginx 部署 | 开发靠 Vite 代理，生产无反向代理 | 无静态资源服务、无统一入口、无 TLS | 🟡 |
| 7.2 | 无可观测性 | 无指标采集、无结构化日志、无错误率统计 | 无 API 耗时/错误率/系统资源监控 | 🟡 |

## 11. 后续修改风险点

### 11.1 遗留死代码（修改前需评估是否清理）

| 文件 | 状态 | 风险 |
|---|---|---|
| `app/routes/ops_route.py` | 定义 `/api/ops/*` 6 个端点，但 `main.py` 未注册 | 若误以为已生效会基于错误前提修改 |
| `app/controllers/ops_controller.py` | 被 `ops_route` 引用 | 同上，整条链路未生效 |
| `app/controllers/test_controller.py` + `test_service.py` + `testModel.py` | 注册在 `/api_test` | 测试脚手架，非业务代码 |

### 11.2 跨表关联的脆弱性

- 三表无外键，关联依赖字符串精确匹配（大小写、空格）。
- 修改 `machine_tag`、`key`、`group` 任意字段的存储或查询逻辑时，必须同步检查 cfg/state/log 三方匹配。
- `ops_cfg.group` 与 `ops_state` 无对应字段；分组信息仅来自 cfg，state-only 无分组。

### 11.3 统计口径的连锁影响

- OS 列表、OS total、OS alarm、仅异常筛选必须使用同一领域集合（已在 Service 层统一）。
- Process 总览与列表口径刻意不一致（总览不含 state-only），修改前必须确认业务口径并补充回归测试。
- 前端 OS 表无分页控件，依赖接口 `total/page_size` 拉全页；分页逻辑变更需同步检查前端多页加载。

### 11.4 状态判定的确定性

- OS/Process 列表必须先全量确定性排序再分页（已实现），跨页加载需检查重复与遗漏。
- Process AM/PM 盘次选择基于本次请求统一时钟，修改时不能引入跨盘次回退。
- 状态优先级（offline → unknown → error → normal）不可调整顺序。

### 11.5 敏感信息

- 进程参数告警保留现有脱敏规则（`SENSITIVE_PROCESS_ARG_NAMES`）。
- `.env.*` 实际文件已在 `.gitignore`，但 `.env.development` 当前存在于工作区（含真实连接信息），不得提交。

## 12. 测试与验证现状

### 12.1 测试文件职责

| 文件 | 职责 | 关键断言 |
|---|---|---|
| `tests/test_ops_service.py` | 核心领域与 DB 查询逻辑 | cfg/state 匹配、状态判定、AM/PM 盘次、state-only、分组、日志分页 |
| `tests/test_monitor_overview_compat.py` | Controller、兼容接口结构、排序、分页 | 路由注册、OpenAPI 一致、UTF-8 响应、字段转换、typo 拒绝（`gropy`） |
| `tests/test_ops_parse.py` | 解析与时间工具 | `parse_dat`、`is_stale`、`is_in_work_time`、跨午夜工作时间 |

测试使用内存 SQLite（`FakeOpsService` 覆盖 `_get_active_cfgs`/`_get_states`/`_get_log_stats`），不依赖真实 MySQL。`pytest.ini` 配置 `testpaths=tests`。

### 12.2 CI 配置

`.github/workflows/ci.yml` 含两个独立 job：

- `backend-tests`：Python 3.11 + `pip install -r requirements.txt` + `python -m pytest -q`，env 设 `ENVIRONMENT=testing`。
- `frontend-build`：Node 22 + `npm ci` + `npm run build`（vue-tsc 类型检查 + Vite 构建）。

> 注意：CI 后端测试不启动 MySQL，依赖测试用内存 SQLite + Fake 对象；`DB_HOST` 等变量仅用于配置加载阶段。

### 12.3 本地验证命令

```powershell
# 后端测试
.\.venv\Scripts\python.exe -m pytest -q

# 前端类型检查与构建
cd frontend
npm run build

# 格式检查（文档/格式变更）
git diff --check
```

> 当前无独立 `npm test` 脚本，不得声称运行了不存在的测试命令。

## 13. 基线量化指标

供后续各 Phase 完成后对比：

| 指标 | 当前值 |
|---|---|
| 已注册监控接口数 | 5 |
| 已注册 router 数 | 2（monitor_overview + test） |
| ORM 数据模型数 | 3（OpsCfg/OpsState/OpsLog）+ 1 遗留（TestModel） |
| 后端 Python 依赖总数 | 20（启用 9，疑似未用 3，预留未用 8） |
| 前端 dependencies | 3（vue/antd/axios） |
| 前端 devDependencies | 4 |
| 前端展示组件数 | 8 |
| 测试文件数 | 3 |
| 环境配置数 | 4（base/dev/prod/testing） |
| 缓存层 | 无 |
| 实时通信通道 | 无 |
| 持久化告警表 | 无 |
| 认证授权 | 无 |
| 容器化配置 | 无 |
| Nginx 部署配置 | 无 |
| 可观测性（指标/结构化日志） | 无 |
| 全局异常处理器 | 无（route 级 try/except） |
| 请求日志中间件 | 无 |

## 14. Phase 路线图映射

将任务书 7 个 Phase 与本基线的债务一一对应，作为后续每阶段的"修改前基线"参照：

| Phase | 目标 | 对应基线债务编号 | 不破坏的约束 |
|---|---|---|---|
| 1 工程基础 | 全局异常/统一响应/请求日志/Docker | 1.1–1.7 | 不改 DB 结构、不引入 K8s/微服务 |
| 2 Redis 缓存 | overview/machine summary 缓存、TTL、Locust 压测 | 2.1–2.3 | 不缓存实时日志、不作 Redis 为 DB、不删 MySQL 查询 |
| 3 DB 查询优化 | SQL 执行计划分析、联合索引 | 3.1–3.4 | 不改 DB 核心结构、不改匹配/状态口径 |
| 4 实时监控 | WebSocket 推送 + polling fallback | 4.1–4.2 | 保留 polling 兜底、不破坏轮询接口契约 |
| 5 告警中心 | alarm/alarm_history 表 + 生命周期 + 前端 | 5.1–5.2 | 不做短信/邮件/微信通知、先闭环 |
| 6 认证权限 | JWT + RBAC（admin/operator/viewer） | 6.1–6.2 | 不设计复杂 SSO |
| 7 部署可观测 | Nginx + API 耗时/错误率/资源监控 | 7.1–7.2 | — |

每个 Phase 完成后需更新本文档对应指标的"Phase 后值"，并执行 `git diff --check` + `pytest -q` + `npm run build` 验证。

---

## 附：基线确认

- 本文档基于 `main` 分支（`02a864a6`）实际生效代码编写。
- 任务书与代码的关键差异已标注：前端 UI 库为 **Ant Design Vue**（非 Element Plus），经确认保持现状。
- `requirements.txt` 中 redis/websockets/python-jose/passlib/PyJWT/bcrypt 均为后续 Phase 预留依赖，当前未启用。
- 上游 MQ 订阅（pika）在 `app/main.py` 中已注释，当前系统仅消费 MySQL 已有数据。







