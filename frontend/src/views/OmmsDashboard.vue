<template>
  <div class="dashboard-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand__mark">OM</span>
        <div>
          <strong>运维中心</strong>
          <small>Operations Monitor</small>
        </div>
      </div>

      <nav class="side-menu">
        <button
          v-for="item in menuItems"
          :key="item.key"
          type="button"
          :class="{ active: activeSection === item.key }"
          @click="scrollToSection(item.key)"
        >
          {{ item.label }}
        </button>
      </nav>
    </aside>

    <main class="dashboard-main">
      <header class="topbar">
        <div>
          <p class="eyebrow">OMMS Monitor Center</p>
          <h1>运维监控中心</h1>
        </div>
        <div class="topbar__actions">
          <span class="refresh-text">刷新间隔 5 秒</span>
          <a-switch v-model:checked="autoRefresh" checked-children="自动" un-checked-children="手动" />
          <a-button type="primary" :loading="pageLoading" @click="refreshAll">刷新</a-button>
        </div>
      </header>

      <div v-if="errorMessage" class="error-banner">
        {{ errorMessage }}
      </div>

      <section :ref="setSectionRef('overview')" class="scroll-section">
        <div class="stat-grid">
          <StatCard
            v-for="card in statCards"
            :key="card.title"
            :title="card.title"
            :total="card.total"
            :alarm="card.alarm"
            :error="card.error"
          />
        </div>
      </section>

      <section :ref="setSectionRef('os')" class="scroll-section">
        <SectionCard title="OS 状态">
          <template #extra>
            <a-space class="section-filter" :size="8">
              <span class="only-error-label">仅异常</span>
              <a-switch v-model:checked="osOnlyError" size="small" />
              <GroupFilter v-model="osGroup" :options="groupOptions" @change="handleOsGroupChange" />
            </a-space>
          </template>
          <OsStatusTable :rows="visibleOsRows" :loading="osLoading" />
        </SectionCard>
      </section>

      <section :ref="setSectionRef('process')" class="scroll-section">
        <SectionCard title="进程状态">
          <template #extra>
            <a-space class="section-filter" :size="8">
              <span class="only-error-label">仅异常</span>
              <a-switch v-model:checked="processOnlyError" size="small" />
              <GroupFilter
                v-model="processGroup"
                :options="groupOptions"
                @change="handleProcessGroupChange"
              />
            </a-space>
          </template>
          <div v-if="processGroup === ''" class="process-group-list">
            <div v-if="processLoading || opProcessRows.length" class="process-group-block">
              <div class="process-group-header">
                <div class="process-group-title">op</div>
                <span class="process-group-count">{{ opProcessRows.length }} 条</span>
              </div>
              <ProcessStatusTable compact :rows="opProcessRows" :loading="processLoading" />
            </div>
            <div v-if="processLoading || algoProcessRows.length" class="process-group-block">
              <div class="process-group-header">
                <div class="process-group-title">algo00x</div>
                <span class="process-group-count">{{ algoProcessRows.length }} 条</span>
              </div>
              <AlgoProcessStatusTable :rows="algoProcessRows" :loading="processLoading" />
            </div>
            <div v-if="otherProcessRows.length" class="process-group-block">
              <div class="process-group-header">
                <div class="process-group-title">其他分组</div>
                <span class="process-group-count">{{ otherProcessRows.length }} 条</span>
              </div>
              <ProcessStatusTable compact :rows="otherProcessRows" :loading="processLoading" />
            </div>
            <div v-if="ungroupedProcessRows.length" class="process-group-block">
              <div class="process-group-header">
                <div class="process-group-title">未分组</div>
                <span class="process-group-count">{{ ungroupedProcessRows.length }} 条</span>
              </div>
              <ProcessStatusTable compact :rows="ungroupedProcessRows" :loading="processLoading" />
            </div>
          </div>
          <AlgoProcessStatusTable
            v-else-if="normalizedProcessGroup === 'algo00x'"
            :rows="algoProcessRows"
            :loading="processLoading"
          />
          <ProcessStatusTable v-else :rows="visibleProcessRows" :loading="processLoading" />
        </SectionCard>
      </section>

      <section :ref="setSectionRef('logs')" class="scroll-section">
        <SectionCard title="最近日志">
          <template #extra>
            <a-space class="section-filter" :size="8">
              <a-input-search
                v-model:value="logMachineTagInput"
                placeholder="机器标识"
                allow-clear
                size="small"
                style="width: 180px"
                @search="handleLogMachineTagSearch"
                @change="handleLogMachineTagInputChange"
              />
              <span class="only-error-label">仅异常</span>
              <a-switch v-model:checked="logOnlyError" size="small" />
              <GroupFilter v-model="logGroup" :options="groupOptions" @change="handleLogGroupChange" />
            </a-space>
          </template>
          <RecentLogTable
            :rows="logRows"
            :loading="logLoading"
            :error-message="logErrorMessage"
            :total="logTotal"
            :page-no="logPageNo"
            :page-size="logPageSize"
            @change-page="handleLogPageChange"
          />
        </SectionCard>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type ComponentPublicInstance } from 'vue';
import { message } from 'ant-design-vue';
import {
  fetchMonitorGroupList,
  fetchOverviewLogList,
  fetchOverviewOsList,
  fetchOverviewProcessList,
  fetchOverviewTotal,
  type LogListParams,
  type LogRow,
  type MonitorGroupItem,
  type MonitorListData,
  type MonitorListParams,
  type MonitorRow,
  type OverviewTotalData,
} from '../api/omms';
import GroupFilter from '../components/GroupFilter.vue';
import AlgoProcessStatusTable from '../components/AlgoProcessStatusTable.vue';
import OsStatusTable from '../components/OsStatusTable.vue';
import ProcessStatusTable from '../components/ProcessStatusTable.vue';
import RecentLogTable from '../components/RecentLogTable.vue';
import SectionCard from '../components/SectionCard.vue';
import StatCard from '../components/StatCard.vue';

type SectionKey = 'overview' | 'os' | 'process' | 'logs';

interface GroupOption {
  label: string;
  value: string;
}

interface StatBlock {
  title: string;
  total: number;
  alarm: number;
  error: number;
}

const FIXED_GROUP_OPTIONS: GroupOption[] = [
  { label: '\u5168\u90e8', value: '' },
];

const menuItems: { key: SectionKey; label: string }[] = [
  { key: 'overview', label: '监控总览' },
  { key: 'os', label: 'OS 监控' },
  { key: 'process', label: '进程监控' },
  { key: 'logs', label: '关键日志' },
];

const AUTO_REFRESH_INTERVAL_MS = 5000;

const overviewTotal = ref<OverviewTotalData>({});
const groupItems = ref<MonitorGroupItem[]>([]);
const groupLoading = ref(false);
const osRows = ref<MonitorRow[]>([]);
const processRows = ref<MonitorRow[]>([]);
const logRows = ref<LogRow[]>([]);
const osGroup = ref('');
const processGroup = ref('');
const logGroup = ref('');
const osOnlyError = ref(false);
const processOnlyError = ref(false);
const logOnlyError = ref(false);
const logMachineTagInput = ref('');
const logMachineTag = ref('');
const logPageNo = ref(1);
const logPageSize = ref(20);
const logTotal = ref(0);
const autoRefresh = ref(true);
const refreshing = ref(false);
const pageLoading = ref(false);
const osLoading = ref(false);
const processLoading = ref(false);
const logLoading = ref(false);
const errorMessage = ref('');
const logErrorMessage = ref('');
const activeSection = ref<SectionKey>('overview');
const sectionRefs = new Map<SectionKey, HTMLElement>();
let refreshTimer: number | undefined;

// OS 与进程列表统一取接口第一页；分组切换时只替换 group，保持请求口径一致。
const baseListParams: Omit<MonitorListParams, 'group'> = {
  page_no: 1,
  page_size: 100,
  sort_by: '',
  sort_order: '',
};

const visibleOsRows = computed(() =>
  [...filterRows(osRows.value, osOnlyError.value)].sort(compareOsRows),
);
const visibleProcessRows = computed(() => filterRows(processRows.value, processOnlyError.value));
// “全部”视图按分组拆给不同表格；指定分组时仍复用对应的过滤结果。
const normalizedProcessGroup = computed(() => processGroup.value.trim());
const opProcessRows = computed(() => visibleProcessRows.value.filter((row) => normalizeGroup(row.group) === 'op'));
const algoProcessRows = computed(() =>
  visibleProcessRows.value.filter((row) => normalizeGroup(row.group) === 'algo00x'),
);
const otherProcessRows = computed(() =>
  visibleProcessRows.value.filter((row) => {
    const group = normalizeGroup(row.group);
    return Boolean(group) && group !== 'op' && group !== 'algo00x';
  }),
);
const ungroupedProcessRows = computed(() =>
  visibleProcessRows.value.filter((row) => !normalizeGroup(row.group)),
);
const osAlarmCount = computed(() => countAlarm(osRows.value));
const processAlarmCount = computed(() => countAlarm(processRows.value));
const logAlarmCount = computed(() => countAlarm(logRows.value));
const groupOptions = computed<GroupOption[]>(() => [
  ...FIXED_GROUP_OPTIONS,
  ...groupItems.value.map((item) => ({
    label: item.display_name || item.group,
    value: item.group,
  })),
]);

// 优先读取总览接口的兼容字段；字段缺失时用当前明细数据生成可展示的兜底统计。
const statCards = computed<StatBlock[]>(() => [
  resolveStatBlock('OS 状态', ['os', 'os_status', 'osStatus', 'os_total', 'osTotal'], {
    total: osRows.value.length,
    alarm: osAlarmCount.value,
    error: countOffline(osRows.value),
  }),
  resolveStatBlock(
    '进程状态',
    ['process', 'process_status', 'processStatus', 'process_total', 'processTotal'],
    {
      total: processRows.value.length,
      alarm: processAlarmCount.value,
      error: countOffline(processRows.value),
    },
  ),
  resolveStatBlock('日志状态', ['log', 'logs', 'log_status', 'logStatus', 'log_total', 'logTotal'], {
    total: logRows.value.length,
    alarm: logAlarmCount.value,
    error: logAlarmCount.value,
  }),
]);

onMounted(() => {
  loadGroupItems();
  refreshAll();
  startAutoRefresh();
});

onBeforeUnmount(() => {
  stopAutoRefresh();
});

watch(autoRefresh, (enabled) => {
  if (enabled) {
    startAutoRefresh();
    return;
  }

  stopAutoRefresh();
});

watch(logOnlyError, () => {
  logPageNo.value = 1;
  void loadLogRows();
});

/**
 * 创建用于登记页面区块元素的 ref 回调。
 *
 * @param key 区块标识。
 * @returns 接收组件或 DOM 元素并更新区块映射的回调。
 */
function setSectionRef(key: SectionKey) {
  return (element: Element | ComponentPublicInstance | null) => {
    if (element instanceof HTMLElement) {
      sectionRefs.set(key, element);
    }
  };
}

/**
 * 激活侧边栏区块并平滑滚动到对应位置。
 *
 * @param key 目标区块标识。
 */
function scrollToSection(key: SectionKey) {
  activeSection.value = key;
  sectionRefs.get(key)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * 加载并归一化监控分组列表。
 *
 * 请求失败时清空分组并记录警告，避免阻断其他监控数据加载。
 *
 * @returns 分组请求完成后的 Promise。
 */
async function loadGroupItems() {
  groupLoading.value = true;

  try {
    const data = await fetchMonitorGroupList();
    groupItems.value = normalizeGroupItems(data.details);
  } catch (error) {
    groupItems.value = [];
    console.warn('Failed to load monitor groups', error);
  } finally {
    groupLoading.value = false;
  }
}

/**
 * 并发刷新总览、OS、进程和日志数据。
 *
 * 同一时刻只允许一轮刷新；任一请求失败时统一展示页面级错误。
 *
 * @returns 本轮刷新完成后的 Promise。
 */
async function refreshAll() {
  // 自动刷新和手动刷新共用入口，防止上一轮请求未结束时再次并发刷新。
  if (refreshing.value) return;

  refreshing.value = true;
  pageLoading.value = true;
  errorMessage.value = '';

  try {
    await Promise.all([
      loadOverviewTotal(),
      loadOsRows(osGroup.value),
      loadProcessRows(processGroup.value),
      loadLogRows(),
    ]);
  } catch (error) {
    const text = error instanceof Error ? error.message : '请求失败';
    errorMessage.value = text;
    message.error(text);
  } finally {
    pageLoading.value = false;
    refreshing.value = false;
  }
}

/**
 * 加载总览统计并更新卡片数据源。
 *
 * @returns 总览请求完成后的 Promise。
 */
async function loadOverviewTotal() {
  overviewTotal.value = await fetchOverviewTotal();
}

/**
 * 按分组加载 OS 状态列表。
 *
 * @param group 分组名称，空字符串表示全部。
 * @returns OS 请求完成后的 Promise。
 */
async function loadOsRows(group: string) {
  osLoading.value = true;
  try {
    const data = await fetchOverviewOsList({ ...baseListParams, group });
    osRows.value = normalizeRows(data);
  } finally {
    osLoading.value = false;
  }
}

/**
 * 按分组加载进程状态列表。
 *
 * @param group 分组名称，空字符串表示全部。
 * @returns 进程请求完成后的 Promise。
 */
async function loadProcessRows(group: string) {
  processLoading.value = true;
  try {
    const data = await fetchOverviewProcessList({ ...baseListParams, group });
    processRows.value = normalizeRows(data);
  } finally {
    processLoading.value = false;
  }
}

/**
 * 使用当前日志筛选和分页状态加载日志列表。
 *
 * 同时兼容数组响应与带分页元数据的对象响应，并单独维护日志错误提示。
 *
 * @returns 日志请求完成后的 Promise。
 */
async function loadLogRows() {
  logLoading.value = true;
  logErrorMessage.value = '';
  try {
    const data = await fetchOverviewLogList(buildLogListParams());
    logRows.value = normalizeRows(data);
    // 同时兼容直接数组和带分页元数据的接口响应。
    if (Array.isArray(data)) {
      logTotal.value = data.length;
    } else {
      logTotal.value = data.total ?? 0;
      logPageNo.value = data.page_no ?? logPageNo.value;
      logPageSize.value = data.page_size ?? logPageSize.value;
    }
  } catch (error) {
    const text = error instanceof Error ? error.message : '请求失败';
    logErrorMessage.value = `最近日志请求失败：${text}`;
    message.error(logErrorMessage.value);
  } finally {
    logLoading.value = false;
  }
}

/**
 * 响应 OS 分组变化并通过统一错误处理重新加载列表。
 *
 * @param value 新分组值。
 * @returns 分组切换处理完成后的 Promise。
 */
async function handleOsGroupChange(value: string) {
  await runAction(() => loadOsRows(value));
}

/**
 * 响应进程分组变化并通过统一错误处理重新加载列表。
 *
 * @param value 新分组值。
 * @returns 分组切换处理完成后的 Promise。
 */
async function handleProcessGroupChange(value: string) {
  await runAction(() => loadProcessRows(value));
}

/**
 * 响应日志分组变化，重置页码后重新加载日志。
 *
 * @returns 日志刷新完成后的 Promise。
 */
async function handleLogGroupChange() {
  // 筛选条件变化后回到第一页，避免沿用旧页码得到空列表。
  logPageNo.value = 1;
  await loadLogRows();
}

/**
 * 提交机器标识搜索条件并从第一页加载日志。
 *
 * @param value 搜索框中的机器标识。
 * @returns 日志刷新完成后的 Promise。
 */
async function handleLogMachineTagSearch(value: string) {
  const machineTag = value.trim();
  logMachineTagInput.value = machineTag;
  logMachineTag.value = machineTag;
  logPageNo.value = 1;
  await loadLogRows();
}

/**
 * 处理机器标识输入变化，并在清空已生效条件时立即刷新日志。
 *
 * @param event 输入框 change 事件。
 */
function handleLogMachineTagInputChange(event: Event) {
  const value = (event.target as HTMLInputElement | null)?.value ?? logMachineTagInput.value;
  // 普通输入等待显式搜索；只有清空已生效的条件时才立即重新请求。
  if (value.trim() || !logMachineTag.value) return;

  logMachineTagInput.value = '';
  logMachineTag.value = '';
  logPageNo.value = 1;
  void loadLogRows();
}

/**
 * 切换日志页码并请求对应页面。
 *
 * @param pageNo 目标页码。
 * @returns 日志刷新完成后的 Promise。
 */
async function handleLogPageChange(pageNo: number) {
  logPageNo.value = pageNo;
  await loadLogRows();
}

/**
 * 执行页面操作并统一转换、展示异常信息。
 *
 * @param action 待执行的异步操作。
 * @returns 操作处理完成后的 Promise。
 */
async function runAction(action: () => Promise<void>) {
  errorMessage.value = '';
  try {
    await action();
  } catch (error) {
    const text = error instanceof Error ? error.message : '请求失败';
    errorMessage.value = text;
    message.error(text);
  }
}

/**
 * 启动唯一的自动刷新定时器。
 */
function startAutoRefresh() {
  if (refreshTimer) return;
  refreshTimer = window.setInterval(refreshAll, AUTO_REFRESH_INTERVAL_MS);
}

/**
 * 清除自动刷新定时器并重置定时器引用。
 */
function stopAutoRefresh() {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = undefined;
  }
}

/**
 * 根据当前筛选和分页状态构造日志请求参数。
 *
 * @returns 可直接传给日志 API 的参数对象。
 */
function buildLogListParams(): LogListParams {
  return {
    group: logGroup.value,
    machine_tag: logMachineTag.value.trim() || undefined,
    only_error: logOnlyError.value ? 1 : 0,
    level: '',
    date: '',
    page_no: logPageNo.value,
    page_size: logPageSize.value,
    sort_by: '',
    sort_order: '',
  };
}

/**
 * 从数组或多种兼容响应字段中提取列表数据。
 *
 * @param data API 返回的数组或列表包装对象。
 * @returns 归一化后的条目数组，无法识别时返回空数组。
 */
function normalizeRows<T>(data: MonitorListData<T> | T[]) {
  // 后端兼容接口可能使用不同列表字段名，这里统一收敛为数组供组件消费。
  if (Array.isArray(data)) return data;
  return data.details || data.list || data.records || data.items || data.rows || data.data || [];
}

/**
 * 清理、去重并补齐分组展示名称。
 *
 * @param items API 返回的可选分组数组。
 * @returns 有效且按首次出现顺序保留的分组数组。
 */
function normalizeGroupItems(items?: MonitorGroupItem[]) {
  const seen = new Set<string>();

  return (items || []).flatMap((item) => {
    const group = item.group?.trim();
    if (!group || seen.has(group)) return [];

    seen.add(group);
    const displayName = item.display_name?.trim() || group;
    return [{ group, display_name: displayName }];
  });
}

/**
 * 把未知类型的分组值归一化为去除首尾空格的字符串。
 *
 * @param group 原始分组值。
 * @returns 归一化后的分组字符串。
 */
function normalizeGroup(group: unknown) {
  return String(group ?? '').trim();
}

/**
 * 按“有分组优先、分组名、机器标签”比较 OS 行。
 *
 * @param a 左侧 OS 行。
 * @param b 右侧 OS 行。
 * @returns 供 Array.sort 使用的比较结果。
 */
function compareOsRows(a: MonitorRow, b: MonitorRow) {
  const groupA = normalizeGroup(a.group);
  const groupB = normalizeGroup(b.group);

  if (groupA && !groupB) return -1;
  if (!groupA && groupB) return 1;

  const groupCompare = groupA.localeCompare(groupB);
  if (groupCompare !== 0) return groupCompare;

  return String(a.machine_tag ?? '').trim().localeCompare(String(b.machine_tag ?? '').trim());
}

/**
 * 根据“仅异常”开关筛选监控行。
 *
 * @param rows 原始监控行。
 * @param onlyError 是否仅保留异常行。
 * @returns 原数组或过滤后的新数组。
 */
function filterRows(rows: MonitorRow[], onlyError: boolean) {
  return onlyError ? rows.filter((row) => isExceptionRow(row)) : rows;
}

/**
 * 判断监控行是否被标记为告警或离线。
 *
 * @param row 监控行。
 * @returns 任一异常标记为 1 时返回 true。
 */
function isExceptionRow(row: MonitorRow) {
  return Number(row.is_alarm) === 1 || Number(row.is_offline) === 1;
}

/**
 * 统计带告警标记的行数。
 *
 * @param rows 含可选告警标记的行。
 * @returns 告警行数量。
 */
function countAlarm(rows: Array<{ is_alarm?: unknown }>) {
  return rows.filter((row) => flag(row.is_alarm)).length;
}

/**
 * 统计带离线标记的监控行数。
 *
 * @param rows 监控行数组。
 * @returns 离线行数量。
 */
function countOffline(rows: MonitorRow[]) {
  return rows.filter((row) => flag(row.is_offline)).length;
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

/**
 * 从兼容字段中解析统计卡片，并为缺失数字应用明细兜底值。
 *
 * @param title 卡片标题。
 * @param blockKeys 可能的统计块字段名。
 * @param fallback 明细数据计算出的兜底统计。
 * @returns 完整的统计卡片数据。
 */
function resolveStatBlock(title: string, blockKeys: string[], fallback: Omit<StatBlock, 'title'>): StatBlock {
  // 依次尝试新旧字段命名；都不存在时 findStatBlock 会回退到响应根对象。
  const source = overviewTotal.value;
  const block = findStatBlock(source, blockKeys);

  return {
    title,
    total: readNumber(block, ['total', 'count'], fallback.total),
    alarm: readNumber(block, ['alarm', 'alarm_count', 'alarmCount'], fallback.alarm),
    error: readNumber(block, ['error', 'error_count', 'errorCount', 'offline', 'offline_count'], fallback.error),
  };
}

/**
 * 查找第一个对象形式的统计块。
 *
 * @param source 总览响应对象。
 * @param blockKeys 候选字段名列表。
 * @returns 找到的统计块；没有匹配时返回响应根对象。
 */
function findStatBlock(source: OverviewTotalData, blockKeys: string[]) {
  for (const key of blockKeys) {
    const directValue = source[key];
    if (isRecord(directValue)) return directValue;
  }

  return source;
}

/**
 * 从候选字段中读取第一个有限数值。
 *
 * @param source 待读取的对象。
 * @param keys 候选数值字段名。
 * @param fallback 无有效字段时使用的值。
 * @returns 解析后的有限数值或兜底值。
 */
function readNumber(source: Record<string, unknown>, keys: string[], fallback: number) {
  for (const key of keys) {
    const value = source[key];
    const numberValue = Number(value);
    if (Number.isFinite(numberValue)) return numberValue;
  }

  return fallback;
}

/**
 * 判断值是否为非数组对象。
 *
 * @param value 待判断值。
 * @returns 值可作为普通记录读取时返回 true。
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
</script>

<style scoped>
.process-group-list {
  display: grid;
  gap: 14px;
}

.process-group-block {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.process-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

.process-group-title {
  color: #1e293b;
  font-size: 15px;
  font-weight: 600;
}

.process-group-count {
  flex: none;
  color: #64748b;
  font-size: 12px;
}
</style>
