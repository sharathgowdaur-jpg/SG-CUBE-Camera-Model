import React, { useState } from "react";
import { Mic, MicOff, Camera, VideoOff, Square, Power, Send, Radio } from "lucide-react";
import type { SystemStatus, AssistantState, CameraMonitoringState } from "@/types";

interface QuickActionsProps {
  status: SystemStatus;
  state: AssistantState;
  cameraMonitoring?: CameraMonitoringState;
  onSendAction: (action: string, payload?: any) => void;
  onToggleMonitoring?: () => void;
}

export const QuickActions: React.FC<QuickActionsProps> = ({
  status,
  state,
  cameraMonitoring,
  onSendAction,
  onToggleMonitoring,
}) => {
  const [inputText, setInputText] = useState("");

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSendAction("SEND_TEXT", { text: inputText });
    setInputText("");
  };

  const isSleeping = state === "SLEEPING";
  const isMonitoringOn = Boolean(cameraMonitoring?.enabled);

  return (
    <div className="w-full flex items-center justify-between gap-3 px-4 py-1.5 bg-[#060B1A]/90 border-t border-cyan-500/20 backdrop-blur-md select-none z-20">
      {/* Control Buttons */}
      <div className="flex items-center gap-2">
        {/* Wake / Sleep */}
        <button
          onClick={() => onSendAction(isSleeping ? "WAKE" : "SLEEP")}
          className={`px-3 py-1 rounded-md text-xs font-mono font-medium flex items-center gap-1.5 transition-all shadow-sm ${
            isSleeping
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400 hover:bg-cyan-500/30"
              : "bg-black/40 text-text-muted border border-cyan-500/20 hover:text-white hover:border-cyan-400"
          }`}
          title={isSleeping ? "Wake Assistant" : "Sleep Mode"}
        >
          <Power className="w-3.5 h-3.5" />
          <span>{isSleeping ? "WAKE" : "SLEEP"}</span>
        </button>

        {/* Mic Toggle */}
        <button
          onClick={() => onSendAction(status.microphone === "Active" ? "STOP_MIC" : "START_MIC")}
          className="px-3 py-1 rounded-md text-xs font-mono text-text-muted border border-cyan-500/20 bg-black/40 hover:text-cyan-300 hover:border-cyan-400 flex items-center gap-1.5 transition-colors"
          title="Toggle Microphone"
        >
          {status.microphone === "Active" ? (
            <>
              <Mic className="w-3.5 h-3.5 text-cyan-400" />
              <span>MIC ACTIVE</span>
            </>
          ) : (
            <>
              <MicOff className="w-3.5 h-3.5 text-red-400" />
              <span>MIC MUTED</span>
            </>
          )}
        </button>

        {/* Camera Toggle */}
        <button
          onClick={() => onSendAction("TOGGLE_CAMERA")}
          className="px-3 py-1 rounded-md text-xs font-mono text-text-muted border border-cyan-500/20 bg-black/40 hover:text-cyan-300 hover:border-cyan-400 flex items-center gap-1.5 transition-colors"
          title="Toggle Camera"
        >
          {status.camera === "Active" ? (
            <>
              <Camera className="w-3.5 h-3.5 text-cyan-400" />
              <span>CAM ACTIVE</span>
            </>
          ) : (
            <>
              <VideoOff className="w-3.5 h-3.5 text-amber-400" />
              <span>CAM PAUSED</span>
            </>
          )}
        </button>

        {/* Camera Monitoring Toggle */}
        <button
          onClick={onToggleMonitoring || (() => onSendAction("TOGGLE_CAMERA_MONITORING"))}
          className={`px-3 py-1 rounded-md text-xs font-mono flex items-center gap-1.5 transition-all shadow-sm ${
            isMonitoringOn
              ? "bg-emerald-950/70 border border-emerald-400 text-emerald-300 shadow-[0_0_8px_rgba(16,185,129,0.3)] hover:bg-emerald-900/80"
              : "border border-cyan-500/20 bg-black/40 text-text-muted hover:text-cyan-300 hover:border-cyan-400"
          }`}
          title="Toggle 10s Automatic Camera Monitoring"
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isMonitoringOn ? "bg-emerald-400 animate-pulse shadow-[0_0_6px_#10B981]" : "bg-zinc-600"
            }`}
          />
          <span>MONITOR: {isMonitoringOn ? "ON" : "OFF"}</span>
        </button>

        {/* Emergency STOP */}
        <button
          onClick={() => onSendAction("STOP")}
          className="px-3 py-1 rounded-md text-xs font-mono font-bold text-red-400 border border-red-500/40 bg-red-950/20 hover:bg-red-900/40 flex items-center gap-1.5 transition-colors shadow-[0_0_8px_rgba(239,68,68,0.2)]"
          title="Emergency Stop / Cancel Action"
        >
          <Square className="w-3.5 h-3.5 fill-red-400 text-red-400" />
          <span>STOP</span>
        </button>
      </div>

      {/* Quick Text Command Input */}
      <form onSubmit={handleSend} className="flex-1 max-w-md flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type a command or question..."
            className="w-full px-3 py-1 rounded-md bg-black/50 border border-cyan-500/20 text-xs text-white placeholder-text-muted focus:outline-none focus:border-cyan-400 transition-colors font-mono"
          />
        </div>
        <button
          type="submit"
          className="px-3 py-1 rounded-md bg-cyan-500/20 text-cyan-300 border border-cyan-400/50 hover:bg-cyan-500/30 flex items-center gap-1 text-xs font-mono transition-colors"
        >
          <Send className="w-3 h-3" />
          <span>SEND</span>
        </button>
      </form>
    </div>
  );
};
