export type WsHandler = (payload: unknown) => void;

function getWsUrl(): string {
  const envWs = import.meta.env.VITE_WS_URL;
  if (envWs) return envWs;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

export function connectYardSocket(onMessage: WsHandler, onStatus: (live: boolean) => void): () => void {
  const url = getWsUrl();
  let socket: WebSocket | null = null;
  let closed = false;
  let retry = 1200;

  const open = () => {
    if (closed) return;
    socket = new WebSocket(url);
    socket.onopen = () => {
      retry = 1200;
      onStatus(true);
    };
    socket.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data as string));
      } catch {
        /* ignore malformed tick */
      }
    };
    socket.onclose = () => {
      onStatus(false);
      if (!closed) window.setTimeout(open, retry);
      retry = Math.min(retry * 1.6, 8000);
    };
    socket.onerror = () => socket?.close();
  };

  open();
  return () => {
    closed = true;
    socket?.close();
  };
}
