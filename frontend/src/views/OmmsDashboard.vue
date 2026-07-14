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
        <SectionCard title="OS 状态" description="机器资源使用率与在线状态">
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
        <SectionCard title="进程状态" description="关键进程资源占用与运行状态">
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
                <div>
                  <div class="process-group-title">op</div>
                  <div class="process-group-desc">普通运维进程</div>
                </div>
                <span class="process-group-count">{{ opProcessRows.length }} 条</span>
              </div>
              <ProcessStatusTable compact :rows="opProcessRows" :loading="processLoading" />
            </div>
            <div v-if="processLoading || algoProcessRows.length" class="process-group-block">
              <div class="process-group-header">
                <div>
                  <div class="process-group-title">algo00x</div>
                  <div class="process-group-desc">算法交易进程</div>
                </div>
                <span class="process-group-count">{{ algoProcessRows.length }} 条</span>
              </div>
              <AlgoProcessStatusTable :rows="algoProcessRows" :loading="processLoading" />
            </div>
            <div v-if="otherProcessRows.length" class="process-group-block">
              <div class="process-group-header">
                <div>
                  <div class="process-group-title">其他分组</div>
                  <div class="process-group-desc">未配置专用列的进程</div>
                </div>
                <span class="process-group-count">{{ otherProcessRows.length }} 条</span>
              </div>
              <ProcessStatusTable compact :rows="otherProcessRows" :loading="processLoading" />
            </div>
            <div v-if="ungroupedProcessRows.length" class="process-group-block">
              <div class="process-group-header">
                <div>
                  <div class="process-group-title">未分组</div>
                  <div class="process-group-desc">未匹配到 group 的上报进程</div>
                </div>
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
        <SectionCard title="最近日志" description="来自最近日志接口的当天日志记录">
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

const baseListParams: Omit<MonitorListParams, 'group'> = {
  page_no: 1,
  page_size: 100,
  sort_by: '',
  sort_order: '',
};

const visibleOsRows = computed(() => filterRows(osRows.value, osOnlyError.value));
const visibleProcessRows = computed(() => filterRows(processRows.value, processOnlyError.value));
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

function setSectionRef(key: SectionKey) {
  return (element: Element | ComponentPublicInstance | null) => {
    if (element instanceof HTMLElement) {
      sectionRefs.set(key, element);
    }
  };
}

function scrollToSection(key: SectionKey) {
  activeSection.value = key;
  sectionRefs.get(key)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

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

async function refreshAll() {
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

async function loadOverviewTotal() {
  overviewTotal.value = await fetchOverviewTotal();
}

async function loadOsRows(group: string) {
  osLoading.value = true;
  try {
    const data = await fetchOverviewOsList({ ...baseListParams, group });
    osRows.value = normalizeRows(data);
  } finally {
    osLoading.value = false;
  }
}

async function loadProcessRows(group: string) {
  processLoading.value = true;
  try {
    const data = await fetchOverviewProcessList({ ...baseListParams, group });
    processRows.value = normalizeRows(data);
  } finally {
    processLoading.value = false;
  }
}

async function loadLogRows() {
  logLoading.value = true;
  logErrorMessage.value = '';
  try {
    const data = await fetchOverviewLogList(buildLogListParams());
    logRows.value = normalizeRows(data);
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

async function handleOsGroupChange(value: string) {
  await runAction(() => loadOsRows(value));
}

async function handleProcessGroupChange(value: string) {
  await runAction(() => loadProcessRows(value));
}

async function handleLogGroupChange() {
  logPageNo.value = 1;
  await loadLogRows();
}

async function handleLogMachineTagSearch(value: string) {
  const machineTag = value.trim();
  logMachineTagInput.value = machineTag;
  logMachineTag.value = machineTag;
  logPageNo.value = 1;
  await loadLogRows();
}

function handleLogMachineTagInputChange(event: Event) {
  const value = (event.target as HTMLInputElement | null)?.value ?? logMachineTagInput.value;
  if (value.trim() || !logMachineTag.value) return;

  logMachineTagInput.value = '';
  logMachineTag.value = '';
  logPageNo.value = 1;
  void loadLogRows();
}

async function handleLogPageChange(pageNo: number) {
  logPageNo.value = pageNo;
  await loadLogRows();
}

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

function startAutoRefresh() {
  if (refreshTimer) return;
  refreshTimer = window.setInterval(refreshAll, AUTO_REFRESH_INTERVAL_MS);
}

function stopAutoRefresh() {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = undefined;
  }
}

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

function normalizeRows<T>(data: MonitorListData<T> | T[]) {
  if (Array.isArray(data)) return data;
  return data.details || data.list || data.records || data.items || data.rows || data.data || [];
}

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

function normalizeGroup(group: unknown) {
  return String(group ?? '').trim();
}

function filterRows(rows: MonitorRow[], onlyError: boolean) {
  return onlyError ? rows.filter((row) => isExceptionRow(row)) : rows;
}

function isExceptionRow(row: MonitorRow) {
  return Number(row.is_alarm) === 1 || Number(row.is_offline) === 1;
}

function countAlarm(rows: Array<{ is_alarm?: unknown }>) {
  return rows.filter((row) => flag(row.is_alarm)).length;
}

function countOffline(rows: MonitorRow[]) {
  return rows.filter((row) => flag(row.is_offline)).length;
}

function flag(value: unknown) {
  return value === true || value === 1 || value === '1';
}

function resolveStatBlock(title: string, blockKeys: string[], fallback: Omit<StatBlock, 'title'>): StatBlock {
  const source = overviewTotal.value;
  const block = findStatBlock(source, blockKeys);

  return {
    title,
    total: readNumber(block, ['total', 'count'], fallback.total),
    alarm: readNumber(block, ['alarm', 'alarm_count', 'alarmCount'], fallback.alarm),
    error: readNumber(block, ['error', 'error_count', 'errorCount', 'offline', 'offline_count'], fallback.error),
  };
}

function findStatBlock(source: OverviewTotalData, blockKeys: string[]) {
  for (const key of blockKeys) {
    const directValue = source[key];
    if (isRecord(directValue)) return directValue;
  }

  return source;
}

function readNumber(source: Record<string, unknown>, keys: string[], fallback: number) {
  for (const key of keys) {
    const value = source[key];
    const numberValue = Number(value);
    if (Number.isFinite(numberValue)) return numberValue;
  }

  return fallback;
}

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

.process-group-desc {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 12px;
}

.process-group-count {
  flex: none;
  color: #64748b;
  font-size: 12px;
}
</style>
