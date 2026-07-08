<template>
  <a-table
    row-key="__rowKey"
    size="middle"
    :columns="columns"
    :data-source="tableRows"
    :loading="loading"
    :pagination="{ pageSize: 10, showSizeChanger: false }"
  >
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'machine'">
        <span class="table-primary">{{ getMachineName(record) }}</span>
      </template>
      <template v-else-if="column.key === 'cpu_usage'">
        {{ formatPercent(record.cpu_usage ?? record.cpu) }}
      </template>
      <template v-else-if="column.key === 'mem_usage'">
        {{ formatPercent(record.mem_usage ?? record.memory ?? record.mem) }}
      </template>
      <template v-else-if="column.key === 'disk_usage'">
        {{ formatPercent(record.disk_usage) }}
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
  { title: '机器标识', key: 'machine', width: 180 },
  { title: 'CPU 使用率', key: 'cpu_usage', width: 130 },
  { title: '内存使用率', key: 'mem_usage', width: 130 },
  { title: '磁盘使用率', key: 'disk_usage', width: 130 },
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

function getUpdateTime(row: MonitorRow) {
  return row.update_time || row.updated_at || row.collect_time || row.timestamp || '-';
}

function formatPercent(value: unknown) {
  if (value === null || value === undefined || value === '') return '-';
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return '-';
  return `${(numberValue * 100).toFixed(1)}%`;
}
</script>
