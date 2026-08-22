/**
 * WebSocket 实时推送客户端。
 *
 * 职责：
 * - 连接 /ws/monitor，收到 refresh/hello 事件时回调 onRefresh（复用页面现有加载逻辑）；
 * - 每 10 秒发送心跳 ping，探测连接活性；
 * - 断线后每 3 秒自动重连，并通知页面切换 reconciliation polling 频率。
 */

export interface MonitorSocketCallbacks {
  onRefresh: () => void;
  onStatusChange: (connected: boolean) => void;
}

export interface MonitorSocketHandle {
  close: () => void;
}

const HEARTBEAT_INTERVAL_MS = 10_000;
const RECONNECT_DELAY_MS = 3_000;

export function connectMonitorSocket(callbacks: MonitorSocketCallbacks): MonitorSocketHandle {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${window.location.host}/ws/monitor`;

  let socket: WebSocket | null = null;
  let closed = false;
  let reconnectTimer: number | undefined;
  let heartbeatTimer: number | undefined;

  const clearTimers = () => {
    if (reconnectTimer !== undefined) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = undefined;
    }
    if (heartbeatTimer !== undefined) {
      window.clearInterval(heartbeatTimer);
      heartbeatTimer = undefined;
    }
  };

  const cleanupSocket = () => {
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      socket.close();
      socket = null;
    }
  };

  const scheduleReconnect = () => {
    clearTimers();
    callbacks.onStatusChange(false);
    if (closed) return;
    reconnectTimer = window.setTimeout(open, RECONNECT_DELAY_MS);
  };

  const open = () => {
    if (closed) return;
    try {
      socket = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      callbacks.onStatusChange(true);
      heartbeatTimer = window.setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send('ping');
        }
      }, HEARTBEAT_INTERVAL_MS);
    };

    socket.onmessage = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data as string) as { event?: string };
        // hello 表示刚连上，refresh 表示后端检测到数据变化；两者都触发一次刷新
        if (payload.event === 'refresh' || payload.event === 'hello') {
          callbacks.onRefresh();
        }
      } catch {
        // 忽略无法解析的服务端消息
      }
    };

    socket.onclose = () => {
      cleanupSocket();
      scheduleReconnect();
    };

    socket.onerror = () => {
      // 统一由 onclose 触发重连
    };
  };

  open();

  return {
    close: () => {
      closed = true;
      clearTimers();
      cleanupSocket();
      callbacks.onStatusChange(false);
    },
  };
}
