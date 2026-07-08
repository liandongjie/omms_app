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
            <GroupFilter v-model="osGroup" :options="GROUP_OPTIONS" @change="handleOsGroupChange" />
          </template>
          <OsStatusTable :rows="visibleOsRows" :loading="osLoading" />
        </SectionCard>
      </section>

      <section :ref="setSectionRef('process')" class="scroll-section">
        <SectionCard title="进程状态" description="关键进程资源占用与运行状态">
          <template #extra>
            <GroupFilter
              v-model="processGroup"
              :options="GROUP_OPTIONS"
              @change="handleProcessGroupChange"
            />
          </template>
          <ProcessStatusTable :rows="visibleProcessRows" :loading="processLoading" />
        </SectionCard>
      </section>

      <section :ref="setSectionRef('logs')" class="scroll-section">
        <SectionCard title="最近日志" description="日志接口待接入，第一版保留页面区域">
          <template #extra>
            <GroupFilter v-model="logGroup" :options="GROUP_OPTIONS" />
          </template>
          <RecentLogTable :group="logGroup" />
        </SectionCard>
      </section>

      <section :ref="setSectionRef('alarms')" class="scroll-section">
        <SectionCard title="告警统计" description="基于当前 OS 和进程数据的本地统计">
          <AlarmSummary :os-alarm="osAlarmCount" :process-alarm="processAlarmCount" :log-alarm="0" />
        </SectionCard>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type ComponentPublicInstance } from 'vue';
import { message } from 'ant-design-vue';
import {
  fetchOverviewOsList,
  fetchOverviewProcessList,
  fetchOverviewTotal,
  type MonitorListData,
  type MonitorListParams,
  type MonitorRow,
  type OverviewTotalData,
} from '../api/omms';
import AlarmSummary from '../components/AlarmSummary.vue';
import GroupFilter from '../components/GroupFilter.vue';
import OsStatusTable from '../components/OsStatusTable.vue';
import ProcessStatusTable from '../components/ProcessStatusTable.vue';
import RecentLogTable from '../components/RecentLogTable.vue';
import SectionCard from '../components/SectionCard.vue';
import StatCard from '../components/StatCard.vue';

type SectionKey = 'overview' | 'os' | 'process' | 'logs' | 'alarms';

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

const GROUP_OPTIONS: GroupOption[] = [
  { label: '全部', value: '' },
  { label: '仅异常', value: '__only_error__' },
  { label: '股票组', value: 'stock' },
  { label: 'CTA组', value: 'algo00x' },
  { label: '套利组', value: 'fut' },
  { label: '公共服务组', value: 'op' },
  { label: '备机组', value: 'backup' },
];

const menuItems: { key: SectionKey; label: string }[] = [
  { key: 'overview', label: '监控总览' },
  { key: 'os', label: 'OS 监控' },
  { key: 'process', label: '进程监控' },
  { key: 'logs', label: '关键日志' },
  { key: 'alarms', label: '告警统计' },
];

const overviewTotal = ref<OverviewTotalData>({});
const osRows = ref<MonitorRow[]>([]);
const processRows = ref<MonitorRow[]>([]);
const osGroup = ref('');
const processGroup = ref('');
const logGroup = ref('');
const osRemoteGroup = ref('');
const processRemoteGroup = ref('');
const autoRefresh = ref(false);
const pageLoading = ref(false);
const osLoading = ref(false);
const processLoading = ref(false);
const errorMessage = ref('');
const activeSection = ref<SectionKey>('overview');
const sectionRefs = new Map<SectionKey, HTMLElement>();
let refreshTimer: number | undefined;

const baseListParams: Omit<MonitorListParams, 'group'> = {
  page_no: 1,
  page_size: 100,
  sort_by: '',
  sort_order: '',
};

const visibleOsRows = computed(() => filterRows(osRows.value, osGroup.value));
const visibleProcessRows = computed(() => filterRows(processRows.value, processGroup.value));
const osAlarmCount = computed(() => countAlarm(osRows.value));
const processAlarmCount = computed(() => countAlarm(processRows.value));

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
    total: 0,
    alarm: 0,
    error: 0,
  }),
]);

onMounted(() => {
  refreshAll();
});

onBeforeUnmount(() => {
  stopAutoRefresh();
});

watch(autoRefresh, (enabled) => {
  if (enabled) {
    refreshTimer = window.setInterval(refreshAll, 5000);
    return;
  }

  stopAutoRefresh();
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

async function refreshAll() {
  pageLoading.value = true;
  errorMessage.value = '';

  try {
    await Promise.all([
      loadOverviewTotal(),
      loadOsRows(osRemoteGroup.value),
      loadProcessRows(processRemoteGroup.value),
    ]);
  } catch (error) {
    const text = error instanceof Error ? error.message : '请求失败';
    errorMessage.value = text;
    message.error(text);
  } finally {
    pageLoading.value = false;
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

async function handleOsGroupChange(value: string) {
  if (value === '__only_error__') return;
  osRemoteGroup.value = value;
  await runAction(() => loadOsRows(value));
}

async function handleProcessGroupChange(value: string) {
  if (value === '__only_error__') return;
  processRemoteGroup.value = value;
  await runAction(() => loadProcessRows(value));
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

function stopAutoRefresh() {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = undefined;
  }
}

function normalizeRows(data: MonitorListData<MonitorRow> | MonitorRow[]) {
  if (Array.isArray(data)) return data;
  return data.details || data.list || data.records || data.items || data.rows || data.data || [];
}

function filterRows(rows: MonitorRow[], group: string) {
  if (group === '__only_error__') {
    return rows.filter((row) => isExceptionRow(row));
  }

  return rows;
}

function isExceptionRow(row: MonitorRow) {
  return Number(row.is_alarm) === 1 || Number(row.is_offline) === 1;
}

function countAlarm(rows: MonitorRow[]) {
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