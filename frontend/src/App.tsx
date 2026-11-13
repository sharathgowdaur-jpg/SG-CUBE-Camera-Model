import React, { useState, useEffect } from "react";
import { Header } from "@/components/Header";
import { CameraPanel } from "@/components/CameraPanel";
import { EnvironmentPanel } from "@/components/EnvironmentPanel";
import { ScenePanel } from "@/components/ScenePanel";
import { HistoryPanel } from "@/components/HistoryPanel";
import { StatusPanel } from "@/components/StatusPanel";
import { CubeVisualization } from "@/components/CubeVisualization";
import { BottomBar } from "@/components/BottomBar";
import { QuickActions } from "@/components/QuickActions";
import { AppBackground } from "@/components/AppBackground";
import { VisionDetailModal } from "@/components/VisionDetailModal";
import { MemoryDetailModal } from "@/components/MemoryDetailModal";
import { SettingsModal } from "@/components/SettingsModal";
import { SetupWizardModal } from "@/components/SetupWizardModal";
import { DiagnosticsModal } from "@/components/DiagnosticsModal";
import { PeopleModal } from "@/components/PeopleModal";
import { GlassesModal } from "@/components/GlassesModal";
import { HistoryModal } from "@/components/HistoryModal";
import { VaultModal } from "@/components/VaultModal";
import { useBackend } from "@/hooks/useBackend";

export default function App() {
  const {
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
    refreshApiUsage,
    apiUsage,
    cameraMonitoring,
    toggleCameraMonitoring,
    describeSceneNow,
  } = useBackend();

  const [isVisionModalOpen, setIsVisionModalOpen] = useState(false);
  const [isMemoryModalOpen, setIsMemoryModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isSetupWizardOpen, setIsSetupWizardOpen] = useState(false);
  const [isDiagnosticsModalOpen, setIsDiagnosticsModalOpen] = useState(false);
  const [isPeopleModalOpen, setIsPeopleModalOpen] = useState(false);
  const [isGlassesModalOpen, setIsGlassesModalOpen] = useState(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);
  const [isVaultModalOpen, setIsVaultModalOpen] = useState(false);

  // Auto-detect fresh first-run installation
  useEffect(() => {
    if (data.firstRunCompleted === false) {
      setIsSetupWizardOpen(true);
    }
  }, [data.firstRunCompleted]);

  const handleNavSelect = (tab: string) => {
    setActiveTab(tab as any);
    if (tab === "vision") setIsVisionModalOpen(true);
    if (tab === "memory") setIsMemoryModalOpen(true);
    if (tab === "history") setIsHistoryModalOpen(true);
    if (tab === "people") setIsPeopleModalOpen(true);
    if (tab === "glasses") setIsGlassesModalOpen(true);
  };

  const handleFinishSetup = async () => {
    await completeSetup();
    setIsSetupWizardOpen(false);
  };

  return (
    <div className="relative w-screen h-screen flex flex-col bg-[#000000] text-white overflow-hidden select-none">
      {/* Dynamic Contextual Background Atmosphere */}
      <AppBackground activeTab={data.activeTab} />

      {/* Header Bar */}
      <Header
        activeTab={data.activeTab}
        onSelectTab={handleNavSelect}
        state={data.state}
        isConnected={isConnected}
        apiUsage={apiUsage}
        onRefreshApiUsage={refreshApiUsage}
        onOpenSettings={() => {
          setIsSettingsModalOpen(true);
          sendAction("OPEN_SETTINGS");
        }}
        onOpenVault={() => setIsVaultModalOpen(true)}
      />

      {/* Main Responsive Dashboard Grid */}
      <main className="flex-1 w-full p-2.5 flex flex-col gap-2.5 overflow-hidden z-10">
        {/* Upper Stage (Camera Hero + Environment & Scene) */}
        <section className="flex-1 min-h-0 flex gap-2.5">
          {/* Left: Environment Panel (~24% width) */}
          <div className="w-[24%] min-w-[220px] max-w-[340px] h-full">
            <EnvironmentPanel data={data.environment} />
          </div>

          {/* Center: Camera Hero Panel (~52% width) */}
          <div className="flex-1 h-full">
            <CameraPanel
              cameraActive={data.status.camera === "Active"}
              fps={data.status.fps}
              onToggleCamera={() => sendAction("TOGGLE_CAMERA")}
            />
          </div>

          {/* Right: Scene Understanding Panel (~24% width) */}
          <div className="w-[24%] min-w-[220px] max-w-[340px] h-full">
            <ScenePanel
              data={data.scene}
              monitoring={cameraMonitoring}
              onToggleMonitoring={toggleCameraMonitoring}
              onDescribeNow={describeSceneNow}
            />
          </div>
        </section>

        {/* Lower Stage (History, 3D Cyan SG CUBE Centerpiece, Status) */}
        <section className="h-[44%] min-h-[200px] max-h-[380px] flex gap-2.5">
          {/* Lower Left: Recent History (35%) */}
          <div className="w-[35%] h-full">
            <HistoryPanel
              items={data.history}
              onViewAll={() => setIsHistoryModalOpen(true)}
            />
          </div>

          {/* Lower Center: 3D Cyan SG CUBE Centerpiece (30%) */}
          <div className="w-[30%] h-full relative rounded-md bg-[#060B1A]/40 border border-cyan-500/20 backdrop-blur-md flex items-center justify-center overflow-hidden shadow-inner">
            <CubeVisualization state={data.state} pulse={data.pulse} />
          </div>

          {/* Lower Right: System Hardware & Network Status (35%) */}
          <div className="w-[35%] h-full">
            <StatusPanel
              status={data.status}
              onOpenDetails={() => setIsDiagnosticsModalOpen(true)}
            />
          </div>
        </section>
      </main>

      {/* Quick Action & Controls Bar */}
      <QuickActions
        status={data.status}
        state={data.state}
        cameraMonitoring={cameraMonitoring}
        onSendAction={sendAction}
        onToggleMonitoring={toggleCameraMonitoring}
      />

      {/* Footer Bar */}
      <BottomBar currentTranscription={data.currentTranscription} />

      {/* Deep Drilldown Modals */}
      <VisionDetailModal
        isOpen={isVisionModalOpen}
        onClose={() => {
          setIsVisionModalOpen(false);
          setActiveTab("home");
        }}
        env={data.environment}
        scene={data.scene}
      />

      <MemoryDetailModal
        isOpen={isMemoryModalOpen}
        onClose={() => {
          setIsMemoryModalOpen(false);
          setActiveTab("home");
        }}
        memories={data.memories}
      />

      <HistoryModal
        isOpen={isHistoryModalOpen}
        onClose={() => {
          setIsHistoryModalOpen(false);
          setActiveTab("home");
        }}
        getHttpBase={getHttpBase}
      />

      <PeopleModal
        isOpen={isPeopleModalOpen}
        onClose={() => {
          setIsPeopleModalOpen(false);
          setActiveTab("home");
        }}
        getHttpBase={getHttpBase}
      />

      <GlassesModal
        isOpen={isGlassesModalOpen}
        onClose={() => {
          setIsGlassesModalOpen(false);
          setActiveTab("home");
        }}
        getHttpBase={getHttpBase}
      />

      <DiagnosticsModal
        isOpen={isDiagnosticsModalOpen}
        onClose={() => setIsDiagnosticsModalOpen(false)}
        runDiagnostics={runDiagnostics}
      />

      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        onSendAction={sendAction}
        fetchSetupStatus={fetchSetupStatus}
        testApiKey={testApiKey}
        saveApiKey={saveApiKey}
        removeApiKey={removeApiKey}
        onOpenDiagnostics={() => setIsDiagnosticsModalOpen(true)}
        onOpenSetupWizard={() => setIsSetupWizardOpen(true)}
        onOpenVault={() => setIsVaultModalOpen(true)}
      />

      {/* First-Run Setup Wizard */}
      <SetupWizardModal
        isOpen={isSetupWizardOpen}
        onClose={() => setIsSetupWizardOpen(false)}
        onComplete={handleFinishSetup}
        fetchSetupStatus={fetchSetupStatus}
        saveUserName={saveUserName}
        testApiKey={testApiKey}
        saveApiKey={saveApiKey}
        removeApiKey={removeApiKey}
        runDiagnostics={runDiagnostics}
      />

      {/* Secure Password Vault Modal */}
      <VaultModal
        isOpen={isVaultModalOpen}
        onClose={() => setIsVaultModalOpen(false)}
        getHttpBase={getHttpBase}
      />
    </div>
  );
}
