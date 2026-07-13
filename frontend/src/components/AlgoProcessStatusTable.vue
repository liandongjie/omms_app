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
        <span
          class="ellipsis-cell"
          :class="valueClass(formatRoundtrip(record, 'r0'))"
          :title="formatRoundtrip(record, 'r0')"
        >
          {{ formatRoundtrip(record, 'r0') }}
        </span>
      </template>
      <template v-else-if="column.key === 'rt1'">
        <span
          class="ellipsis-cell"
          :class="valueClass(formatRoundtrip(record, 'r1'))"
          :title="formatRoundtrip(record, 'r1')"
        >
          {{ formatRoundtrip(record, 'r1') }}
        </span>
      </template>
    </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { TableColumnsType } from 'ant-design-vue';
import type { MonitorRow } from '../api/omms';

const props = defineProps<{
  rows: MonitorRow[];
  loading?: boolean;
}>();

const columns: TableColumnsType = [
  { title: '标签', key: 'label', width: 170 },
  { title: '进程名', key: 'process_name', width: 140 },
  { title: 'args', key: 'args', width: 280 },
  { title: 'PID', key: 'pid', width: 90 },
  { title: 'CPU (%)', key: 'cpu', width: 80 },
  { title: '内存 (M)', key: 'mem', width: 90 },
  { title: '更新时间', key: 'update_time', width: 150 },
  { title: 'mds', key: 'mds', width: 120 },
  { title: 'algo00x_cfg', key: 'algo00x_cfg', width: 110 },
  { title: 'ord_speed', key: 'ord_speed', width: 90 },
  { title: 'ord_dist', key: 'ord_dist', width: 200 },
  { title: 'rt0', key: 'rt0', width: 240 },
  { title: 'rt1', key: 'rt1', width: 240 },
];

const tableRows = computed(() =>
  props.rows.map((row, index) => ({
    __rowKey: row.id ?? `${row.machine_tag || 'machine'}-${getProcessName(row)}-${row.pid ?? 'pid'}-${index}`,
    ...row,
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
  if (!isPlainRecord(value)) return formatValue(value);
  const entries = Object.entries(value);
  return entries.length ? entries.map(([key, item]) => `${key}:${formatValue(item)}`).join(', ') : '-';
}

function formatRoundtrip(row: MonitorRow, key: 'r0' | 'r1') {
  const roundtrip = getExtra(row, 'roundtrip');
  if (!isPlainRecord(roundtrip) || !isPlainRecord(roundtrip[key])) return '-';

  const metrics = roundtrip[key];
  return ['mean', 'std', 'p50', 'p90'].map((metric) => formatValue(metrics[metric])).join(' / ');
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

.empty-value {
  color: #cbd5e1;
}
</style>
