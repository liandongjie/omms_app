import axios from 'axios';

export interface ApiResponse<T> {
  code: number;
  msg: string;
  data: T;
}

export interface MonitorListParams {
  group: string;
  page_no: number;
  page_size: number;
  sort_by: string;
  sort_order: string;
}

export interface LogListParams extends MonitorListParams {
  only_error: number;
  level: string;
  date: string;
}

export interface MonitorRow {
  id?: string | number;
  machine_tag?: string;
  machine_id?: string;
  machine?: string;
  host?: string;
  hostname?: string;
  host_name?: string;
  ip?: string;
  name?: string;
  process_name?: string;
  proc_name?: string;
  pid?: string | number;
  cpu?: number;
  cpu_usage?: number;
  mem?: number;
  memory?: number;
  mem_usage?: number;
  disk_usage?: number;
  update_time?: string;
  updated_at?: string;
  collect_time?: string;
  timestamp?: string;
  is_alarm?: number | boolean;
  is_offline?: number | boolean;
  [key: string]: unknown;
}

export interface LogRow {
  log_id?: number;
  date?: string;
  machine_tag?: string;
  log_name?: string;
  level?: string;
  log?: string;
  update_time?: string;
  is_alarm?: number | boolean;
  [key: string]: unknown;
}

export interface MonitorListData<T = MonitorRow> {
  details?: T[];
  list?: T[];
  records?: T[];
  items?: T[];
  rows?: T[];
  data?: T[];
  total?: number;
  [key: string]: unknown;
}

export interface OverviewTotalData {
  [key: string]: unknown;
}

const http = axios.create({
  timeout: 10000,
});

async function requestData<T>(url: string, method: 'GET' | 'POST', data?: unknown): Promise<T> {
  const response = await http.request<ApiResponse<T>>({
    url,
    method,
    data,
  });

  const payload = response.data;
  if (payload.code !== 200) {
    throw new Error(payload.msg || '接口返回异常');
  }

  return payload.data;
}

export function fetchOverviewTotal() {
  return requestData<OverviewTotalData>('/api_omms/monitor/overview/total', 'GET');
}

export function fetchOverviewOsList(params: MonitorListParams) {
  return requestData<MonitorListData<MonitorRow> | MonitorRow[]>(
    '/api_omms/monitor/overview/os/list',
    'POST',
    params,
  );
}

export function fetchOverviewProcessList(params: MonitorListParams) {
  return requestData<MonitorListData<MonitorRow> | MonitorRow[]>(
    '/api_omms/monitor/overview/process/list',
    'POST',
    params,
  );
}

export function fetchOverviewLogList(params: LogListParams) {
  return requestData<MonitorListData<LogRow> | LogRow[]>(
    '/api_omms/monitor/overview/log/list',
    'POST',
    params,
  );
}
