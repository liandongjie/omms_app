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

/**
 * 按兼容字段优先级读取机器标识。
 *
 * @param row OS 监控行。
 * @returns 第一个有效机器标识或占位符。
 */
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

/**
 * 组合分组与机器标签作为 OS 行标题。
 *
 * @param row OS 监控行。
 * @returns ``分组/机器`` 标签；缺少分组时使用“未分组”。
 */
function formatOsLabel(row: MonitorRow) {
  const machineTag = String(row.machine_tag ?? '').trim();
  if (!machineTag) return '-';

  const group = String(row.group ?? '').trim();
  return group ? `${group}/${machineTag}` : `未分组/${machineTag}`;
}

/**
 * 按兼容字段优先级读取更新时间。
 *
 * @param row OS 监控行。
 * @returns 第一个有效时间或占位符。
 */
function getUpdateTime(row: MonitorRow) {
  return row.update_time || row.updated_at || row.collect_time || row.timestamp || '-';
}

/**
 * 把比例指标格式化为一位小数的百分比文本。
 *
 * @param value 原始比例值。
 * @returns 百分比文本或占位符。
 */
function formatPercent(value: unknown) {
  const percent = metricPercent(value);
  return percent === null ? '-' : `${percent.toFixed(1)}%`;
}

/**
 * 判断指标是否能转换为有效数值。
 *
 * @param value 原始指标值。
 * @returns 可转换时返回 true。
 */
function hasMetric(value: unknown) {
  return metricPercent(value) !== null;
}

/**
 * 计算进度条使用的百分比并限制最大宽度。
 *
 * @param value 原始比例值。
 * @returns 0 到 100 范围内的进度条百分比。
 */
function metricBarPercent(value: unknown) {
  const percent = metricPercent(value);
  if (percent === null) return 0;
  // 仅限制进度条的视觉宽度，旁边的文本仍保留实际换算值。
  return Math.min(percent, 100);
}

/**
 * 根据指标告警标记选择进度条状态。
 *
 * @param alarm 原始告警标记。
 * @returns 告警时返回 exception，否则返回 normal。
 */
function metricStatus(alarm: unknown) {
  return flag(alarm) ? 'exception' : 'normal';
}

/**
 * 把接口比例值换算为百分数。
 *
 * @param value 原始比例值。
 * @returns 百分数；无法转换时返回 null。
 */
function metricPercent(value: unknown) {
  // 接口中的资源使用率是比例值，组件统一换算为百分数再展示。
  const numberValue = metricValue(value);
  return numberValue === null ? null : numberValue * 100;
}

/**
 * 把未知类型指标转换为有限数值。
 *
 * @param value 原始指标值。
 * @returns 有限数值；空值或非法数值返回 null。
 */
function metricValue(value: unknown) {
  if (value === null || value === undefined || value === '') return null;
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return null;
  return numberValue;
}

/**
 * 兼容布尔值、数字和字符串形式的真值标记。
 *
 * @param value 原始标记值。
 * @returns 值表示 true 或 1 时返回 true。
 */
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
