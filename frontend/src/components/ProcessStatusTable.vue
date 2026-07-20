<template>
  <a-table
    row-key="__rowKey"
    size="middle"
    :columns="columns"
    :data-source="tableRows"
    :loading="loading"
    :pagination="compact
      ? { pageSize: 10, showSizeChanger: false, hideOnSinglePage: true }
      : { pageSize: 10, showSizeChanger: false }"
  >
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
        <div v-if="hasArgs(record)" class="process-args-cell">
          <span class="process-args-cell__text">{{ getArgsText(record) }}</span>
          <a-button class="process-args-cell__copy" type="link" size="small" @click="copyArgs(record)">
            复制
          </a-button>
        </div>
        <span v-else>-</span>
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
        <a-tag v-if="isNoReportRow(record)" :bordered="false">暂无上报数据</a-tag>
        <StatusTag v-else :is-alarm="record.is_alarm" :is-offline="record.is_offline" />
      </template>
      <template v-else-if="column.key === 'extra'">
        <a-button v-if="hasExtra(record)" type="link" size="small" @click="openExtraModal(record)">
          查看
        </a-button>
        <span v-else>-</span>
      </template>
      <template v-else-if="column.key === 'action'">
        <a-space :size="0">
          <a-button type="link" size="small" @click="showUnavailable('重启')">重启</a-button>
          <a-button type="link" size="small" danger @click="showUnavailable('停止')">停止</a-button>
        </a-space>
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
      <a-descriptions-item label="标签">
        {{ formatProcessLabel(selectedRow) }}
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
import { message, type TableColumnsType } from 'ant-design-vue';
import type { MonitorRow } from '../api/omms';
import StatusTag from './StatusTag.vue';

const props = defineProps<{
  rows: MonitorRow[];
  loading?: boolean;
  compact?: boolean;
}>();

const columns: TableColumnsType = [
  { title: '标签', key: 'label', width: 150 },
  { title: '进程名', key: 'process_name', width: 170 },
  { title: '配置', key: 'config', width: 100, align: 'center' },
  { title: 'args', key: 'args', width: 260 },
  { title: 'PID', key: 'pid', width: 100 },
  { title: 'CPU (%)', key: 'cpu', width: 110 },
  { title: '内存 (M)', key: 'mem', width: 110 },
  { title: '更新时间', key: 'update_time', width: 190 },
  { title: '状态', key: 'status', width: 110, align: 'center' },
  { title: '详情', key: 'extra', width: 90, align: 'center' },
  { title: '操作', key: 'action', width: 120, align: 'center' },
];

const extraModalOpen = ref(false);
const selectedRow = ref<MonitorRow | null>(null);

const tableRows = computed(() =>
  props.rows.map((row, index) => ({
    __rowKey: row.id ?? `${row.machine_tag || getMachineName(row)}-${getProcessName(row)}-${row.pid ?? 'pid'}-${index}`,
    ...row,
  })),
);

// 详情弹窗只展开 extra，基础字段仍由固定描述项展示，避免重复。
const selectedExtraItems = computed(() => {
  const extra = selectedRow.value?.extra;
  if (!isPlainRecord(extra)) return [];

  return Object.entries(extra).map(([key, value]) => ({
    key,
    value: formatExtraValue(value),
  }));
});

/**
 * 按兼容字段优先级读取机器标识。
 *
 * @param row 进程监控行。
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
 * 把进程启动参数转换为展示文本。
 *
 * @param row 进程监控行。
 * @returns 参数文本；空值返回占位符。
 */
function getArgsText(row: MonitorRow) {
  return hasArgs(row) ? row.args! : '-';
}

/**
 * 判断进程启动参数是否包含可展示、可复制的内容。
 *
 * @param row 进程监控行。
 * @returns 参数包含非空字符时返回 true。
 */
function hasArgs(row: MonitorRow) {
  // 纯空白参数按空值展示，避免为无意义内容提供复制入口。
  return Boolean(row.args?.trim());
}

/**
 * 把进程启动参数的原始值写入剪贴板并反馈结果。
 *
 * @param row 要复制参数的进程监控行。
 * @returns 剪贴板操作完成后的 Promise。
 */
async function copyArgs(row: MonitorRow) {
  // 表格始终展示完整 args；复制时直接使用接口原始值，避免复制到未来可能格式化的展示文本。
  const text = row.args;
  if (!text?.trim()) return;

  // 浏览器不支持剪贴板 API 或写入被拒绝时，明确提示用户手动复制。
  if (!navigator.clipboard?.writeText) {
    message.error('复制失败，请手动复制');
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    message.success('已复制 args');
  } catch {
    message.error('复制失败，请手动复制');
  }
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
  // 已配置项缺少运行指标但又未被后端判为异常时，与真正离线状态分开展示。
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
 * 把运行指标格式化为两位小数文本。
 *
 * @param value 原始指标值。
 * @returns 格式化数值、原始非法数值文本或占位符。
 */
function formatMetric(value: unknown) {
  if (value === null || value === undefined || value === '') return '-';
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return String(value);
  return numberValue.toFixed(2);
}

/**
 * 判断进程行是否包含可展示的扩展字段。
 *
 * @param row 进程监控行。
 * @returns extra 为非空普通对象时返回 true。
 */
function hasExtra(row: MonitorRow) {
  return isPlainRecord(row.extra) && Object.keys(row.extra).length > 0;
}

/**
 * 选中进程行并打开扩展信息弹窗。
 *
 * @param row 要查看的进程监控行。
 */
function openExtraModal(row: MonitorRow) {
  selectedRow.value = row;
  extraModalOpen.value = true;
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
 * 把扩展字段值转换为弹窗中的可读文本。
 *
 * @param value 原始扩展值。
 * @returns 字符串化后的值或占位符。
 */
function formatExtraValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-';
  // 复合值优先序列化为可读文本；无法序列化时退回通用字符串转换。
  if (Array.isArray(value) || typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
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
.process-args-cell {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 4px;
  width: 100%;
}

.process-args-cell__text {
  flex: 1 1 160px;
  min-width: 0;
  /* 在固定列宽内折行长参数，防止内容撑开或覆盖相邻列。 */
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  word-break: break-word;
}

.process-args-cell__copy {
  flex: none;
}

.detail-value {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
