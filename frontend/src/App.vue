<template>
  <a-config-provider :theme="theme">
    <OmmsDashboard />
  </a-config-provider>
</template>

<script setup lang="ts">
import OmmsDashboard from './views/OmmsDashboard.vue';

const theme = {
  token: {
    colorPrimary: '#2563eb',
    colorSuccess: '#16a34a',
    colorWarning: '#f59e0b',
    colorError: '#dc2626',
    colorText: '#1e293b',
    colorTextSecondary: '#64748b',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBorder: '#e2e8f0',
    colorBorderSecondary: '#edf2f7',
    borderRadius: 8,
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  },
};
</script>