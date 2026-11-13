import React, { useState, useEffect, useRef } from "react";
import {
  Cloud,
  RefreshCw,
  Zap,
  AlertCircle,
  CheckCircle2,
  X,
  Key,
  Database,
  Sliders,
  Info,
} from "lucide-react";
import type { ApiUsageData } from "@/types";

interface ApiUsageIndicatorProps {
  apiUsage?: ApiUsageData | null;
  onRefresh: () => Promise<any>;
  onOpenSettings?: () => void;
  className?: string;
}

export const ApiUsageIndicator: React.FC<ApiUsageIndicatorProps> = ({
  apiUsage,
  onRefresh,
  onOpenSettings,
  className = "",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleRefresh = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  const status = apiUsage?.status || "DISCONNECTED";
  const isConnected = status === "CONNECTED";
  const isError = status === "ERROR" || status === "NO_KEY";
  const totalRequests = apiUsage?.totalRequests ?? 0;
  const totalTokens = apiUsage?.totalTokens ?? 0;
  const promptTokens = apiUsage?.promptTokens ?? 0;
  const candidateTokens = apiUsage?.candidatesTokens ?? 0;
  const successfulRequests = apiUsage?.successfulRequests ?? 0;
  const failedRequests = apiUsage?.failedRequests ?? 0;
  const sessionTurns = apiUsage?.sessionTurns ?? 0;

  // Status styling
  let statusColorClass = "text-amber-400 bg-amber-400/10 border-amber-400/30";
  let dotColorClass = "bg-amber-400 shadow-[0_0_8px_#F59E0B]";
  if (isConnected) {
    statusColorClass = "text-cyan-300 bg-cyan-500/10 border-cyan-400/30";
    dotColorClass = "bg-cyan-400 shadow-[0_0_8px_#22D3EE]";
  } else if (isError) {
    statusColorClass = "text-red-400 bg-red-500/10 border-red-400/30";
    dotColorClass = "bg-red-400 shadow-[0_0_8px_#EF4444]";
  }

  // Quota & remaining calculation
  const hasReliableQuota =
    typeof apiUsage?.quotaLimit === "number" &&
    typeof apiUsage?.remainingQuota === "number" &&
    apiUsage.quotaLimit > 0;

  const usagePercent = hasReliableQuota
    ? Math.min(
        100,
        Math.max(
          0,
          Math.round(((apiUsage!.quotaLimit! - apiUsage!.remainingQuota!) / apiUsage!.quotaLimit!) * 100)
        )
      )
    : null;

  return (
    <div className={`relative inline-block ${className}`} ref={popoverRef}>
      {/* Compact Header Pill Trigger */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-2 px-2.5 py-1.5 rounded-full bg-[#0A1226] border border-cyan-500/30 hover:border-cyan-400/60 transition-all duration-200 shadow-[0_0_10px_rgba(34,211,238,0.1)] group text-xs"
        title="API Usage & Quota Monitor (Click for breakdown)"
      >
        <Cloud className="w-3.5 h-3.5 text-cyan-400 group-hover:scale-110 transition-transform" />

        {/* Status Dot */}
        <span className={`w-2 h-2 rounded-full ${dotColorClass}`} />

        {/* Status & Short Summary */}
        <span className="font-mono font-medium text-white tracking-wide">
          API: {status}
        </span>

        {/* Reqs / Tokens Quick Count (desktop/tablet) */}
        <div className="hidden sm:flex items-center gap-1.5 pl-1 text-[11px] font-mono text-cyan-300/80 border-l border-cyan-500/20">
          <span>{totalRequests} req</span>
          <span className="text-cyan-500/40">•</span>
          <span>{totalTokens.toLocaleString()} tok</span>
        </div>

        {/* Small Refresh Trigger inside pill */}
        <button
          onClick={handleRefresh}
          className="ml-0.5 p-0.5 text-text-muted hover:text-cyan-300 transition-colors"
          title="Refresh API Status & Quota"
        >
          <RefreshCw className={`w-3 h-3 ${isRefreshing ? "animate-spin text-cyan-400" : ""}`} />
        </button>
      </button>

      {/* Expanded Cyber Popover Card */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-88 max-w-[90vw] z-50 rounded-xl bg-[#070D1E]/95 border border-cyan-500/40 shadow-[0_0_28px_rgba(34,211,238,0.25)] backdrop-blur-xl p-4 flex flex-col gap-3 text-white animate-in fade-in zoom-in-95 duration-150">
          {/* Popover Header */}
          <div className="flex items-center justify-between pb-2 border-b border-cyan-500/20">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-cyan-400" />
              <div>
                <h3 className="font-bold text-xs tracking-wider text-cyan-200 uppercase">
                  Gemini API Usage & Quota
                </h3>
                <p className="text-[10px] text-text-muted font-mono">
                  {apiUsage?.provider || "Google Gemini"} • {apiUsage?.activeModel || "gemini-3.1-flash-live-preview"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={handleRefresh}
                className="p-1 rounded-md text-text-muted hover:text-cyan-300 hover:bg-cyan-500/10 transition-colors"
                title="Refresh with Gemini API"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-cyan-400" : ""}`} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded-md text-text-muted hover:text-white hover:bg-white/10 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Connection Status & Key Info */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-black/40 border border-cyan-500/20 text-xs">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] uppercase border ${statusColorClass}`}>
                {status}
              </span>
              <span className="text-[11px] text-text-secondary truncate max-w-[130px]">
                {apiUsage?.statusMessage || (isConnected ? "Connected to Gemini" : "Disconnected")}
              </span>
            </div>

            {apiUsage?.activeKeyMasked ? (
              <div className="flex items-center gap-1 text-[11px] font-mono text-cyan-300/90 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-500/20">
                <Key className="w-3 h-3 text-cyan-400" />
                <span>Slot {apiUsage.activeKeySlot || 1}:</span>
                <span className="text-white">{apiUsage.activeKeyMasked.slice(-6)}</span>
              </div>
            ) : (
              <span className="text-[10px] text-amber-300 font-mono">No Key Loaded</span>
            )}
          </div>

          {/* Metrics Grid: Requests & Turns */}
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 rounded-lg bg-[#0A1226] border border-cyan-500/20 flex flex-col">
              <span className="text-[10px] text-text-muted font-mono uppercase">Requests</span>
              <span className="text-sm font-bold font-mono text-white mt-0.5">
                {totalRequests}
              </span>
              <span className="text-[9px] text-emerald-400 font-mono">
                {successfulRequests} ok / {failedRequests} err
              </span>
            </div>

            <div className="p-2 rounded-lg bg-[#0A1226] border border-cyan-500/20 flex flex-col">
              <span className="text-[10px] text-text-muted font-mono uppercase">Total Tokens</span>
              <span className="text-sm font-bold font-mono text-cyan-300 mt-0.5">
                {totalTokens.toLocaleString()}
              </span>
              <span className="text-[9px] text-text-muted font-mono truncate">
                {promptTokens} in / {candidateTokens} out
              </span>
            </div>

            <div className="p-2 rounded-lg bg-[#0A1226] border border-cyan-500/20 flex flex-col">
              <span className="text-[10px] text-text-muted font-mono uppercase">Live Turns</span>
              <span className="text-sm font-bold font-mono text-white mt-0.5">
                {sessionTurns}
              </span>
              <span className="text-[9px] text-text-muted font-mono">
                Audio/Video
              </span>
            </div>
          </div>

          {/* Quota & Remaining Section */}
          <div className="p-2.5 rounded-lg bg-black/40 border border-cyan-500/20 flex flex-col gap-1.5 text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-[11px] font-semibold text-text-secondary uppercase">
                  Account Quota & Limits
                </span>
              </div>

              {hasReliableQuota && (
                <span className="text-[11px] font-mono font-bold text-cyan-300">
                  {usagePercent}% Used
                </span>
              )}
            </div>

            {/* Quota Value / Limitation Message */}
            <div className="flex items-center justify-between font-mono text-[11px] pt-1">
              <span className="text-text-muted">Quota Status:</span>
              <span className={hasReliableQuota ? "text-white" : "text-amber-300/90 italic text-[11px]"}>
                {apiUsage?.quotaDisplay || "Quota unavailable from provider"}
              </span>
            </div>

            {hasReliableQuota ? (
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden mt-1">
                <div
                  className="bg-cyan-400 h-full rounded-full transition-all duration-300 shadow-[0_0_6px_#22D3EE]"
                  style={{ width: `${usagePercent}%` }}
                />
              </div>
            ) : (
              <div className="flex items-start gap-1.5 mt-1 p-1.5 rounded bg-cyan-950/20 border border-cyan-500/10 text-[10px] text-text-muted leading-tight">
                <Info className="w-3 h-3 text-cyan-400 shrink-0 mt-0.5" />
                <span>
                  Google Gemini Developer API keys do not expose account balances or remaining billing credit via API. Displaying verified app-level consumption.
                </span>
              </div>
            )}

            {/* Reference Rate Limits for Gemini Free Tier */}
            <div className="mt-1 pt-1.5 border-t border-cyan-500/10 flex items-center justify-between text-[10px] font-mono text-text-muted">
              <span>Rate Limits (Free):</span>
              <span className="text-cyan-300/80">15 RPM • 1M TPM • 1,500 RPD</span>
            </div>
          </div>

          {/* Footer: Last Sync & Settings Link */}
          <div className="flex items-center justify-between pt-1 border-t border-cyan-500/15 text-[10px] font-mono text-text-muted">
            <span>
              Synced: {apiUsage?.lastSyncTime ? apiUsage.lastSyncTime.split(" ")[1] || apiUsage.lastSyncTime : "Never"}
            </span>

            {onOpenSettings && (
              <button
                onClick={() => {
                  setIsOpen(false);
                  onOpenSettings();
                }}
                className="flex items-center gap-1 text-cyan-400 hover:text-cyan-200 transition-colors"
              >
                <Sliders className="w-3 h-3" />
                <span>Manage Keys</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
