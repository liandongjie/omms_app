export const FALLBACK_POLL_INTERVAL_MS = 5_000;
export const CONNECTED_RECONCILIATION_INTERVAL_MS = 30_000;

export function getAutoRefreshInterval(
  enabled: boolean,
  connected: boolean,
  visible: boolean,
): number | undefined {
  if (!enabled || !visible) return undefined;
  return connected ? CONNECTED_RECONCILIATION_INTERVAL_MS : FALLBACK_POLL_INTERVAL_MS;
}

export function createRefreshCoordinator(refreshOnce: () => Promise<void>) {
  let refreshing = false;
  let pending = false;

  const request = async () => {
    if (refreshing) {
      pending = true;
      return;
    }

    refreshing = true;
    try {
      do {
        pending = false;
        await refreshOnce();
      } while (pending);
    } finally {
      refreshing = false;
    }
  };

  return {
    request,
    requestAutomatic: (enabled: boolean) => (enabled ? request() : Promise.resolve()),
    // manual/hidden 模式取消尚未开始的补偿轮；正在执行的请求不做破坏性中断。
    cancelPending: () => {
      pending = false;
    },
  };
}
