# AGENTS.md

本文件适用于仓库根目录及所有子目录，用于约束在 OMMS 仓库中工作的代码代理。

## 1. 事实来源与优先级

当前实现以最新 `main` 中实际生效的内容为准。出现冲突时，按以下优先级判断：

1. 当前被注册、引用和执行的代码；
2. 当前测试及断言；
3. `requirements.txt`、`package.json`、锁文件、环境配置和构建脚本；
4. 前后端真实调用链；
5. 已合并的近期 Git 变更；
6. `README.md` 和 `docs/` 中的文档。

README 和历史文档只能作为线索。不得因为文件存在，就认定它当前已经注册、被调用或属于正式链路。发现文档与代码冲突时，以代码和测试为准，并在任务总结中指出。

## 2. 项目概览

OMMS 是内部运维监控系统，当前页面包含：

- 监控总览；
- OS 状态；
- 进程状态；
- 最近日志；
- 分组与异常筛选。

后端技术栈：Python、FastAPI、SQLAlchemy、Pydantic、MySQL、PyMySQL。

前端技术栈：Vue 3、TypeScript、Vite、Ant Design Vue、Axios。

当前系统以数据正确性、业务口径一致性和可维护性为优先目标。不要擅自引入面向大规模并发的架构改造。

## 3. 重要目录和调用链

### 后端

```text
app/main.py
→ app/routes/
→ app/controllers/
→ app/services/
→ app/models/ + MySQL
```

- `app/main.py`：FastAPI 应用及正式路由注册。
- `app/routes/monitor_overview_route.py`：`/api_omms` 监控接口入口。
- `app/controllers/monitor_overview_controller.py`：请求归一化、领域对象到接口对象转换、OS/进程排序与内存分页。
- `app/services/ops_service.py`：配置/state 匹配、状态判定、日志查询、总览和分组等核心业务逻辑。
- `app/schemas/monitor_overview_schema.py`：对外监控接口请求和响应结构。
- `app/schemas/ops_schema.py`：Service 层领域对象。
- `app/models/ops_model.py`：`ops_cfg`、`ops_state`、`ops_log` ORM 映射。
- `app/utils/ops_parse.py`：`dat`、指标、时间、工作时间和进程参数解析。
- `app/config/`：环境配置、阈值和分页上限。
- `app/utils/db.py`：MySQL Engine 和 Session。

当前 `app/main.py` 正式注册：

```text
GET  /api_omms/monitor/overview/total
GET  /api_omms/monitor/group/list
POST /api_omms/monitor/overview/os/list
POST /api_omms/monitor/overview/process/list
POST /api_omms/monitor/overview/log/list
```

不要仅凭旧路由文件存在，就认定 `/api/ops/*` 已对外生效。

### 前端

```text
frontend/src/api/omms.ts
→ frontend/src/views/OmmsDashboard.vue
→ frontend/src/components/*.vue
```

- `frontend/src/api/omms.ts`：接口类型和请求封装。
- `frontend/src/views/OmmsDashboard.vue`：页面状态、刷新、筛选、OS 多页加载和统计兜底。
- `frontend/src/components/OsStatusTable.vue`：OS 表格。
- `frontend/src/components/ProcessStatusTable.vue`：普通进程表格。
- `frontend/src/components/AlgoProcessStatusTable.vue`：algo00x 扩展进程表格。
- `frontend/src/components/RecentLogTable.vue`：日志表格及分页。
- `frontend/vite.config.ts`：开发服务器监听 `0.0.0.0:5173`，代理 `/api_omms` 到 `127.0.0.1:8004`。

### 测试

- `tests/test_ops_service.py`：核心领域和数据库查询逻辑。
- `tests/test_monitor_overview_compat.py`：Controller、兼容接口结构、排序和分页。
- `tests/test_ops_parse.py`：解析和时间工具。

## 4. 本地命令

### 后端安装

在仓库根目录：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.development.example .env.development
```

填写实际 MySQL 连接信息，不得提交真实凭据。

### 后端启动

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

开发时可以增加 `--reload`。

### 后端测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### 前端安装和启动

```powershell
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

### 前端验证

```powershell
cd frontend
npm run build
```

`npm run build` 同时执行 `vue-tsc --noEmit` 和 Vite 生产构建。当前没有独立 `npm test` 脚本，不得声称运行了不存在的测试命令。

## 5. 数据表角色

### `ops_cfg`

启用的监控配置，主要包括：

- `type`；
- `machine_tag`；
- `group`；
- `key`；
- `value`；
- `work_time`；
- `status`。

物理表没有数据库主键。ORM 使用 `type + machine_tag + group + key + value` 作为逻辑复合主键。修改相关逻辑时要考虑重复配置和 ORM identity 合并风险。

### `ops_state`

保存按日期、类型、机器、key、value 区分的最新状态。页面上的 `normal`、`offline`、`unknown`、`error` 不是直接读取的数据库最终状态，而是 Service 动态计算。

### `ops_log`

追加式日志记录。日志按“行”统计，不按独立故障事件去重。

数据库没有显式外键。跨表关联依赖字符串一致性，修改时不得忽略大小写、空格和命名差异。

## 6. OS 业务规则

### 6.1 可见集合

全部分组的 OS 集合为：

```text
启用的 OS 配置项
+
当天未匹配启用配置的 state-only OS
```

- 配置与 state 使用 `(machine_tag, key)` 匹配。
- OS 匹配不使用 `cfg.value`。
- 同一 `(machine_tag, key)` 有多条 state 时，稳定选择 `update_time` 最新记录。
- 已被配置消费的 state 不得再次以 state-only 展示。
- state-only OS 返回 `group=None`、`is_configured=False`。
- 指定具体 group 时，不展示无分组的 state-only OS。

### 6.2 状态规则

配置 OS：

- 没有 state：工作时间内 `offline`，工作时间外 `normal`；
- 工作时间内 state 超过离线阈值：`offline`；
- `dat` 非空但无法解析：`unknown`；
- `cpu`、`mem`、`disk` 缺失或无效：`unknown`；
- 资源指标达到阈值：`error`；
- 其他情况：`normal`。

state-only OS 没有 `work_time`，始终检查 state 是否 stale。这里的 `offline` 只表示上报数据不新鲜，不代表系统确认该机器在业务上本应运行。

`disk_home` 是可选指标：

- 缺失、无效或负数时按空值处理；
- 不会仅因为 `disk_home` 缺失而判为 `unknown`；
- 有效值达到磁盘阈值时判为 `error`。

状态优先级必须保持：

```text
stale/offline
→ parse/missing/unknown
→ resource threshold/error
→ normal
```

### 6.3 总览、筛选和分页

- OS 列表、OS total、OS alarm 和仅异常筛选必须使用同一领域集合。
- OS total 表示可见 OS 数量，不再仅表示配置数量。
- Controller 必须在完整集合上稳定排序后再分页。
- 前端 OS 表没有分页控件，必须根据接口 `total/page_size` 拉取全部页。
- 后续页失败或返回数量不足时，不得用不完整结果覆盖现有列表。

## 7. Process 业务规则

### 7.1 cfg/state 匹配

候选必须同时满足：

```text
state.machine_tag == cfg.machine_tag
state.type == cfg.type
cfg.key in state.key
cfg.value 为空，或 cfg.value in state.value
```

匹配区分大小写。不要擅自改成模糊、不区分大小写或结构化匹配。

### 7.2 盘次和候选选择

- 从 `state.value` 参数中识别 `_am.yaml` 和 `_pm.yaml`。
- 08:00（含）至 18:00（不含）选择 AM，其他时间选择 PM。
- 存在盘次候选时，只从目标盘次选择最新 state。
- 目标盘次缺失时，不得回退到另一盘次或 generic 候选。
- 没有盘次候选时，从 generic 候选中稳定选择最新 state。
- 所有属于配置的候选都要标记为已消费，避免未选中的历史/其他盘次被错误补成 state-only。

修改这部分前必须阅读相关告警日志、敏感参数脱敏和测试。

### 7.3 args 和状态

配置进程的 args 优先级：

```text
有效 state.value
→ cfg.value
→ None
```

- state 超时但 `state.value` 有效时，仍显示最后一次真实上报参数。
- `cfg.value` 只作为缺少有效上报参数时的原样兜底，不得推测完整启动参数。
- state-only 进程只使用 `state.value`。

配置进程当前只根据 state 是否存在、是否 stale 和 `dat` 是否可解析计算状态；CPU、内存只展示，不参与阈值告警。

### 7.4 state-only 和统计口径

- 全部分组的 Process 列表包含未被配置消费的 state-only 进程。
- state-only 返回 `group=None`、`is_configured=False`，没有配置工作时间。
- 指定具体 group 时不包含 state-only。
- 当前 Process 总览不包含 state-only，可能与全部 Process 列表行数不同。这是当前实现，修改前必须明确业务口径并补充回归测试。
- 前端 Process 列表当前固定请求前 100 条；扩容时存在静默截断风险，不得在无评估情况下假设其为全量。

## 8. Log 业务规则

- `date` 为空时查询服务器当天。
- `machine_tag` 精确过滤。
- `level` 支持 `info`、`warn`、`error`，大小写归一为小写。
- 显式 `level` 优先于 `only_error`。
- `only_error` 在未指定 level 时查询 `warn` 和 `error`。
- 日志 `alarm = warn + error`，`error = error`。
- 日志在数据库中完成过滤、排序和分页；`total` 在分页前计算。
- 默认按 `log_id desc` 排序。

`ops_log` 没有 group。按组筛选时，从所有启用 `ops_cfg` 记录中取得该 group 的 `machine_tag`；当前没有限制 `cfg.type`。同一机器属于多个组时，日志分组可能存在歧义，修改前先确认业务规则。

## 9. Group 规则

分组来自启用的 `ops_cfg.group`：

- 去除首尾空格；
- 排除空值；
- 排除界面保留名称“全部”“仅异常”；
- 去重并升序返回；
- `display_name` 当前等于原始 group。

`op`、`algo00x` 等字符串的正式业务定义不在代码中。未得到业务确认时，不得在代码或文档中自行扩写为确定含义。

## 10. 修改边界

- 开始前先沿 Route → Controller → Service → Model/数据库和前端调用链阅读。
- 做最小范围修改，不顺手重构无关模块。
- 不擅自修改接口字段、状态口径、阈值、数据库结构或生产数据。
- 不自动向 `ops_cfg` 插入 state-only 数据。
- 修改共享方法前，检查 OS、Process、Overview、Alarm 和前端统计的连锁影响。
- 后端列表、总览和前端展示的统计口径必须明确且一致；已有刻意不一致必须被记录。
- 分页前必须使用确定性排序；跨页加载必须检查重复和遗漏。
- 不新增依赖，除非任务明确要求且说明理由。
- 不进行全文件无关格式化或变量批量重命名。
- 不覆盖用户已有的未提交修改。

## 11. 注释要求

- 对新增或修改的关键业务逻辑添加简洁中文注释。
- 注释重点解释原因、数据优先级、去重键、状态口径和兼容边界。
- 不逐行翻译语法，不给简单赋值和明显循环添加废话注释。
- 已有清晰注释不要重复。
- 无法从代码证明的业务含义不得写成事实。

## 12. 测试与验收

按修改范围执行最相关测试，并尽量执行完整验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

文档或格式变更至少执行：

```powershell
git diff --check
```

完成任务后必须如实报告：

- 修改文件；
- 核心行为变化；
- 新增或修改的关键注释；
- 执行的测试和结果；
- 未执行的验证及原因；
- `git diff --stat`；
- `git status`。

不得把环境错误或未执行测试描述为测试通过。

## 13. Git 工作流

- 开始前执行 `git status` 和 `git branch --show-current`。
- 从最新 `main` 创建语义清晰的任务分支。
- 未经明确要求，不得 commit、push、merge 或删除分支。
- 不使用强制推送。
- 一个分支只处理一个清晰主题。
- 文档更新和业务代码修改应尽量拆成独立 PR。

## 14. 安全与隐私

- 不提交 `.env.*` 实际文件、密码、令牌、DSN、数据库连接串或内部敏感地址。
- 记录进程参数警告时保留现有脱敏规则。
- 不在测试、README、AGENTS 或 PR 中粘贴生产凭据和大段真实日志。
- 示例数据应使用脱敏值或仓库已有的非敏感测试数据。
