<template>
  <div class="recent-log-table">
    <a-alert
      v-if="errorMessage"
      class="recent-log-table__alert"
      type="warning"
      show-icon
      :message="errorMessage"
    />
    <a-table
      :row-key="resolveRowKey"
      size="middle"
      table-layout="fixed"
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      :pagination="false"
    >
      <template #emptyText>
        <a-empty description="暂无日志数据" />
      </template>
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'machine_tag'">
          {{ record.machine_tag || '-' }}
        </template>
        <template v-else-if="column.key === 'level'">
          <a-tag :bordered="false" :color="levelColor(record.level)">
            {{ record.level || '-' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'log_name'">
          <span class="recent-log-table__ellipsis" :title="record.log_name || ''">
            {{ record.log_name || '-' }}
          </span>
        </template>
        <template v-else-if="column.key === 'log'">
          <span class="recent-log-table__content" :title="record.log || ''">
            {{ record.log || '-' }}
          </span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button
            type="link"
            size="small"
            :disabled="!hasLogContent(record)"
            @click="copyLogContent(record)"
          >
            复制内容
          </a-button>
        </template>
        <template v-else-if="column.key === 'index'">
          {{ index + 1 }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { message, type TableColumnsType } from 'ant-design-vue';
import type { LogRow } from '../api/omms';

defineProps<{
  rows: LogRow[];
  loading: boolean;
  errorMessage?: string;
}>();

const columns: TableColumnsType = [
  { title: '机器标识', key: 'machine_tag', width: 150 },
  { title: '级别', key: 'level', width: 90 },
  { title: '日志名称', key: 'log_name', width: 220, ellipsis: true },
  { title: '日志内容', key: 'log', ellipsis: true },
  { title: '操作', key: 'action', width: 110 },
];

function resolveRowKey(record: LogRow, index?: number) {
  if (record.log_id !== undefined) return record.log_id;
  return `${record.machine_tag || 'log'}-${record.update_time || record.date || index || 0}`;
}

function levelColor(level?: string) {
  const normalized = level?.toLowerCase();
  if (normalized === 'error') return 'red';
  if (normalized === 'warn' || normalized === 'warning') return 'orange';
  if (normalized === 'info') return 'blue';
  return 'default';
}


function hasLogContent(record: LogRow) {
  return Boolean(record.log?.trim());
}

async function copyLogContent(record: LogRow) {
  const text = record.log || '';

  if (!text.trim()) {
    message.warning('暂无可复制内容');
    return;
  }

  if (!navigator.clipboard?.writeText) {
    message.error('复制失败，请手动复制');
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    message.success('已复制日志内容');
  } catch {
    message.error('复制失败，请手动复制');
  }
}
</script>

<style scoped>
.recent-log-table {
  min-width: 0;
}

.recent-log-table__alert {
  margin-bottom: 12px;
}

.recent-log-table__ellipsis,
.recent-log-table__content {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-log-table__content {
  font-family: var(--font-code, Consolas, 'Courier New', monospace);
}
</style>
