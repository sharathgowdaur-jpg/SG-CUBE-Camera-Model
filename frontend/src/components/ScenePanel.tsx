import React from "react";
import { Box, ArrowLeft, Target, ArrowRight, Navigation, Eye, Radio, Sparkles } from "lucide-react";
import type { SceneState, CameraMonitoringState } from "@/types";

interface ScenePanelProps {
  data: SceneState;
  monitoring?: CameraMonitoringState;
  onToggleMonitoring?: () => void;
  onDescribeNow?: () => void;
}

export const ScenePanel: React.FC<ScenePanelProps> = ({
  data,
  monitoring,
  onToggleMonitoring,
  onDescribeNow,
}) => {
  const isMonitoringOn = Boolean(monitoring?.enabled);
  const status = monitoring?.status || "IDLE";
  const isAnalyzing = status === "ANALYZING";

  return (
    <div className="hud-panel p-3 flex flex-col justify-between h-full select-none gap-2">
      {/* Header with Title and Camera Monitoring Toggle */}
      <div className="flex items-center justify-between pb-2 border-b border-cyan-500/15">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#22D3EE]" />
          <h2 className="hud-heading text-xs tracking-wider">SCENE</h2>
        </div>

        {/* Small, clear control: CAMERA MONITORING: OFF / ON */}
        <button
          onClick={onToggleMonitoring}
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-[10px] font-mono font-bold transition-all shadow-sm ${
            isMonitoringOn
              ? "bg-emerald-950/70 border-emerald-400/80 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.3)] hover:bg-emerald-900/80"
              : "bg-black/50 border-cyan-500/20 text-text-muted hover:text-white hover:border-cyan-400/40"
          }`}
          title={isMonitoringOn ? "Camera Monitoring: Active (10s interval) — Click to Turn OFF" : "Camera Monitoring: Inactive — Click to Turn ON"}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isMonitoringOn ? "bg-emerald-400 animate-pulse shadow-[0_0_6px_#10B981]" : "bg-zinc-500"
            }`}
          />
          <span>CAMERA MONITORING: {isMonitoringOn ? "ON" : "OFF"}</span>
        </button>
      </div>

      {/* Monitoring Status & Live Description Banner when ON */}
      {isMonitoringOn && (
        <div className="p-2 rounded bg-black/40 border border-emerald-500/30 text-[10px] font-mono flex flex-col gap-1 shadow-inner">
          <div className="flex items-center justify-between text-text-muted">
            <div className="flex items-center gap-1.5">
              <Radio className={`w-3 h-3 ${isAnalyzing ? "text-emerald-400 animate-spin" : "text-emerald-400"}`} />
              <span className="text-emerald-300 font-bold uppercase">{status}</span>
              <span className="text-zinc-500">•</span>
              <span>10s interval</span>
            </div>
            {monitoring?.lastObservationTime && (
              <span className="text-text-secondary">{monitoring.lastObservationTime}</span>
            )}
          </div>
          {monitoring?.latestDescription && (
            <p className="text-white/90 text-[10px] font-sans italic line-clamp-2 leading-tight">
              "{monitoring.latestDescription}"
            </p>
          )}
        </div>
      )}

      {/* Spatial Entities Rows */}
      <div className="flex flex-col gap-1.5 my-auto py-0.5">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-text-muted">
            <Box className="w-3.5 h-3.5 text-cyan-400/80" />
            <span className="text-text-secondary">People</span>
          </div>
          <span className="font-mono text-white font-medium">{data.people || "0 | Objects: 0"}</span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-text-muted">
            <ArrowLeft className="w-3.5 h-3.5 text-cyan-400/80" />
            <span className="text-text-secondary">Left</span>
          </div>
          <span className="font-mono text-white font-medium">{data.left || "None"}</span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-text-muted">
            <Target className="w-3.5 h-3.5 text-cyan-400/80" />
            <span className="text-text-secondary">Center</span>
          </div>
          <span className="font-mono text-white font-medium">{data.center || "None"}</span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-text-muted">
            <ArrowRight className="w-3.5 h-3.5 text-cyan-400/80" />
            <span className="text-text-secondary">Right</span>
          </div>
          <span className="font-mono text-white font-medium">{data.right || "None"}</span>
        </div>

        <div className="flex items-center justify-between text-xs pt-1 border-t border-cyan-500/10">
          <div className="flex items-center gap-2 text-text-muted">
            <Navigation className="w-3.5 h-3.5 text-cyan-400/80" />
            <span className="text-text-secondary">Path</span>
          </div>
          <span
            className={`font-mono font-semibold ${
              data.path === "Clear" ? "text-cyan-400" : "text-amber-400"
            }`}
          >
            {data.path || "Clear"}
          </span>
        </div>
      </div>

      {/* Manual Observation / Describe Scene Trigger */}
      {onDescribeNow && (
        <div className="pt-1.5 border-t border-cyan-500/15 flex items-center justify-between text-[11px]">
          <span className="text-[10px] text-text-muted font-mono">Manual Vision</span>
          <button
            onClick={onDescribeNow}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#0A1226] border border-cyan-500/30 text-cyan-300 hover:text-white hover:border-cyan-400 transition-colors shadow-sm font-mono text-[10px]"
            title="Perform Immediate Scene Analysis"
          >
            <Sparkles className="w-3 h-3 text-cyan-400" />
            <span>Describe Now</span>
          </button>
        </div>
      )}
    </div>
  );
};
