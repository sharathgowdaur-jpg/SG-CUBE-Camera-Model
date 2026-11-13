export type AssistantState =
  | "IDLE"
  | "LISTENING"
  | "USER_SPEAKING"
  | "AI_THINKING"
  | "AI_SPEAKING"
  | "SAFETY_ALERT"
  | "SLEEPING"
  | "PAUSED";

export interface SystemStatus {
  camera: "Active" | "Paused" | "Error";
  fps: number;
  microphone: "Active" | "Muted";
  speaker: "Active" | "Muted";
  ai: "Ready" | "Connecting" | "Offline";
  battery: string;
  network: "Online" | "Degraded" | "Offline";
  gemini_state?: string;
  voice?: string;
}

export interface EnvironmentState {
  people: string;
  room: string;
  lighting: string;
  noise: string;
  safety: "Clear" | "Alert";
}

export interface SceneState {
  people: string;
  left: string;
  center: string;
  right: string;
  path: string;
}

export interface HistoryItem {
  id?: string;
  time: string;
  sender: "user" | "ai" | "system";
  text: string;
}

export interface MemoryItem {
  id?: string;
  key: string;
  value: string;
  category?: string;
  timestamp?: string;
}

export interface DiagnosticCheck {
  id: string;
  name: string;
  status: "PASS" | "WARNING" | "FAIL";
  details: string;
  remedy: string | null;
}

export interface DiagnosticResult {
  overall: "PASS" | "WARNING" | "FAIL";
  timestamp: number;
  checks: DiagnosticCheck[];
}

export interface SetupStatus {
  first_run_completed: boolean;
  user_name: string;
  user_display_name: string;
  has_api_key: boolean;
  masked_key: string;
  keys?: Record<string, { configured: boolean; masked: string }>;
  active_slot?: number;
}

export interface PersonProfile {
  id: string;
  name: string;
  enrollment_count?: number;
  created_at?: string;
}

export type NavTab = "home" | "vision" | "memory" | "history" | "people" | "glasses";

export interface BackendState {
  state: AssistantState;
  pulse: number;
  status: SystemStatus;
  environment: EnvironmentState;
  scene: SceneState;
  history: HistoryItem[];
  memories: MemoryItem[];
  activeTab: NavTab;
  currentTranscription: string;
  activeModel: string;
  isSleeping: boolean;
  firstRunCompleted?: boolean;
  userName?: string;
  hasApiKey?: boolean;
  apiUsage?: ApiUsageData | null;
  cameraMonitoring?: CameraMonitoringState;
}

export interface CameraMonitoringState {
  enabled: boolean;
  intervalSeconds: number;
  status: "IDLE" | "ANALYZING" | "COOLDOWN" | "ERROR";
  lastObservationTime: string | null;
  latestDescription: string;
  error: string | null;
  peopleCount: number;
  objectsCount: number;
  movementDetected: boolean;
}

export interface RateLimits {
  requestsPerMinute: number;
  tokensPerMinute: number;
  requestsPerDay: number;
  tier: string;
}

export interface ApiUsageData {
  provider: string;
  status: "CONNECTED" | "DISCONNECTED" | "ERROR" | "CONNECTING" | "NO_KEY";
  statusMessage: string;
  activeKeySlot: number | null;
  activeKeyMasked: string;
  activeModel: string;
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  sessionTurns: number;
  promptTokens: number;
  candidatesTokens: number;
  totalTokens: number;
  quotaLimit: number | null;
  remainingQuota: number | null;
  quotaDisplay: string;
  usagePercentage: number | null;
  usageScope: string;
  rateLimits?: RateLimits;
  lastSyncTime: string | null;
  lastError?: string | null;
}
