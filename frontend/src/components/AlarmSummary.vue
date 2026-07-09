<template>
  <div class="alarm-summary">
    <div v-for="item in items" :key="item.label" class="alarm-summary__item">
      <span class="alarm-summary__label">{{ item.label }}</span>
      <strong :class="{ 'alarm-summary__number--active': item.value > 0 }">
        {{ item.value }}
      </strong>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  osAlarm: number;
  processAlarm: number;
  logAlarm: number;
}>();

const items = computed(() => [
  { label: '总告警数', value: props.osAlarm + props.processAlarm + props.logAlarm },
  { label: 'OS 告警数', value: props.osAlarm },
  { label: 'Process 告警数', value: props.processAlarm },
  { label: 'Log 告警数', value: props.logAlarm },
]);
</script>
