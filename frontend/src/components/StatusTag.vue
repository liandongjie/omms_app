<template>
  <a-tag :class="['status-tag', status.className]" :bordered="false">
    {{ status.label }}
  </a-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  isAlarm?: number | boolean;
  isOffline?: number | boolean;
}>();

function flag(value: unknown) {
  return value === true || value === 1 || value === '1';
}

const status = computed(() => {
  if (flag(props.isOffline)) {
    return { label: '离线', className: 'status-error' };
  }

  if (flag(props.isAlarm)) {
    return { label: '告警', className: 'status-warning' };
  }

  return { label: '正常', className: 'status-success' };
});
</script>