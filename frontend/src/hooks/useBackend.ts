import { useEffect, useRef, useState, useCallback } from "react";
import type { BackendState, AssistantState, NavTab } from "@/types";

const INITIAL_STATE: BackendState = {
  state: "IDLE",
  pulse: 1.0,
  status: {
    camera: "Paused",
    fps: 0,
    microphone: "Active",
    speaker: "Active",
    ai: "Ready",
    battery: "100%",
    network: "Online",
  },
  environment: {
    people: "None",
    room: "Workspace",
    lighting: "Normal",
    noise: "Low",
    safety: "Clear",
  },
  scene: {
    people: "0 | Objects: 0",
    left: "None",
    center: "None",
    right: "None",
    path: "Clear",
  },
  history: [],
  memories: [],
  activeTab: "home",
  currentTranscription: "",
  activeModel: "Gemini 3.1 Flash Live",
  isSleeping: false,
  firstRunCompleted: undefined,
  userName: "",
  hasApiKey: false,
  apiUsage: null,
  cameraMonitoring: {
    enabled: false,
    intervalSeconds: 10,
    status: "IDLE",
    lastObservationTime: null,
    latestDescription: "Camera monitoring is inactive.",
    error: null,
    peopleCount: 0,
    objectsCount: 0,
    movementDetected: false,
  },
};

export function useBackend() {
  const [data, setData] = useState<BackendState>(INITIAL_STATE);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const getWsUrl = useCallback(() => {
    const loc = window.location;
    const protocol = loc.protocol === "https:" ? "wss:" : "ws:";
    if (loc.port === "5173") {
      return `${protocol}//127.0.0.1:8000/ws`;
    }
    return `${protocol}//${loc.host}/ws`;
  }, []);

  const getHttpBase = useCallback(() => {
    const loc = window.location;
    if (loc.port === "5173") {
      return `http://127.0.0.1:8000`;
    }
    return `${loc.protocol}//${loc.host}`;
  }, []);

  // Poll HTTP status once at start or when offline
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${getHttpBase()}/api/status`);
      if (res.ok) {
        const json = await res.json();
        setData((prev) => ({
          ...prev,
          state: json.state || prev.state,
          pulse: json.pulse ?? prev.pulse,
          status: { ...prev.status, ...(json.status || {}) },
          environment: { ...prev.environment, ...(json.environment || {}) },
          scene: { ...prev.scene, ...(json.scene || {}) },
          history: json.history || prev.history,
          memories: json.memories || prev.memories,
          isSleeping: json.is_sleeping ?? prev.isSleeping,
          firstRunCompleted: json.first_run_completed ?? prev.firstRunCompleted,
          userName: json.user_name ?? prev.userName,
          hasApiKey: json.has_api_key ?? prev.hasApiKey,
          apiUsage: json.api_usage !== undefined ? json.api_usage : prev.apiUsage,
          cameraMonitoring: json.camera_monitoring !== undefined ? json.camera_monitoring : prev.cameraMonitoring,
        }));
        setIsConnected(true);
      }
    } catch {
      // Offline fallback state kept
    }
  }, [getHttpBase]);

  const sendAction = useCallback((action: string, payload: any = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }));
    } else {
      // Fallback to REST POST
      fetch(`${getHttpBase()}/api/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...payload }),
      }).catch(() => {});
    }
  }, [getHttpBase]);

  const setActiveTab = useCallback((tab: NavTab) => {
    setData((prev) => ({ ...prev, activeTab: tab }));
    sendAction("SELECT_NAV", { tab });
  }, [sendAction]);

  // Setup Wizard APIs
  const fetchSetupStatus = useCallback(async () => {
    try {
      const res = await fetch(`${getHttpBase()}/api/setup/status`);
      if (res.ok) {
        return await res.json();
      }
    } catch {
      return null;
    }
    return null;
  }, [getHttpBase]);

  const saveUserName = useCallback(async (userName: string, userDisplayName?: string) => {
    try {
      const res = await fetch(`${getHttpBase()}/api/setup/user-name`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: userName, user_display_name: userDisplayName || userName }),
      });
      if (res.ok) {
        setData((prev) => ({ ...prev, userName }));
        return await res.json();
      }
    } catch (e: any) {
      return { status: "error", message: e.message };
    }
    return { status: "error", message: "Failed to save user name" };
  }, [getHttpBase]);

  const testApiKey = useCallback(async (apiKey: string) => {
    try {
      const res = await fetch(`${getHttpBase()}/api/setup/api-key/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey }),
      });
      return await res.json();
    } catch (e: any) {
      return { status: "error", valid: false, message: `Network error: ${e.message}` };
    }
  }, [getHttpBase]);

  const saveApiKey = useCallback(async (apiKey: string, slot: number = 1) => {
    try {
      const res = await fetch(`${getHttpBase()}/api/setup/api-key/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, slot }),
      });
      const data = await res.json();
      if (res.ok && data.status === "ok") {
        setData((prev) => ({ ...prev, hasApiKey: true }));
      }
      return data;
    } catch (e: any) {
      return { status: "error", message: `Save error: ${e.message}` };
    }
  }, [getHttpBase]);

  const removeApiKey = useCallback(async (slot: number = 1) => {
    try {
      const res = await fetch(`${getHttpBase()}/api/setup/api-key/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot }),
      });
      const data = await res.json();
      if (res.ok && slot === 1) {
        setData((prev) => ({ ...prev, hasApiKey: false }));
      }
      return data;
    } catch (e: any) {
      return { status: "error", message: `Remove error: ${e.message}` };
    }
  }, [getHttpBase]);

  const runDiagnostics = useCallback(async () => {
    try {
      const res = await fetch(`${getHttpBase()}/api/setup/diagnostics`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e: any) {
      return { overall: "FAIL", checks: [], error: e.message };
    }
    return { overall: "FAIL", checks: [], error: "Diagnostics request failed" };
  }, [getHttpBase]);

  const completeSetup = useCallback(async () => {
    try {
      const res = await fetch(`${getHttpBase()}/api/setup/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const json = await res.json();
      if (res.ok) {
        setData((prev) => ({ ...prev, firstRunCompleted: true }));
      }
      return json;
    } catch (e: any) {
      return { status: "error", message: e.message };
    }
  }, [getHttpBase]);

  const resetSetup = useCallback(async () => {
    try {
      const res = await fetch(`${getHttpBase()}/api/setup/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        setData((prev) => ({ ...prev, firstRunCompleted: false }));
      }
      return await res.json();
    } catch (e: any) {
      return { status: "error", message: e.message };
    }
  }, [getHttpBase]);

  const fetchApiUsage = useCallback(async () => {
    try {
      const res = await fetch(`${getHttpBase()}/api/usage`);
      if (res.ok) {
        const json = await res.json();
        setData((prev) => ({ ...prev, apiUsage: json }));
        return json;
      }
    } catch {
      return null;
    }
    return null;
  }, [getHttpBase]);

  const refreshApiUsage = useCallback(async () => {
    try {
      const res = await fetch(`${getHttpBase()}/api/usage/refresh`, {
        method: "POST",
      });
      if (res.ok) {
        const json = await res.json();
        setData((prev) => ({ ...prev, apiUsage: json }));
        return json;
      }
    } catch {
      return null;
    }
    return null;
  }, [getHttpBase]);

  const setCameraMonitoring = useCallback(async (enabled: boolean) => {
    try {
      const res = await fetch(`${getHttpBase()}/api/camera/monitoring`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (res.ok) {
        const json = await res.json();
        setData((prev) => ({ ...prev, cameraMonitoring: json }));
        return json;
      }
    } catch {
      return null;
    }
    return null;
  }, [getHttpBase]);

  const toggleCameraMonitoring = useCallback(async () => {
    try {
      const current = data.cameraMonitoring?.enabled ?? false;
      return await setCameraMonitoring(!current);
    } catch {
      return null;
    }
  }, [data.cameraMonitoring, setCameraMonitoring]);

  const describeSceneNow = useCallback(async () => {
    try {
      const res = await fetch(`${getHttpBase()}/api/camera/describe`, {
        method: "POST",
      });
      if (res.ok) {
        const json = await res.json();
        setData((prev) => ({ ...prev, cameraMonitoring: json }));
        return json;
      }
    } catch {
      return null;
    }
    return null;
  }, [getHttpBase]);

  useEffect(() => {
    fetchStatus();

    let unmounted = false;

    function connectWs() {
      if (unmounted) return;
      try {
        const url = getWsUrl();
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (unmounted) return;
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          if (unmounted) return;
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "STATE_UPDATE" || msg.type === "STATUS") {
              setData((prev) => ({
                ...prev,
                state: msg.state || prev.state,
                pulse: msg.pulse ?? prev.pulse,
                status: { ...prev.status, ...(msg.status || {}) },
                environment: { ...prev.environment, ...(msg.environment || {}) },
                scene: { ...prev.scene, ...(msg.scene || {}) },
                isSleeping: msg.is_sleeping ?? prev.isSleeping,
                firstRunCompleted: msg.first_run_completed ?? prev.firstRunCompleted,
                userName: msg.user_name ?? prev.userName,
                hasApiKey: msg.has_api_key ?? prev.hasApiKey,
                apiUsage: msg.api_usage !== undefined ? msg.api_usage : prev.apiUsage,
                cameraMonitoring: msg.camera_monitoring !== undefined ? msg.camera_monitoring : prev.cameraMonitoring,
              }));
            } else if (msg.type === "TRANSCRIPTION") {
              setData((prev) => ({
                ...prev,
                currentTranscription: msg.text || "",
              }));
            } else if (msg.type === "NEW_MESSAGE") {
              setData((prev) => ({
                ...prev,
                history: [msg.item, ...prev.history.slice(0, 19)],
              }));
            }
          } catch {
            // Ignore parse errors
          }
        };

        ws.onclose = () => {
          if (unmounted) return;
          setIsConnected(false);
          reconnectTimeoutRef.current = window.setTimeout(connectWs, 2000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        if (!unmounted) {
          reconnectTimeoutRef.current = window.setTimeout(connectWs, 3000);
        }
      }
    }

    connectWs();

    // Adaptive status poll: poll frequently (every 3s) only when disconnected;
    // relax to 15s watchdog when live WebSocket is actively streaming.
    let tickCount = 0;
    const interval = window.setInterval(() => {
      tickCount++;
      const isWsOpen = wsRef.current && wsRef.current.readyState === WebSocket.OPEN;
      if (!isWsOpen || tickCount % 5 === 0) {
        fetchStatus();
      }
    }, 3000);

    return () => {
      unmounted = true;
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      clearInterval(interval);
    };
  }, [fetchStatus, getWsUrl]);

  return {
    data,
    isConnected,
    sendAction,
    setActiveTab,
    getHttpBase,
    fetchSetupStatus,
    saveUserName,
    testApiKey,
    saveApiKey,
    removeApiKey,
    runDiagnostics,
    completeSetup,
    resetSetup,
    fetchApiUsage,
    refreshApiUsage,
    apiUsage: data.apiUsage,
    cameraMonitoring: data.cameraMonitoring,
    setCameraMonitoring,
    toggleCameraMonitoring,
    describeSceneNow,
  };
}
