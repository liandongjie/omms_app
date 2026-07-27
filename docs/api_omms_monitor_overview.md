# API OMMS 监控总览

本文档描述当前由 `app/main.py` 注册的 `/api_omms` 运维监控接口。旧的 `/api/ops/*` 路由当前不对外注册。

## 通用响应

成功响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": {}
}
```

业务处理异常时，路由当前返回：

```json
{
  "code": 500,
  "msg": "error message",
  "errors": null
}
```

## 总览统计

```http
GET /api_omms/monitor/overview/total
```

不需要请求参数。

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "os": {"total": 14, "alarm": 3, "error": 3},
    "process": {"total": 16, "alarm": 2, "error": 2},
    "log": {"total": 120, "alarm": 15, "error": 2}
  }
}
```

统计口径：

- OS `total`：启用的 OS 配置项，加上当天没有匹配启用配置的 state-only OS；OS 列表、总览和异常统计使用同一集合。
- OS `alarm`：状态为 `warning`、`error`、`offline` 或 `unknown` 的可见 OS 数量。
- OS `error`：当前兼容接口直接等于 OS `alarm`。
- Process `total`：启用的进程配置项数量；不包含仅存在于 `ops_state` 的 state-only 进程。
- Process `alarm`：状态为 `warning`、`error`、`offline` 或 `unknown` 的配置进程数量。
- Process `error`：当前兼容接口直接等于 Process `alarm`。
- Log `total`：当天日志行数。
- Log `alarm`：`warn + error` 日志行数。
- Log `error`：`error` 日志行数。

## 分组列表

```http
GET /api_omms/monitor/group/list
```

从启用的 `ops_cfg` 中提取非空分组，去重后按名称升序返回。

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "details": [
      {"group": "algo00x", "display_name": "algo00x"},
      {"group": "op", "display_name": "op"}
    ]
  }
}
```

分组字符串的正式业务含义由业务配置定义，接口不进行中文翻译。

## OS 状态列表

```http
POST /api_omms/monitor/overview/os/list
```

请求体：

```json
{
  "group": "",
  "page_no": 1,
  "page_size": 100,
  "sort_by": "",
  "sort_order": ""
}
```

参数：

- `group`：`null`、空字符串或 `all` 表示全部；其他值按启用的 `ops_cfg.group` 精确过滤。
- `page_no`：最小为 1；缺省时使用 `OPS_DEFAULT_PAGE_NO`。
- `page_size`：最小为 1，最大不超过 `OPS_MAX_PAGE_SIZE`。
- `sort_by`：支持 `machine_tag`、`cpu_usage`、`mem_usage`、`disk_usage`、`update_time`、`is_offline`、`is_alarm`。
- `sort_order`：支持 `asc`、`desc`。

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "page_no": 1,
    "page_size": 100,
    "total": 14,
    "details": [
      {
        "machine_tag": "machine-unconfigured-001",
        "group": null,
        "is_configured": false,
        "cpu_usage": 0.245,
        "mem_usage": 0.133,
        "disk_usage": 0.908,
        "disk_home_usage": null,
        "cpu_alarm": 0,
        "mem_alarm": 0,
        "disk_alarm": 1,
        "disk_home_alarm": 0,
        "update_time": "20260727 10:11:08",
        "is_offline": 0,
        "is_alarm": 1
      }
    ]
  }
}
```

### OS 数据规则

- 配置与 state 按 `(machine_tag, key)` 匹配，不使用 `cfg.value`。
- 同一天同一 `(machine_tag, key)` 有多条 state 时，稳定选择 `update_time` 最新记录。
- `group` 为全部时，补充当天没有匹配启用配置的 state-only OS。
- state-only OS 返回 `group=null`、`is_configured=false`；指定具体分组时不返回 state-only OS。
- `cpu`、`mem`、`disk` 为必需指标；缺失或不可解析时状态为 `unknown`。
- `disk_home` 为可选指标；缺失、不可解析或负数时返回 `null`，不会单独导致 `unknown`。
- 配置 OS 只在 `work_time` 内执行 stale 离线判断；state-only OS 没有 `work_time`，始终依据上报时间是否 stale 判断。
- `is_offline=1` 仅表示内部状态为 `offline`。
- `is_alarm=1` 表示内部状态属于 `warning`、`error`、`offline`、`unknown`。
- Controller 在完整集合上先执行确定性排序，再计算 `total` 和分页。

当前前端 OS 表格不展示分页控件，会根据首个响应的 `total/page_size` 拉取并合并全部页面。

## Process 状态列表

```http
POST /api_omms/monitor/overview/process/list
```

请求体与 OS 列表一致：

```json
{
  "group": "",
  "page_no": 1,
  "page_size": 100,
  "sort_by": "",
  "sort_order": ""
}
```

`sort_by` 支持：

```text
machine_tag
process_name
pid
cpu
mem
update_time
is_offline
is_alarm
```

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "page_no": 1,
    "page_size": 100,
    "total": 1,
    "details": [
      {
        "machine_tag": "lk_cta_2510",
        "group": "algo00x",
        "process_name": "tlBinTradeLite",
        "args": "['sys_simnow.yaml', 'user_simnow_20260727_am.yaml']",
        "pid": 233666,
        "cpu": 0.133,
        "mem": 1778.863,
        "update_time": "20260727 10:11:05",
        "is_configured": true,
        "is_offline": 0,
        "is_alarm": 0,
        "extra": {
          "mds": "10:11:05.0,",
          "algo00x_cfg": "24/4",
          "ord_speed": 16
        }
      }
    ]
  }
}
```

### Process 数据规则

- 配置进程匹配条件：
  - `state.machine_tag == cfg.machine_tag`；
  - `state.type == cfg.type`；
  - `cfg.key` 是 `state.key` 的子串；
  - `cfg.value` 非空时，是 `state.value` 的子串。
- 字符串匹配区分大小写。
- 有 `_am.yaml`、`_pm.yaml` 参数的候选会按当前时段选择 AM 或 PM 盘次，并在目标盘次内选择最新记录；不会用另一盘次兜底。
- 普通候选同样选择 `update_time` 最新记录。
- 匹配到 state 且 `state.value` 非空时，`args` 使用 `state.value`；否则回退到 `cfg.value`。
- 配置进程的 CPU、内存当前只展示，不参与阈值告警。
- 在全部分组的 Process 列表中，Controller 会补充 state-only 进程，返回 `group=null`、`is_configured=false`。
- 指定具体分组时不返回 state-only 进程。
- 当前总览 Process `total` 不包含 state-only 进程，因此可能小于全部分组的 Process 列表总数。

## Log 状态列表

```http
POST /api_omms/monitor/overview/log/list
```

请求体：

```json
{
  "group": "",
  "machine_tag": "",
  "only_error": 0,
  "level": "",
  "date": "",
  "page_no": 1,
  "page_size": 20,
  "sort_by": "",
  "sort_order": ""
}
```

参数：

- `group`：为空时不过滤；有值时先从全部启用配置中取得该组的 `machine_tag` 集合，再过滤日志。该查询当前不限制 `cfg.type`。
- `machine_tag`：精确匹配，首尾空格会被移除。
- `date`：为空时使用服务器当天；有值时按 `ops_log.date` 精确匹配，格式通常为 `YYYYMMDD`。
- `level`：支持空值、`info`、`warn`、`error`，输入会统一转为小写。
- `only_error`：`level` 为空时，值为真只返回 `warn` 和 `error`。
- `level` 与 `only_error` 同时传入时，`level` 优先。
- `sort_by`：支持 `log_id`、`date`、`machine_tag`、`log_name`、`level`、`update_time`。
- `sort_order`：`asc` 为升序，其他值按降序；默认 `log_id desc`。

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "page_no": 1,
    "page_size": 20,
    "total": 2,
    "details": [
      {
        "log_id": 210,
        "date": "20260708",
        "machine_tag": "lk_cta_2510",
        "log_name": "/home/ywang/tp_v2601_s...",
        "level": "info",
        "log": "[20260708 08:50:04.343456][info] ...",
        "update_time": "20260708 08:50:04",
        "is_alarm": 0
      }
    ]
  }
}
```

日志分页在数据库查询中完成，`total` 是应用全部筛选条件后、分页前的日志行数。

`is_alarm` 规则：

- `warn`、`error`：`1`
- `info` 或其他级别：`0`
