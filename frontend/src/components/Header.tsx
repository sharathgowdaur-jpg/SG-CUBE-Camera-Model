import React from "react";
import {
  Home,
  Eye,
  Database,
  Clock,
  Users,
  Glasses,
  Activity,
  Settings,
  Shield,
} from "lucide-react";
import type { NavTab, AssistantState, ApiUsageData } from "@/types";
import { ApiUsageIndicator } from "@/components/ApiUsageIndicator";

interface HeaderProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  state: AssistantState;
  isConnected: boolean;
  apiUsage?: ApiUsageData | null;
  onRefreshApiUsage?: () => Promise<any>;
  onOpenSettings?: () => void;
  onOpenVault?: () => void;
}

const TABS: { id: NavTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "vision", label: "Vision", icon: Eye },
  { id: "memory", label: "Memory", icon: Database },
  { id: "history", label: "History", icon: Clock },
  { id: "people", label: "People", icon: Users },
  { id: "glasses", label: "Meta Glass", icon: Glasses },
];

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onSelectTab,
  state,
  isConnected,
  apiUsage,
  onRefreshApiUsage,
  onOpenSettings,
  onOpenVault,
}) => {
  return (
    <header className="w-full h-16 px-4 py-2 flex items-center justify-between border-b border-cyan-500/20 bg-[#060B1A]/80 backdrop-blur-md z-30 select-none">
      {/* Brand Identity */}
      <div className="flex items-center gap-3">
        {/* Futuristic 3D mini cube glyph */}
        <div className="w-10 h-10 rounded-md border border-cyan-400/40 bg-cyan-950/40 flex items-center justify-center shadow-[0_0_12px_rgba(34,211,238,0.25)]">
          <div className="w-5 h-5 border border-cyan-300 rotate-45 flex items-center justify-center">
            <div className="w-2.5 h-2.5 bg-cyan-400" />
          </div>
        </div>

        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold tracking-wider text-white">SG CUBE</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-400/30 text-cyan-300 font-mono">
              v2.5.0
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <span className="text-text-secondary">Personal AI Companion</span>
            <span>•</span>
            <span className="text-cyan-400">Seeing</span>
            <span className="text-cyan-300">•</span>
            <span className="text-cyan-400">Understanding</span>
            <span className="text-cyan-300">•</span>
            <span className="text-cyan-400">Helping</span>
          </div>
        </div>
      </div>

      {/* Navigation Pills */}
      <nav className="flex items-center gap-1 bg-black/40 p-1 rounded-xl border border-cyan-500/20 shadow-inner">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              className={`relative px-4 py-1.5 rounded-lg flex items-center gap-2 transition-all duration-200 text-sm font-medium ${
                isActive
                  ? "bg-[#0A1226] text-white border border-cyan-400/50 shadow-[0_0_12px_rgba(34,211,238,0.2)]"
                  : "text-text-muted hover:text-cyan-200 hover:bg-cyan-950/20 border border-transparent"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-cyan-400" : "text-text-muted"}`} />
              <span>{tab.label}</span>
              {isActive && (
                <div className="absolute bottom-0 left-3 right-3 h-[2px] bg-cyan-400 shadow-[0_0_8px_#22D3EE] rounded-full" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Status Pill & Settings */}
      <div className="flex items-center gap-2.5">
        {/* Real API Usage & Quota Indicator */}
        <ApiUsageIndicator
          apiUsage={apiUsage}
          onRefresh={onRefreshApiUsage || (async () => {})}
          onOpenSettings={onOpenSettings}
        />

        {/* Status Pill */}
        <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-[#0A1226] border border-cyan-500/30 shadow-[0_0_10px_rgba(34,211,238,0.1)]">
          <Activity className="w-4 h-4 text-cyan-400 animate-pulse" />
          <span
            className={`w-2 h-2 rounded-full ${
              isConnected ? "bg-cyan-400 shadow-[0_0_8px_#22D3EE]" : "bg-amber-400 shadow-[0_0_8px_#F59E0B]"
            }`}
          />
          <span className="text-xs font-mono font-medium text-white tracking-wide">
            {state === "SAFETY_ALERT" ? "ALERT" : state}
          </span>
        </div>

        {/* Secure Password Vault button */}
        <button
          onClick={onOpenVault}
          title="Secure Password Vault (AES-256-GCM)"
          className="w-9 h-9 rounded-lg border border-cyan-500/30 bg-[#0A1226] flex items-center justify-center text-text-muted hover:text-cyan-300 hover:border-cyan-400 transition-colors shadow-sm"
        >
          <Shield className="w-4 h-4" />
        </button>

        {/* Settings button */}
        <button
          onClick={onOpenSettings}
          title="Settings & System Tools"
          className="w-9 h-9 rounded-lg border border-cyan-500/30 bg-[#0A1226] flex items-center justify-center text-text-muted hover:text-cyan-300 hover:border-cyan-400 transition-colors shadow-sm"
        >
          <Settings className="w-4 h-4 hover:rotate-45 transition-transform duration-300" />
        </button>
      </div>
    </header>
  );
};
