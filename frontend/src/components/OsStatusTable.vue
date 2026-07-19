<template>
  <a-table
    row-key="__rowKey"
    size="middle"
    :columns="columns"
    :data-source="tableRows"
    :loading="loading"
    :pagination="false"
  >
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'label'">
        <span class="table-primary">{{ formatOsLabel(record) }}</span>
      </template>
      <template v-else-if="column.key === 'cpu_usage'">
        <div v-if="hasMetric(record.cpu_usage ?? record.cpu)" class="os-metric-progress">
          <a-progress
            size="small"
            :percent="metricBarPercent(record.cpu_usage ?? record.cpu)"
            :status="metricStatus(record.cpu_alarm)"
            :format="() => formatPercent(record.cpu_usage ?? record.cpu)"
          />
        </div>
        <span v-else>-</span>
      </template>
      <template v-else-if="column.key === 'mem_usage'">
        <div v-if="hasMetric(record.mem_usage ?? record.memory ?? record.mem)" class="os-metric-progress">
          <a-progress
            size="small"
            :percent="metricBarPercent(record.mem_usage ?? record.memory ?? record.mem)"
            :status="metricStatus(record.mem_alarm)"
            :format="() => formatPercent(record.mem_usage ?? record.memory ?? record.mem)"
          />
        </div>
        <span v-else>-</span>
      </template>
      <template v-else-if="column.key === 'disk_usage'">
        <div class="os-disk-metrics">
          <div class="os-disk-metric">
            <span class="os-disk-label">disk</span>
            <div v-if="hasMetric(record.disk_usage)" class="os-metric-progress">
              <a-progress
                size="small"
                :percent="metricBarPercent(record.disk_usage)"
                :status="metricStatus(record.disk_alarm)"
                :format="() => formatPercent(record.disk_usage)"
              />
            </div>
            <span v-else>-</span>
          </div>
          <div class="os-disk-metric">
            <span class="os-disk-label">disk_home</span>
            <div v-if="hasMetric(record.disk_home_usage)" class="os-metric-progress">
              <a-progress
                size="small"
                :percent="metricBarPercent(record.disk_home_usage)"
                :status="metricStatus(record.disk_home_alarm)"
                :format="() => formatPercent(record.disk_home_usage)"
              />
            </div>
            <span v-else>-</span>
          </div>
        </div>
      </template>
      <template v-else-if="column.key === 'update_time'">
        {{ getUpdateTime(record) }}
      </template>
      <template v-else-if="column.key === 'status'">
        <StatusTag :is-alarm="record.is_alarm" :is-offline="record.is_offline" />
      </template>
    </template>
  </a-table>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { TableColumnsType } from 'ant-design-vue';
import type { MonitorRow } from '../api/omms';
import StatusTag from './StatusTag.vue';

const props = defineProps<{
  rows: MonitorRow[];
  loading?: boolean;
}>();

const columns: TableColumnsType = [
  { title: '标签', key: 'label', width: 220 },
  { title: 'CPU 使用率', key: 'cpu_usage', width: 160 },
  { title: '内存使用率', key: 'mem_usage', width: 160 },
  { title: '磁盘使用率', key: 'disk_usage', width: 240 },
  { title: '更新时间', key: 'update_time', width: 190 },
  { title: '状态', key: 'status', width: 110, align: 'center' },
];

const tableRows = computed(() =>
  props.rows.map((row, index) => ({
    __rowKey: row.id ?? `${row.machine_tag || getMachineName(row)}-${getUpdateTime(row)}-${index}`,
    ...row,
  })),
);

function getMachineName(row: MonitorRow) {
  return (
    row.machine_tag ||
    row.machine_id ||
    row.machine ||
    row.host ||
    row.hostname ||
    row.host_name ||
    row.ip ||
    row.name ||
    '-'
  );
}

function formatOsLabel(row: MonitorRow) {
  const machineTag = String(row.machine_tag ?? '').trim();
  if (!machineTag) return '-';

  const group = String(row.group ?? '').trim();
  return group ? `${group}/${machineTag}` : `未分组/${machineTag}`;
}

function getUpdateTime(row: MonitorRow) {
  return row.update_time || row.updated_at || row.collect_time || row.timestamp || '-';
}

function formatPercent(value: unknown) {
  const percent = metricPercent(value);
  return percent === null ? '-' : `${percent.toFixed(1)}%`;
}

function hasMetric(value: unknown) {
  return metricPercent(value) !== null;
}

function metricBarPercent(value: unknown) {
  const percent = metricPercent(value);
  if (percent === null) return 0;
  return Math.min(percent, 100);
}

function metricStatus(alarm: unknown) {
  return flag(alarm) ? 'exception' : 'normal';
}

function metricPercent(value: unknown) {
  const numberValue = metricValue(value);
  return numberValue === null ? null : numberValue * 100;
}

function metricValue(value: unknown) {
  if (value === null || value === undefined || value === '') return null;
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return null;
  return numberValue;
}

function flag(value: unknown) {
  return value === true || value === 1 || value === '1';
}
</script>

<style scoped>
.os-metric-progress {
  width: 120px;
  max-width: 100%;
}

.os-disk-metrics {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.os-disk-metric {
  display: flex;
  align-items: center;
  gap: 8px;
}

.os-disk-label {
  width: 68px;
  flex: 0 0 68px;
  color: rgba(0, 0, 0, 0.65);
  font-size: 12px;
}
</style>
