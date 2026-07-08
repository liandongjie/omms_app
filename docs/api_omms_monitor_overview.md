# API OMMS 监控总览

本文档描述当前对外暴露的 `/api_omms` 运维监控总览接口。旧的 `/api/ops/*` 路由不再对外注册。

## 总览统计

```http
GET /api_omms/monitor/overview/total
```

该接口不需要请求参数。

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "os": {"total": 10, "alarm": 2, "error": 2},
    "process": {"total": 30, "alarm": 5, "error": 5},
    "log": {"total": 120, "alarm": 15, "error": 2}
  }
}
```

## OS 总览列表

```http
POST /api_omms/monitor/overview/os/list
```

请求体：

```json
{
  "group": "",
  "page_no": 1,
  "page_size": 10,
  "sort_by": "",
  "sort_order": ""
}
```

字段说明：

- `group`：空字符串、`null`、`all` 表示不过滤；其他值按数据库 `ops_cfg.group` 过滤。
- `page_no`：最小为 1；缺省时读取 `OPS_DEFAULT_PAGE_NO`。
- `page_size`：最小为 1；缺省时读取 `OPS_DEFAULT_PAGE_SIZE`；最大不超过 `OPS_MAX_PAGE_SIZE`。
- `sort_by`：允许 `machine_tag`、`cpu_usage`、`mem_usage`、`disk_usage`、`update_time`、`is_offline`、`is_alarm`，为空时使用默认排序。
- `sort_order`：允许 `asc`、`desc`，为空时指定排序字段默认升序。

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "page_no": 1,
    "page_size": 10,
    "total": 100,
    "details": [
      {
        "machine_tag": "machine-001",
        "cpu_usage": 65,
        "mem_usage": 86,
        "disk_usage": 72,
        "update_time": "2026-07-02 16:20:30",
        "is_offline": 0,
        "is_alarm": 0
      }
    ]
  }
}
```

注意：只支持正确拼写 `group` 和 `details`；不兼容 `gropy` 或 `deatils`。

## Process 总览列表

```http
POST /api_omms/monitor/overview/process/list
```

请求体与 OS 总览列表一致：

```json
{
  "group": "",
  "page_no": 1,
  "page_size": 10,
  "sort_by": "",
  "sort_order": ""
}
```

`group` 为空、`null` 或 `all` 表示不过滤；有值时按数据库 `ops_cfg.group` 过滤。`sort_by` 允许 `machine_tag`、`process_name`、`pid`、`cpu`、`mem`、`update_time`、`is_offline`、`is_alarm`，为空时默认按告警、离线、机器、进程名排序。

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "page_no": 1,
    "page_size": 10,
    "total": 1,
    "details": [
      {
        "machine_tag": "lk_cta_2510",
        "process_name": "tlBinTradeLite",
        "pid": 141976,
        "cpu": 0.116,
        "mem": 2097.57,
        "update_time": "20260706 23:59:54",
        "is_offline": 0,
        "is_alarm": 0
      }
    ]
  }
}
```

Process 列表以启用的 `ops_cfg.type = 'process'` 配置为基准，匹配 `ops_state` 时使用 `machine_tag + type + key + value`，其中 key/value 按包含关系匹配。`cpu` 和 `mem` 展示数据库 `dat` 中的原始值，不乘以 100，不做单位换算。

## Log 总览列表

```http
POST /api_omms/monitor/overview/log/list
```

请求体：

```json
{
  "group": "",
  "only_error": 0,
  "level": "",
  "date": "",
  "page_no": 1,
  "page_size": 20,
  "sort_by": "",
  "sort_order": ""
}
```

`group` 为空、`null` 或 `all` 表示不过滤；有值时先通过 `ops_cfg.group` 查询启用配置的 `machine_tag` 集合，再过滤 `ops_log.machine_tag`。`date` 为空时默认查询当天，传值时按 `ops_log.date` 字符串匹配。`level` 支持 `info`、`warn`、`error`，大小写输入会统一按小写处理；`level` 有值时优先精确过滤，`level` 为空且 `only_error=1` 时只返回 `warn` 和 `error`。默认按 `log_id desc` 排序。

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
        "log": "[20260708 08:50:04.343456][info] [tlBinTradeLite] START...",
        "update_time": "20260708 08:50:04",
        "is_alarm": 0
      }
    ]
  }
}
```

`is_alarm` 规则：`warn` 和 `error` 返回 1，`info` 返回 0。
