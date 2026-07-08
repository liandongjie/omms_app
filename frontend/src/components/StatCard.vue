<template>
  <div class="stat-card">
    <div class="stat-card__header">
      <span class="stat-card__title">{{ title }}</span>
      <span :class="['stat-card__signal', signalClass]" />
    </div>
    <div class="stat-card__total">{{ total }}</div>
    <div class="stat-card__meta">
      <span>告警 {{ alarm }}</span>
      <span>异常 {{ error }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  title: string;
  total: number;
  alarm: number;
  error: number;
}>();

const signalClass = computed(() => {
  if (props.error > 0) return 'stat-card__signal--error';
  if (props.alarm > 0) return 'stat-card__signal--warning';
  return 'stat-card__signal--success';
});
</script>
