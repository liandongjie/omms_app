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
      <template v-else-if="column.key === 'config'">
        <a-tag :bordered="false" :color="isConfigured(record) ? 'green' : 'orange'">
          {{ isConfigured(record) ? '已配置' : '未配置' }}
        </a-tag>
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
      <template v-else-if="column.key === 'status'">
        <a-tag v-if="isNoReportRow(record)" :bordered="false">暂无上报数据</a-tag>
        <StatusTag v-else :is-alarm="record.is_alarm" :is-offline="record.is_offline" />
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
        <span v-if="record.__rt0.isEmpty" class="empty-value">-</span>
        <div v-else class="rt-metric-cell" :title="record.__rt0.title">
          <div class="rt-metric-row">
            <span>mean: <span :class="valueClass(record.__rt0.mean)">{{ record.__rt0.mean }}</span></span>
            <span>std: <span :class="valueClass(record.__rt0.std)">{{ record.__rt0.std }}</span></span>
          </div>
          <div class="rt-metric-row">
            <span>p50: <span :class="valueClass(record.__rt0.p50)">{{ record.__rt0.p50 }}</span></span>
            <span>p90: <span :class="valueClass(record.__rt0.p90)">{{ record.__rt0.p90 }}</span></span>
          </div>
        </div>
      </template>
      <template v-else-if="column.key === 'rt1'">
        <span v-if="record.__rt1.isEmpty" class="empty-value">-</span>
        <div v-else class="rt-metric-cell" :title="record.__rt1.title">
          <div class="rt-metric-row">
            <span>mean: <span :class="valueClass(record.__rt1.mean)">{{ record.__rt1.mean }}</span></span>
            <span>std: <span :class="valueClass(record.__rt1.std)">{{ record.__rt1.std }}</span></span>
          </div>
          <div class="rt-metric-row">
            <span>p50: <span :class="valueClass(record.__rt1.p50)">{{ record.__rt1.p50 }}</span></span>
            <span>p90: <span :class="valueClass(record.__rt1.p90)">{{ record.__rt1.p90 }}</span></span>
          </div>
        </div>
      </template>
      <template v-else-if="column.key === 'action'">
        <a-space :size="0">
          <a-button type="link" size="small" @click="showUnavailable('重启')">重启</a-button>
          <a-button type="link" size="small" danger @click="showUnavailable('停止')">停止</a-button>
        </a-space>
      </template>
    </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { message, type TableColumnsType } from 'ant-design-vue';
import type { MonitorRow } from '../api/omms';
import StatusTag from './StatusTag.vue';

const props = defineProps<{
  rows: MonitorRow[];
  loading?: boolean;
}>();

const columns: TableColumnsType = [
  { title: '标签', key: 'label', width: 170 },
  { title: '进程名', key: 'process_name', width: 140 },
  { title: '配置', key: 'config', width: 100, align: 'center' },
  { title: 'args', key: 'args', width: 280 },
  { title: 'PID', key: 'pid', width: 90 },
  { title: 'CPU (%)', key: 'cpu', width: 80 },
  { title: '内存 (M)', key: 'mem', width: 90 },
  { title: '更新时间', key: 'update_time', width: 150 },
  { title: '状态', key: 'status', width: 110, align: 'center' },
  { title: 'mds', key: 'mds', width: 120 },
  { title: 'algo00x_cfg', key: 'algo00x_cfg', width: 110 },
  { title: 'ord_speed', key: 'ord_speed', width: 90 },
  { title: 'ord_dist', key: 'ord_dist', width: 200 },
  { title: 'rt0', key: 'rt0', width: 240 },
  { title: 'rt1', key: 'rt1', width: 240 },
  { title: '操作', key: 'action', width: 120, align: 'center' },
];

// 在进入模板前一次性补齐稳定行键和 roundtrip 展示模型，避免单元格重复解析 extra。
const tableRows = computed(() =>
  props.rows.map((row, index) => ({
    __rowKey: row.id ?? `${row.machine_tag || 'machine'}-${getProcessName(row)}-${row.pid ?? 'pid'}-${index}`,
    ...row,
    __rt0: formatRoundtrip(row, 'r0'),
    __rt1: formatRoundtrip(row, 'r1'),
  })),
);

/**
 * 组合分组与机器标签作为进程行标题。
 *
 * @param row 进程监控行。
 * @returns ``分组/机器`` 标签；缺少分组时使用“未分组”。
 */
function formatProcessLabel(row: MonitorRow) {
  const machineTag = String(row.machine_tag ?? '').trim();
  if (!machineTag) return '-';

  const group = String(row.group ?? '').trim();
  return group ? `${group}/${machineTag}` : `未分组/${machineTag}`;
}

/**
 * 按兼容字段优先级读取进程名称。
 *
 * @param row 进程监控行。
 * @returns 进程名称或占位符。
 */
function getProcessName(row: MonitorRow) {
  return row.process_name || row.proc_name || row.name || '-';
}

/**
 * 判断进程是否来自配置项。
 *
 * @param row 进程监控行。
 * @returns 仅显式为 false 时返回 false。
 */
function isConfigured(row: MonitorRow) {
  return row.is_configured !== false;
}

/**
 * 判断值是否包含非空内容。
 *
 * @param value 待检查值。
 * @returns 值非 null、undefined 和空字符串时返回 true。
 */
function hasValue(value: unknown) {
  return value !== null && value !== undefined && String(value).trim() !== '';
}

/**
 * 识别已配置但尚无运行指标的进程行。
 *
 * @param row 进程监控行。
 * @returns 缺少关键指标且没有异常标记时返回 true。
 */
function isNoReportRow(row: MonitorRow) {
  // 已配置但没有任何运行指标，且后端未标记异常/离线时，单独显示“暂无上报数据”。
  return (
    isConfigured(row) &&
    !hasValue(row.pid) &&
    !hasValue(row.cpu) &&
    !hasValue(row.mem) &&
    !hasValue(row.memory) &&
    !hasValue(row.mem_usage) &&
    !hasValue(row.update_time) &&
    Number(row.is_alarm) !== 1 &&
    Number(row.is_offline) !== 1
  );
}

/**
 * 按兼容字段优先级读取更新时间。
 *
 * @param row 进程监控行。
 * @returns 第一个有效时间或占位符。
 */
function getUpdateTime(row: MonitorRow) {
  return row.update_time || row.updated_at || row.collect_time || row.timestamp || '-';
}

/**
 * 安全读取进程 extra 中的指定字段。
 *
 * @param row 进程监控行。
 * @param key extra 字段名。
 * @returns 字段值；extra 不是普通对象时返回 undefined。
 */
function getExtra(row: MonitorRow, key: string) {
  return isPlainRecord(row.extra) ? row.extra[key] : undefined;
}

/**
 * 把未知类型值格式化为表格文本。
 *
 * @param value 原始值。
 * @returns 规范化文本；空值返回占位符。
 */
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

/**
 * 把 ord_dist 的数组、对象或标量格式化为稳定文本。
 *
 * @param value 原始 ord_dist 值。
 * @returns 使用连字符连接的展示文本或占位符。
 */
function formatOrdDist(value: unknown) {
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => formatValue(item)).join('-') : '-';
  }
  if (!isPlainRecord(value)) return formatValue(value);

  // 对象按 key 排序后只展示 value，确保相同数据每次渲染顺序一致。
  const entries = Object.entries(value).sort(([left], [right]) => left.localeCompare(right));
  return entries.length ? entries.map(([, item]) => formatValue(item)).join('-') : '-';
}

/**
 * 从 extra.roundtrip 中提取一组往返指标展示模型。
 *
 * @param row 进程监控行。
 * @param key roundtrip 子项键。
 * @returns 包含 mean、std、p50、p90、空值标记和提示文本的对象。
 */
function formatRoundtrip(row: MonitorRow, key: 'r0' | 'r1') {
  // roundtrip 位于 extra 的嵌套对象中，缺失或类型不符时按空指标处理。
  const roundtrip = getExtra(row, 'roundtrip');
  const metrics: Record<string, unknown> =
    isPlainRecord(roundtrip) && isPlainRecord(roundtrip[key]) ? roundtrip[key] : {};
  const mean = formatRoundtripMetric(metrics.mean);
  const std = formatRoundtripMetric(metrics.std);
  const p50 = formatRoundtripMetric(metrics.p50);
  const p90 = formatRoundtripMetric(metrics.p90);

  return {
    mean,
    std,
    p50,
    p90,
    isEmpty: [mean, std, p50, p90].every((value) => value === '-'),
    title: `mean: ${mean}, std: ${std}, p50: ${p50}, p90: ${p90}`,
  };
}

/**
 * 归一化单个 roundtrip 指标。
 *
 * @param value 数字或数字字符串。
 * @returns 缩放并保留一位小数的文本；非法值返回占位符。
 */
function formatRoundtripMetric(value: unknown) {
  if (typeof value !== 'number' && typeof value !== 'string') return '-';
  if (typeof value === 'string' && !value.trim()) return '-';

  // 数字和数字字符串共用既有的千分缩放展示规则，非法值统一显示为空。
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? (numberValue / 1000).toFixed(1) : '-';
}

/**
 * 提示指定进程操作尚未接入。
 *
 * @param action 用户点击的操作名称。
 */
function showUnavailable(action: '重启' | '停止') {
  message.info(`${action}功能暂未接入`);
}

/**
 * 为占位值返回弱化显示样式。
 *
 * @param value 已格式化的文本。
 * @returns 占位样式类名或 undefined。
 */
function valueClass(value: string | undefined) {
  return value === '-' ? 'empty-value' : undefined;
}

/**
 * 判断值是否为可按键读取的非数组对象。
 *
 * @param value 待判断值。
 * @returns 值为普通记录时返回 true。
 */
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

.rt-metric-cell {
  display: inline-flex;
  flex-direction: column;
  line-height: 1.25;
  vertical-align: middle;
  white-space: nowrap;
}

.rt-metric-row {
  display: flex;
  gap: 12px;
}

.empty-value {
  color: #cbd5e1;
}
</style>
