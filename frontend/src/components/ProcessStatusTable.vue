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
      <template v-else-if="column.key === 'process_name'">
        {{ getProcessName(record) }}
      </template>
      <template v-else-if="column.key === 'config'">
        <a-tag :bordered="false" :color="isConfigured(record) ? 'green' : 'orange'">
          {{ isConfigured(record) ? '已配置' : '未配置' }}
        </a-tag>
      </template>
      <template v-else-if="column.key === 'args'">
        <span class="process-args-cell" :title="getArgsText(record)">{{ getArgsText(record) }}</span>
      </template>
      <template v-else-if="column.key === 'pid'">
        {{ record.pid ?? '-' }}
      </template>
      <template v-else-if="column.key === 'cpu'">
        {{ formatMetric(record.cpu_usage ?? record.cpu) }}
      </template>
      <template v-else-if="column.key === 'mem'">
        {{ formatMetric(record.mem_usage ?? record.memory ?? record.mem) }}
      </template>
      <template v-else-if="column.key === 'update_time'">
        {{ getUpdateTime(record) }}
      </template>
      <template v-else-if="column.key === 'status'">
        <StatusTag :is-alarm="record.is_alarm" :is-offline="record.is_offline" />
      </template>
      <template v-else-if="column.key === 'extra'">
        <a-button v-if="hasExtra(record)" type="link" size="small" @click="openExtraModal(record)">
          查看
        </a-button>
        <span v-else>-</span>
      </template>
    </template>
  </a-table>

  <a-modal
    v-model:open="extraModalOpen"
    title="进程详情"
    :footer="null"
    width="680px"
  >
    <a-descriptions
      v-if="selectedRow"
      bordered
      size="small"
      :column="1"
    >
      <a-descriptions-item label="机器标识">
        {{ getMachineName(selectedRow) }}
      </a-descriptions-item>
      <a-descriptions-item label="进程名">
        {{ getProcessName(selectedRow) }}
      </a-descriptions-item>
      <a-descriptions-item label="args">
        <span class="detail-value">{{ getArgsText(selectedRow) }}</span>
      </a-descriptions-item>
      <a-descriptions-item
        v-for="item in selectedExtraItems"
        :key="item.key"
        :label="item.key"
      >
        <span class="detail-value">{{ item.value }}</span>
      </a-descriptions-item>
    </a-descriptions>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { TableColumnsType } from 'ant-design-vue';
import type { MonitorRow } from '../api/omms';
import StatusTag from './StatusTag.vue';

const props = defineProps<{
  rows: MonitorRow[];
  loading?: boolean;
}>();

const columns: TableColumnsType = [
  { title: '机器标识', key: 'machine', width: 150 },
  { title: '进程名', key: 'process_name', width: 170 },
  { title: '配置', key: 'config', width: 100, align: 'center' },
  { title: 'args', key: 'args', width: 260 },
  { title: 'PID', key: 'pid', width: 100 },
  { title: 'CPU (%)', key: 'cpu', width: 110 },
  { title: '内存 (M)', key: 'mem', width: 110 },
  { title: '更新时间', key: 'update_time', width: 190 },
  { title: '状态', key: 'status', width: 110, align: 'center' },
  { title: '详情', key: 'extra', width: 90, align: 'center' },
];

const extraModalOpen = ref(false);
const selectedRow = ref<MonitorRow | null>(null);

const tableRows = computed(() =>
  props.rows.map((row, index) => ({
    __rowKey: row.id ?? `${row.machine_tag || getMachineName(row)}-${getProcessName(row)}-${row.pid ?? 'pid'}-${index}`,
    ...row,
  })),
);

const selectedExtraItems = computed(() => {
  const extra = selectedRow.value?.extra;
  if (!isPlainRecord(extra)) return [];

  return Object.entries(extra).map(([key, value]) => ({
    key,
    value: formatExtraValue(value),
  }));
});

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

function getProcessName(row: MonitorRow) {
  return row.process_name || row.proc_name || row.name || '-';
}

function getArgsText(row: MonitorRow) {
  if (row.args === null || row.args === undefined || row.args === '') return '-';
  return String(row.args);
}

function isConfigured(row: MonitorRow) {
  return row.is_configured !== false;
}

function getUpdateTime(row: MonitorRow) {
  return row.update_time || row.updated_at || row.collect_time || row.timestamp || '-';
}

function formatMetric(value: unknown) {
  if (value === null || value === undefined || value === '') return '-';
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return String(value);
  return numberValue.toFixed(2);
}

function hasExtra(row: MonitorRow) {
  return isPlainRecord(row.extra) && Object.keys(row.extra).length > 0;
}

function openExtraModal(row: MonitorRow) {
  selectedRow.value = row;
  extraModalOpen.value = true;
}

function formatExtraValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-';
  if (Array.isArray(value) || typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
</script>

<style scoped>
.process-args-cell {
  display: inline-block;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.detail-value {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
