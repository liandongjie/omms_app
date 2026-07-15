<template>
  <div class="algo-process-table">
    <a-table
      row-key="__rowKey"
      size="small"
      :columns="columns"
      :data-source="tableRows"
      :loading="loading"
      :pagination="{ pageSize: 10, showSizeChanger: false, hideOnSinglePage: true }"
      :scroll="{ x: 'max-content' }"
    >
      <template #headerCell="{ column }">
        <span v-if="column.key === 'rt0'" title="rt0 (mean/std/p50/p90)">rt0</span>
        <span v-else-if="column.key === 'rt1'" title="rt1 (mean/std/p50/p90)">rt1</span>
      </template>
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'label'">
        <span class="table-primary" :title="formatProcessLabel(record)">
          {{ formatProcessLabel(record) }}
        </span>
      </template>
      <template v-else-if="column.key === 'process_name'">
        {{ getProcessName(record) }}
      </template>
      <template v-else-if="column.key === 'config'">
        <a-tag :bordered="false" :color="isConfigured(record) ? 'green' : 'orange'">
          {{ isConfigured(record) ? '已配置' : '未配置' }}
        </a-tag>
      </template>
      <template v-else-if="column.key === 'args'">
        <span class="ellipsis-cell" :title="formatValue(record.args)">{{ formatValue(record.args) }}</span>
      </template>
      <template v-else-if="column.key === 'pid'">
        <span :class="valueClass(formatValue(record.pid))">{{ formatValue(record.pid) }}</span>
      </template>
      <template v-else-if="column.key === 'cpu'">
        <span :class="valueClass(formatValue(record.cpu_usage ?? record.cpu))">
          {{ formatValue(record.cpu_usage ?? record.cpu) }}
        </span>
      </template>
      <template v-else-if="column.key === 'mem'">
        <span :class="valueClass(formatValue(record.mem_usage ?? record.memory ?? record.mem))">
          {{ formatValue(record.mem_usage ?? record.memory ?? record.mem) }}
        </span>
      </template>
      <template v-else-if="column.key === 'update_time'">
        {{ getUpdateTime(record) }}
      </template>
      <template v-else-if="column.key === 'status'">
        <a-tag v-if="isNoReportRow(record)" :bordered="false">暂无上报数据</a-tag>
        <StatusTag v-else :is-alarm="record.is_alarm" :is-offline="record.is_offline" />
      </template>
      <template v-else-if="column.key === 'mds'">
        <span :class="valueClass(formatValue(getExtra(record, 'mds')))">
          {{ formatValue(getExtra(record, 'mds')) }}
        </span>
      </template>
      <template v-else-if="column.key === 'algo00x_cfg'">
        <span :class="valueClass(formatValue(getExtra(record, 'algo00x_cfg')))">
          {{ formatValue(getExtra(record, 'algo00x_cfg')) }}
        </span>
      </template>
      <template v-else-if="column.key === 'ord_speed'">
        <span :class="valueClass(formatValue(getExtra(record, 'ord_speed')))">
          {{ formatValue(getExtra(record, 'ord_speed')) }}
        </span>
      </template>
      <template v-else-if="column.key === 'ord_dist'">
        <span
          class="ellipsis-cell"
          :class="valueClass(formatOrdDist(getExtra(record, 'ord_dist')))"
          :title="formatOrdDist(getExtra(record, 'ord_dist'))"
        >
          {{ formatOrdDist(getExtra(record, 'ord_dist')) }}
        </span>
      </template>
      <template v-else-if="column.key === 'rt0'">
        <span v-if="record.__rt0.isEmpty" class="empty-value">-</span>
        <div v-else class="rt-metric-cell" :title="record.__rt0.title">
          <div class="rt-metric-row">
            <span>mean: <span :class="valueClass(record.__rt0.mean)">{{ record.__rt0.mean }}</span></span>
            <span>std: <span :class="valueClass(record.__rt0.std)">{{ record.__rt0.std }}</span></span>
          </div>
          <div class="rt-metric-row">
            <span>p50: <span :class="valueClass(record.__rt0.p50)">{{ record.__rt0.p50 }}</span></span>
            <span>p90: <span :class="valueClass(record.__rt0.p90)">{{ record.__rt0.p90 }}</span></span>
          </div>
        </div>
      </template>
      <template v-else-if="column.key === 'rt1'">
        <span v-if="record.__rt1.isEmpty" class="empty-value">-</span>
        <div v-else class="rt-metric-cell" :title="record.__rt1.title">
          <div class="rt-metric-row">
            <span>mean: <span :class="valueClass(record.__rt1.mean)">{{ record.__rt1.mean }}</span></span>
            <span>std: <span :class="valueClass(record.__rt1.std)">{{ record.__rt1.std }}</span></span>
          </div>
          <div class="rt-metric-row">
            <span>p50: <span :class="valueClass(record.__rt1.p50)">{{ record.__rt1.p50 }}</span></span>
            <span>p90: <span :class="valueClass(record.__rt1.p90)">{{ record.__rt1.p90 }}</span></span>
          </div>
        </div>
      </template>
      <template v-else-if="column.key === 'action'">
        <a-space :size="0">
          <a-button type="link" size="small" @click="showUnavailable('重启')">重启</a-button>
          <a-button type="link" size="small" danger @click="showUnavailable('停止')">停止</a-button>
        </a-space>
      </template>
    </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { message, type TableColumnsType } from 'ant-design-vue';
import type { MonitorRow } from '../api/omms';
import StatusTag from './StatusTag.vue';

const props = defineProps<{
  rows: MonitorRow[];
  loading?: boolean;
}>();

const columns: TableColumnsType = [
  { title: '标签', key: 'label', width: 170 },
  { title: '进程名', key: 'process_name', width: 140 },
  { title: '配置', key: 'config', width: 100, align: 'center' },
  { title: 'args', key: 'args', width: 280 },
  { title: 'PID', key: 'pid', width: 90 },
  { title: 'CPU (%)', key: 'cpu', width: 80 },
  { title: '内存 (M)', key: 'mem', width: 90 },
  { title: '更新时间', key: 'update_time', width: 150 },
  { title: '状态', key: 'status', width: 110, align: 'center' },
  { title: 'mds', key: 'mds', width: 120 },
  { title: 'algo00x_cfg', key: 'algo00x_cfg', width: 110 },
  { title: 'ord_speed', key: 'ord_speed', width: 90 },
  { title: 'ord_dist', key: 'ord_dist', width: 200 },
  { title: 'rt0', key: 'rt0', width: 240 },
  { title: 'rt1', key: 'rt1', width: 240 },
  { title: '操作', key: 'action', width: 120, align: 'center' },
];

const tableRows = computed(() =>
  props.rows.map((row, index) => ({
    __rowKey: row.id ?? `${row.machine_tag || 'machine'}-${getProcessName(row)}-${row.pid ?? 'pid'}-${index}`,
    ...row,
    __rt0: formatRoundtrip(row, 'r0'),
    __rt1: formatRoundtrip(row, 'r1'),
  })),
);

function formatProcessLabel(row: MonitorRow) {
  const machineTag = String(row.machine_tag ?? '').trim();
  if (!machineTag) return '-';

  const group = String(row.group ?? '').trim();
  return group ? `${group}/${machineTag}` : `未分组/${machineTag}`;
}

function getProcessName(row: MonitorRow) {
  return row.process_name || row.proc_name || row.name || '-';
}

function isConfigured(row: MonitorRow) {
  return row.is_configured !== false;
}

function hasValue(value: unknown) {
  return value !== null && value !== undefined && String(value).trim() !== '';
}

function isNoReportRow(row: MonitorRow) {
  return (
    isConfigured(row) &&
    !hasValue(row.pid) &&
    !hasValue(row.cpu) &&
    !hasValue(row.mem) &&
    !hasValue(row.memory) &&
    !hasValue(row.mem_usage) &&
    !hasValue(row.update_time) &&
    Number(row.is_alarm) !== 1 &&
    Number(row.is_offline) !== 1
  );
}

function getUpdateTime(row: MonitorRow) {
  return row.update_time || row.updated_at || row.collect_time || row.timestamp || '-';
}

function getExtra(row: MonitorRow, key: string) {
  return isPlainRecord(row.extra) ? row.extra[key] : undefined;
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return String(value);
    return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
  }
  if (typeof value === 'string') return value.trim() || '-';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function formatOrdDist(value: unknown) {
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => formatValue(item)).join('-') : '-';
  }
  if (!isPlainRecord(value)) return formatValue(value);

  const entries = Object.entries(value).sort(([left], [right]) => left.localeCompare(right));
  return entries.length ? entries.map(([, item]) => formatValue(item)).join('-') : '-';
}

function formatRoundtrip(row: MonitorRow, key: 'r0' | 'r1') {
  const roundtrip = getExtra(row, 'roundtrip');
  const metrics: Record<string, unknown> =
    isPlainRecord(roundtrip) && isPlainRecord(roundtrip[key]) ? roundtrip[key] : {};
  const mean = formatRoundtripMetric(metrics.mean);
  const std = formatRoundtripMetric(metrics.std);
  const p50 = formatRoundtripMetric(metrics.p50);
  const p90 = formatRoundtripMetric(metrics.p90);

  return {
    mean,
    std,
    p50,
    p90,
    isEmpty: [mean, std, p50, p90].every((value) => value === '-'),
    title: `mean: ${mean}, std: ${std}, p50: ${p50}, p90: ${p90}`,
  };
}

function formatRoundtripMetric(value: unknown) {
  if (typeof value !== 'number' && typeof value !== 'string') return '-';
  if (typeof value === 'string' && !value.trim()) return '-';

  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? (numberValue / 1000).toFixed(1) : '-';
}

function showUnavailable(action: '重启' | '停止') {
  message.info(`${action}功能暂未接入`);
}

function valueClass(value: string | undefined) {
  return value === '-' ? 'empty-value' : undefined;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
</script>

<style scoped>
.algo-process-table {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
}

.ellipsis-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.rt-metric-cell {
  display: inline-flex;
  flex-direction: column;
  line-height: 1.25;
  vertical-align: middle;
  white-space: nowrap;
}

.rt-metric-row {
  display: flex;
  gap: 12px;
}

.empty-value {
  color: #cbd5e1;
}
</style>
