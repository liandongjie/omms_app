# API OMMS 监控概览

本文档描述了用于前端集成的首批概览页 API。

## 基础 URL

本地开发环境：

```text
http://127.0.0.1:8004
```

后端代码提交并由导师部署后，请使用已部署的测试环境基础 URL。

## 通用查询参数

| 名称       | 类型   | 是否必填 | 说明                                                         |
| ---------- | ------ | -------- | ------------------------------------------------------------ |
| group      | string | 否       | 使用真实的 `ops_cfg.group` 值。省略该参数或传入 `all` 表示查询所有分组。示例：`algo00x`、`op`。 |
| only_error | int    | 否       | `1` 表示只查询异常数据；`0` 或省略表示查询全部数据。         |

重要说明：不要使用 `stock`、`cta`、`fut`、`backup` 等示例枚举值，除非它们确实存在于 `ops_cfg.group` 中。

## 概览总数

```http
GET /api_omms/monitor/overview/total
```

示例：

```powershell
Invoke-RestMethod "http://127.0.0.1:8004/api_omms/monitor/overview/total" |
  ConvertTo-Json -Depth 10
```

带筛选条件：

```powershell
Invoke-RestMethod "http://127.0.0.1:8004/api_omms/monitor/overview/total?group=op&only_error=1" |
  ConvertTo-Json -Depth 10
```

curl：

```bash
curl "http://127.0.0.1:8004/api_omms/monitor/overview/total?group=op&only_error=1"
```

响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "os": {
      "total": 10,
      "alarm": 2
    },
    "process": {
      "total": 30,
      "alarm": 5
    },
    "log": {
      "total": 120,
      "alarm": 15
    }
  }
}
```

## OS 概览列表

```http
GET /api_omms/monitor/overview/os/list
```

示例：

```powershell
Invoke-RestMethod "http://127.0.0.1:8004/api_omms/monitor/overview/os/list" |
  ConvertTo-Json -Depth 10
```

带筛选条件：

```powershell
Invoke-RestMethod "http://127.0.0.1:8004/api_omms/monitor/overview/os/list?group=op&only_error=1" |
  ConvertTo-Json -Depth 10
```

curl：

```bash
curl "http://127.0.0.1:8004/api_omms/monitor/overview/os/list?group=op&only_error=1"
```

响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": [
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
```

## 空数据检查清单

如果接口返回为空，请检查：

- API 默认读取当天的数据。
- `ops_cfg.status` 必须为 `1`。
- `group` 查询参数的值必须真实存在于 `ops_cfg.group` 中。
- 本地 `.env.development` 数据库配置必须指向 `lk_td_option`。

## 协作流程

后端开发和本地测试先完成，然后将代码提交到 Git。导师会将后端部署到测试环境，前端集成时应使用已部署的测试环境地址。