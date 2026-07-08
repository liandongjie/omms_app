<template>
  <a-table
    row-key="id"
    size="middle"
    :columns="columns"
    :data-source="filteredRows"
    :pagination="false"
  >
    <template #emptyText>
      <a-empty description="暂无日志接口，第一版先保留占位" />
    </template>
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'level'">
        <a-tag :bordered="false" :color="record.level === 'ERROR' ? 'red' : 'orange'">
          {{ record.level }}
        </a-tag>
      </template>
    </template>
  </a-table>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { TableColumnsType } from 'ant-design-vue';

interface LogRow {
  id: number;
  time: string;
  group: string;
  source: string;
  message: string;
  level: 'WARN' | 'ERROR';
  is_alarm: number;
}

const props = defineProps<{
  group: string;
}>();

const columns: TableColumnsType = [
  { title: '时间', dataIndex: 'time', key: 'time', width: 180 },
  { title: '分组', dataIndex: 'group', key: 'group', width: 120 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 160 },
  { title: '级别', key: 'level', width: 100 },
  { title: '内容', dataIndex: 'message', key: 'message' },
];

const mockRows: LogRow[] = [];

const filteredRows = computed(() => {
  if (props.group === '__only_error__') {
    return mockRows.filter((row) => row.is_alarm === 1);
  }

  if (!props.group) {
    return mockRows;
  }

  return mockRows.filter((row) => row.group === props.group);
});
</script>
