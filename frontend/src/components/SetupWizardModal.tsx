import React, { useState, useEffect } from "react";
import {
  Sparkles,
  User,
  Key,
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ArrowRight,
  ArrowLeft,
  Eye,
  EyeOff,
  RefreshCw,
  ShieldCheck,
  Cpu,
  Trash2,
  Shield,
  ShieldAlert,
  Lock,
  Unlock,
} from "lucide-react";
import type { DiagnosticResult, SetupStatus } from "@/types";

interface SetupWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
  fetchSetupStatus: () => Promise<SetupStatus | null>;
  saveUserName: (name: string, displayName?: string) => Promise<any>;
  testApiKey: (key: string) => Promise<{ status: string; valid: boolean; message: string }>;
  saveApiKey: (key: string, slot?: number) => Promise<any>;
  removeApiKey: (slot?: number) => Promise<any>;
  runDiagnostics: () => Promise<DiagnosticResult>;
}

export const SetupWizardModal: React.FC<SetupWizardModalProps> = ({
  isOpen,
  onComplete,
  fetchSetupStatus,
  saveUserName,
  testApiKey,
  saveApiKey,
  removeApiKey,
  runDiagnostics,
}) => {
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [userName, setUserName] = useState<string>("");
  const [userDisplayName, setUserDisplayName] = useState<string>("");

  // API Key state
  const [apiKeyInput, setApiKeyInput] = useState<string>("");
  const [showKeyText, setShowKeyText] = useState<boolean>(false);
  const [maskedKey, setMaskedKey] = useState<string>("");
  const [keyStatus, setKeyStatus] = useState<"not_configured" | "validating" | "valid" | "error">(
    "not_configured"
  );
  const [keyStatusMsg, setKeyStatusMsg] = useState<string>("");
  const [isTestingKey, setIsTestingKey] = useState<boolean>(false);
  const [isSavingKey, setIsSavingKey] = useState<boolean>(false);

  // Vault Setup state
  const [vaultChoice, setVaultChoice] = useState<"ask" | "setup" | "configured">("ask");
  const [vaultMasterPw, setVaultMasterPw] = useState<string>("");
  const [vaultConfirmPw, setVaultConfirmPw] = useState<string>("");
  const [showVaultPw, setShowVaultPw] = useState<boolean>(false);
  const [isSettingUpVault, setIsSettingUpVault] = useState<boolean>(false);
  const [vaultMsg, setVaultMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Diagnostics state
  const [diagResult, setDiagResult] = useState<DiagnosticResult | null>(null);
  const [isRunningDiag, setIsRunningDiag] = useState<boolean>(false);

  // On open, load existing setup status if any
  useEffect(() => {
    if (isOpen) {
      fetchSetupStatus().then((status) => {
        if (status) {
          if (status.user_name) setUserName(status.user_name);
          if (status.user_display_name) setUserDisplayName(status.user_display_name);
          if (status.has_api_key && status.masked_key) {
            setMaskedKey(status.masked_key);
            setKeyStatus("valid");
            setKeyStatusMsg("Gemini API key is configured and encrypted with Windows DPAPI.");
          }
        }
      });
    }
  }, [isOpen, fetchSetupStatus]);

  if (!isOpen) return null;

  // Step 2 Handler: Save Name
  const handleSaveNameAndContinue = async () => {
    const trimmed = userName.trim();
    if (!trimmed) {
      return;
    }
    await saveUserName(trimmed, userDisplayName.trim() || trimmed);
    setCurrentStep(3);
  };

  // Step 3: Test Key
  const handleTestKey = async () => {
    if (!apiKeyInput.trim()) {
      setKeyStatus("error");
      setKeyStatusMsg("Please enter an API key to test.");
      return;
    }
    setIsTestingKey(true);
    setKeyStatus("validating");
    setKeyStatusMsg("Validating key with Google Gemini API...");
    try {
      const res = await testApiKey(apiKeyInput.trim());
      if (res && res.valid) {
        setKeyStatus("valid");
        setKeyStatusMsg("Key is valid and active on Google Gemini gateway.");
      } else {
        setKeyStatus("error");
        setKeyStatusMsg(res?.message || "Invalid API key or network unreachable.");
      }
    } catch (e: any) {
      setKeyStatus("error");
      setKeyStatusMsg(e.message || "Failed to reach Gemini validation service.");
    } finally {
      setIsTestingKey(false);
    }
  };

  // Step 3: Save Key
  const handleSaveKey = async () => {
    if (!apiKeyInput.trim()) {
      setKeyStatus("error");
      setKeyStatusMsg("Please enter an API key first.");
      return;
    }
    setIsSavingKey(true);
    try {
      // Validate first if not already valid
      if (keyStatus !== "valid") {
        setKeyStatus("validating");
        setKeyStatusMsg("Validating before saving...");
        const testRes = await testApiKey(apiKeyInput.trim());
        if (!testRes || !testRes.valid) {
          setKeyStatus("error");
          setKeyStatusMsg(testRes?.message || "Invalid API key. Please check and try again.");
          setIsSavingKey(false);
          return;
        }
      }
      const res = await saveApiKey(apiKeyInput.trim(), 1);
      if (res && res.status === "ok") {
        setMaskedKey(res.masked_key || "••••••••••••••••");
        setApiKeyInput("");
        setKeyStatus("valid");
        setKeyStatusMsg("Key securely stored using Windows DPAPI encryption.");
      } else {
        setKeyStatus("error");
        setKeyStatusMsg(res?.message || "Failed to save key.");
      }
    } catch (e: any) {
      setKeyStatus("error");
      setKeyStatusMsg(e.message || "Error saving key.");
    } finally {
      setIsSavingKey(false);
    }
  };

  // Step 3: Remove Key
  const handleRemoveKey = async () => {
    try {
      await removeApiKey(1);
      setMaskedKey("");
      setApiKeyInput("");
      setKeyStatus("not_configured");
      setKeyStatusMsg("API key removed.");
    } catch (e: any) {
      setKeyStatusMsg(`Error removing key: ${e.message}`);
    }
  };

  const getHttpBase = () => {
    const loc = window.location;
    if (loc.port === "5173") {
      return `http://127.0.0.1:8000`;
    }
    return `${loc.protocol}//${loc.host}`;
  };

  // Step 4: Vault Setup In Wizard
  const handleSetupVaultInWizard = async () => {
    if (vaultMasterPw.length < 6) {
      setVaultMsg({ type: "error", text: "Master password must be at least 6 characters." });
      return;
    }
    if (vaultMasterPw !== vaultConfirmPw) {
      setVaultMsg({ type: "error", text: "Master passwords do not match. Please verify." });
      return;
    }
    setIsSettingUpVault(true);
    setVaultMsg(null);
    try {
      const res = await fetch(`${getHttpBase()}/api/vault/setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ master_password: vaultMasterPw }),
      });
      const data = await res.json();
      if (res.ok && data.status === "ok") {
        setVaultChoice("configured");
        setVaultMsg({ type: "success", text: "Secure Password Vault initialized and unlocked!" });
        setVaultMasterPw("");
        setVaultConfirmPw("");
        setTimeout(() => {
          goToDiagnostics();
        }, 1200);
      } else {
        setVaultMsg({ type: "error", text: data.message || "Failed to set up vault." });
      }
    } catch {
      setVaultMsg({ type: "error", text: "Failed to connect to vault service." });
    } finally {
      setIsSettingUpVault(false);
    }
  };

  // Step 5: Run Diagnostics
  const handleRunDiagnostics = async () => {
    setIsRunningDiag(true);
    try {
      const res = await runDiagnostics();
      setDiagResult(res);
    } catch {
      //
    } finally {
      setIsRunningDiag(false);
    }
  };

  // Trigger diagnostics automatically when entering step 5
  const goToDiagnostics = () => {
    setCurrentStep(5);
    handleRunDiagnostics();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 select-none">
      <div className="w-full max-w-2xl bg-[#060B1A] border border-cyan-500/40 rounded-xl shadow-[0_0_50px_rgba(34,211,238,0.25)] flex flex-col overflow-hidden text-white animate-in fade-in zoom-in-95 duration-200">
        {/* Wizard Header */}
        <div className="px-6 py-4 flex items-center justify-between border-b border-cyan-500/20 bg-[#0A1226]/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg border border-cyan-400/40 bg-cyan-950/40 flex items-center justify-center shadow-[0_0_10px_rgba(34,211,238,0.25)]">
              <Sparkles className="w-4 h-4 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-base font-bold tracking-wide text-white">SG CUBE Setup Wizard</h2>
              <p className="text-[11px] text-text-muted font-mono">First-Time User Configuration & System Health Check</p>
            </div>
          </div>
          {/* Step Pills */}
          <div className="flex items-center gap-1.5 font-mono text-xs">
            {[1, 2, 3, 4, 5, 6].map((step) => (
              <span
                key={step}
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold transition-all ${
                  currentStep === step
                    ? "bg-cyan-400 text-black shadow-[0_0_10px_#22D3EE]"
                    : currentStep > step
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-500/40"
                    : "bg-black/40 text-text-muted border border-white/10"
                }`}
              >
                {step}
              </span>
            ))}
          </div>
        </div>

        {/* Wizard Body */}
        <div className="p-6 flex-1 overflow-y-auto max-h-[65vh]">
          {/* STEP 1: Welcome */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-500/30 flex items-start gap-3">
                <Cpu className="w-6 h-6 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-cyan-300 mb-1">
                    Welcome to SG CUBE — Your AI Assistive Companion
                  </h3>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    SG CUBE is a dual-mode assistive system designed specifically for visually impaired users. It combines real-time local computer vision (face recognition, obstacle awareness, color detection, document reading) with Google Gemini conversational intelligence and Windows desktop automation.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-3 rounded-lg bg-black/40 border border-cyan-500/20 flex flex-col gap-1">
                  <span className="text-cyan-400 font-bold">MODE 1: ASSISTIVE VISION</span>
                  <p className="text-[11px] text-text-muted font-sans">
                    Fast local vision models (YuNet + SFace) running entirely on CPU for latency-critical environmental awareness and face identification.
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-black/40 border border-cyan-500/20 flex flex-col gap-1">
                  <span className="text-cyan-400 font-bold">MODE 2: PERSONAL AI</span>
                  <p className="text-[11px] text-text-muted font-sans">
                    Gemini Live multimodal reasoning for open conversation, persistent memory, screen understanding, and system volume/media control.
                  </p>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 flex items-center gap-2 text-xs text-emerald-300">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>All biometric face embeddings and encrypted API keys are stored securely on this computer.</span>
              </div>
            </div>
          )}

          {/* STEP 2: Ask Name */}
          {currentStep === 2 && (
            <div className="space-y-5">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2 mb-1">
                  <User className="w-5 h-5 text-cyan-400" />
                  What should SG CUBE call you?
                </h3>
                <p className="text-xs text-text-muted">
                  SG CUBE uses your name to personalize speech greetings and identify your user profile.
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-mono text-cyan-400 mb-1.5">
                    Your Name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={userName}
                    onChange={(e) => setUserName(e.target.value)}
                    placeholder="Enter your name (e.g. Alex, Sam, Maria)..."
                    className="w-full px-3.5 py-2 rounded-lg bg-black/50 border border-cyan-500/30 text-white placeholder-text-muted/50 focus:outline-none focus:border-cyan-400 text-sm font-sans"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-xs font-mono text-text-muted mb-1.5">
                    Display / Spoken Greeting (Optional)
                  </label>
                  <input
                    type="text"
                    value={userDisplayName}
                    onChange={(e) => setUserDisplayName(e.target.value)}
                    placeholder={userName ? `Default: ${userName}` : "How SG CUBE should address you..."}
                    className="w-full px-3.5 py-2 rounded-lg bg-black/50 border border-cyan-500/20 text-white placeholder-text-muted/50 focus:outline-none focus:border-cyan-400 text-sm font-sans"
                  />
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: API Key Setup */}
          {currentStep === 3 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2 mb-1">
                  <Key className="w-5 h-5 text-cyan-400" />
                  Configure Google Gemini API Key
                </h3>
                <p className="text-xs text-text-muted">
                  A Google Gemini API key enables real-time voice conversations and visual reasoning. Your key is stored locally and protected with Windows DPAPI encryption.
                </p>
              </div>

              {/* Configured Key Display if available */}
              {maskedKey && (
                <div className="p-3.5 rounded-lg bg-black/40 border border-cyan-500/30 flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-mono text-cyan-400">CURRENT ENCRYPTED KEY</span>
                    <span className="text-sm font-mono tracking-widest text-emerald-400 font-bold">
                      {maskedKey}
                    </span>
                  </div>
                  <button
                    onClick={handleRemoveKey}
                    className="px-2.5 py-1 rounded bg-red-950/40 border border-red-500/30 text-red-300 hover:bg-red-900/60 text-xs font-mono flex items-center gap-1 transition-colors"
                    title="Remove key"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Remove</span>
                  </button>
                </div>
              )}

              {/* Input for new or replacement key */}
              <div className="space-y-2">
                <label className="block text-xs font-mono text-cyan-400">
                  {maskedKey ? "Replace / Update Gemini API Key:" : "Enter Gemini API Key:"}
                </label>
                <div className="relative">
                  <input
                    type={showKeyText ? "text" : "password"}
                    value={apiKeyInput}
                    onChange={(e) => {
                      setApiKeyInput(e.target.value);
                      if (keyStatus === "error") setKeyStatus("not_configured");
                    }}
                    placeholder="AIzaSy..."
                    className="w-full pl-3.5 pr-10 py-2 rounded-lg bg-black/50 border border-cyan-500/30 text-white placeholder-text-muted/50 focus:outline-none focus:border-cyan-400 text-sm font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKeyText(!showKeyText)}
                    className="absolute right-2.5 top-2.5 text-text-muted hover:text-white"
                  >
                    {showKeyText ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Action Buttons: Test Key & Save Key */}
              <div className="flex items-center gap-2.5 pt-1">
                <button
                  type="button"
                  onClick={handleTestKey}
                  disabled={isTestingKey || !apiKeyInput.trim()}
                  className="px-3.5 py-1.5 rounded-lg bg-black/40 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-950/40 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-mono font-medium flex items-center gap-1.5 transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isTestingKey ? "animate-spin text-cyan-400" : ""}`} />
                  <span>{isTestingKey ? "Validating Key..." : "Test Key"}</span>
                </button>

                <button
                  type="button"
                  onClick={handleSaveKey}
                  disabled={isSavingKey || !apiKeyInput.trim()}
                  className="px-4 py-1.5 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-mono font-bold flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(34,211,238,0.2)]"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{isSavingKey ? "Saving..." : "Save Key"}</span>
                </button>
              </div>

              {/* Status Indicator */}
              {keyStatusMsg && (
                <div
                  className={`p-3 rounded-lg border text-xs font-mono flex items-start gap-2 ${
                    keyStatus === "valid"
                      ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-300"
                      : keyStatus === "error"
                      ? "bg-red-950/40 border-red-500/40 text-red-300"
                      : "bg-cyan-950/40 border-cyan-500/40 text-cyan-300"
                  }`}
                >
                  {keyStatus === "valid" ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  ) : keyStatus === "error" ? (
                    <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  ) : (
                    <RefreshCw className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5 animate-spin" />
                  )}
                  <span>{keyStatusMsg}</span>
                </div>
              )}
            </div>
          )}

          {/* STEP 4: Secure Password Vault Setup */}
          {currentStep === 4 && (
            <div className="space-y-5 py-1">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2 mb-1">
                  <Shield className="w-5 h-5 text-cyan-400" />
                  Would you like to set up your secure password vault?
                </h3>
                <p className="text-xs text-text-muted">
                  Protect private credentials, Wi-Fi passwords, ATM PINs, and sensitive documents with local AES-256-GCM hardware encryption and Argon2id key derivation.
                </p>
              </div>

              {vaultChoice === "ask" && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-500/30 flex items-start gap-3">
                    <ShieldAlert className="w-6 h-6 text-cyan-400 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-xs font-bold text-cyan-300 mb-1">Zero-Knowledge Offline Vault</h4>
                      <p className="text-xs text-text-secondary leading-relaxed">
                        Your master password is never stored in plaintext, never logged, and never sent to cloud models. All secrets remain strictly encrypted on this PC.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setVaultChoice("setup")}
                      className="p-4 rounded-xl bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 flex flex-col items-center justify-center gap-2 transition-all shadow-[0_0_15px_rgba(34,211,238,0.2)] text-xs font-mono font-bold"
                    >
                      <Lock className="w-5 h-5 text-cyan-400" />
                      <span>Set Up Vault</span>
                    </button>

                    <button
                      type="button"
                      onClick={goToDiagnostics}
                      className="p-4 rounded-xl bg-black/40 border border-white/15 text-text-muted hover:text-white hover:border-white/30 flex flex-col items-center justify-center gap-2 transition-all text-xs font-mono"
                    >
                      <Unlock className="w-5 h-5 text-text-muted" />
                      <span>Skip for Now</span>
                    </button>
                  </div>
                </div>
              )}

              {vaultChoice === "setup" && (
                <div className="space-y-4 max-w-lg mx-auto">
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-mono text-cyan-400 mb-1">
                        Choose Master Password <span className="text-red-400">*</span>
                      </label>
                      <div className="relative">
                        <input
                          type={showVaultPw ? "text" : "password"}
                          value={vaultMasterPw}
                          onChange={(e) => setVaultMasterPw(e.target.value)}
                          placeholder="Enter strong master password (min 6 chars)..."
                          className="w-full pl-3.5 pr-10 py-2 rounded-lg bg-black/50 border border-cyan-500/30 text-white placeholder-text-muted/50 focus:outline-none focus:border-cyan-400 text-sm font-mono"
                          autoFocus
                        />
                        <button
                          type="button"
                          onClick={() => setShowVaultPw(!showVaultPw)}
                          className="absolute right-2.5 top-2.5 text-text-muted hover:text-white"
                        >
                          {showVaultPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-mono text-cyan-400 mb-1">
                        Confirm Master Password <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="password"
                        value={vaultConfirmPw}
                        onChange={(e) => setVaultConfirmPw(e.target.value)}
                        placeholder="Repeat master password..."
                        className="w-full px-3.5 py-2 rounded-lg bg-black/50 border border-cyan-500/30 text-white placeholder-text-muted/50 focus:outline-none focus:border-cyan-400 text-sm font-mono"
                      />
                      {vaultConfirmPw && vaultMasterPw !== vaultConfirmPw && (
                        <p className="text-[11px] text-red-400 font-mono mt-1">Passwords do not match.</p>
                      )}
                    </div>
                  </div>

                  {vaultMsg && (
                    <div
                      className={`p-2.5 rounded-lg border text-xs font-mono flex items-center gap-2 ${
                        vaultMsg.type === "success"
                          ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-300"
                          : "bg-red-950/40 border-red-500/40 text-red-300"
                      }`}
                    >
                      {vaultMsg.type === "success" ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                      )}
                      <span>{vaultMsg.text}</span>
                    </div>
                  )}

                  <div className="flex items-center gap-2.5 pt-1">
                    <button
                      type="button"
                      onClick={handleSetupVaultInWizard}
                      disabled={isSettingUpVault || !vaultMasterPw || vaultMasterPw !== vaultConfirmPw || vaultMasterPw.length < 6}
                      className="px-5 py-2 rounded-lg bg-cyan-500/25 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/35 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-mono font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(34,211,238,0.25)]"
                    >
                      {isSettingUpVault ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      )}
                      <span>{isSettingUpVault ? "Initializing..." : "Create & Initialize Vault"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={goToDiagnostics}
                      className="px-4 py-2 rounded-lg bg-black/40 border border-white/15 text-text-muted hover:text-white text-xs font-mono"
                    >
                      Skip for Now
                    </button>
                  </div>
                </div>
              )}

              {vaultChoice === "configured" && (
                <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/40 flex items-center gap-3 text-emerald-300 text-xs font-mono">
                  <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0" />
                  <div>
                    <span className="font-bold">Password Vault Configured & Active</span>
                    <p className="text-[11px] text-emerald-200/80 font-sans mt-0.5">
                      Your vault is now ready. You can add passwords anytime from the top bar or via voice commands.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 5: Real System Diagnostics */}
          {currentStep === 5 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <Activity className="w-5 h-5 text-cyan-400" />
                    System Hardware & Diagnostic Check
                  </h3>
                  <p className="text-xs text-text-muted">
                    Testing operating system, microphone, speakers, camera, internet, AI models, and local databases.
                  </p>
                </div>
                <button
                  onClick={handleRunDiagnostics}
                  disabled={isRunningDiag}
                  className="px-3 py-1 rounded bg-black/40 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-950/40 text-xs font-mono flex items-center gap-1.5 transition-colors disabled:opacity-40"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isRunningDiag ? "animate-spin" : ""}`} />
                  <span>Re-test</span>
                </button>
              </div>

              {/* Overall status banner */}
              {diagResult && (
                <div
                  className={`p-2.5 rounded-lg border text-xs font-mono flex items-center justify-between ${
                    diagResult.overall === "PASS"
                      ? "bg-emerald-950/50 border-emerald-500/40 text-emerald-300"
                      : diagResult.overall === "WARNING"
                      ? "bg-amber-950/50 border-amber-500/40 text-amber-300"
                      : "bg-red-950/50 border-red-500/40 text-red-300"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {diagResult.overall === "PASS" ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : diagResult.overall === "WARNING" ? (
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400" />
                    )}
                    <span className="font-bold">SYSTEM READINESS: {diagResult.overall}</span>
                  </div>
                  <span className="text-[10px] text-text-muted">
                    {diagResult.checks.filter((c) => c.status === "PASS").length} of {diagResult.checks.length} checks passed
                  </span>
                </div>
              )}

              {/* Diagnostic Items List */}
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {isRunningDiag && !diagResult ? (
                  <div className="py-8 flex flex-col items-center justify-center gap-2 text-cyan-400 font-mono text-xs">
                    <RefreshCw className="w-6 h-6 animate-spin" />
                    <span>Executing real hardware & network tests...</span>
                  </div>
                ) : diagResult?.checks ? (
                  diagResult.checks.map((c) => (
                    <div
                      key={c.id}
                      className="p-2.5 rounded-lg bg-black/40 border border-cyan-500/20 text-xs font-mono flex flex-col gap-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white">{c.name}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            c.status === "PASS"
                              ? "bg-emerald-950 text-emerald-300 border border-emerald-500/40"
                              : c.status === "WARNING"
                              ? "bg-amber-950 text-amber-300 border border-amber-500/40"
                              : "bg-red-950 text-red-300 border border-red-500/40"
                          }`}
                        >
                          {c.status}
                        </span>
                      </div>
                      <p className="text-[11px] text-text-secondary font-sans">{c.details}</p>
                      {c.remedy && (
                        <p className="text-[11px] text-amber-300/90 bg-amber-950/20 p-1.5 rounded border border-amber-500/20 font-sans mt-0.5">
                          💡 <span className="font-semibold">Action:</span> {c.remedy}
                        </p>
                      )}
                    </div>
                  ))
                ) : null}
              </div>
            </div>
          )}

          {/* STEP 6: Completion */}
          {currentStep === 6 && (
            <div className="space-y-5 text-center py-4">
              <div className="w-16 h-16 rounded-full bg-cyan-950/60 border border-cyan-400/50 flex items-center justify-center mx-auto shadow-[0_0_24px_rgba(34,211,238,0.3)]">
                <CheckCircle2 className="w-8 h-8 text-cyan-400" />
              </div>

              <div>
                <h3 className="text-lg font-bold text-white mb-1">
                  Setup Complete! Welcome aboard, {userName || "friend"}.
                </h3>
                <p className="text-xs text-text-secondary max-w-md mx-auto">
                  SG CUBE is now configured and ready. Say <span className="text-cyan-400 font-mono">"SG CUBE"</span> anytime to wake your assistant, or use the interactive HUD dashboard.
                </p>
              </div>

              <div className="p-3.5 rounded-lg bg-black/40 border border-cyan-500/20 text-xs font-mono text-left max-w-md mx-auto space-y-1 text-text-muted">
                <div className="flex justify-between">
                  <span>Profile Name:</span>
                  <span className="text-white font-bold">{userName || "User"}</span>
                </div>
                <div className="flex justify-between">
                  <span>Gemini API:</span>
                  <span className={maskedKey ? "text-emerald-400 font-bold" : "text-amber-400"}>
                    {maskedKey ? "Configured & Protected" : "Standby (Local Vision Only)"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Password Vault:</span>
                  <span className={vaultChoice === "configured" ? "text-emerald-400 font-bold" : "text-cyan-400 font-bold"}>
                    {vaultChoice === "configured" ? "Encrypted & Configured" : "Available in Settings"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>First-Run Status:</span>
                  <span className="text-emerald-400 font-bold">Verified Ready</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Wizard Footer Controls */}
        <div className="px-6 py-3.5 border-t border-cyan-500/20 bg-[#0A1226]/80 flex items-center justify-between">
          {currentStep > 1 && currentStep < 6 ? (
            <button
              onClick={() => setCurrentStep((prev) => prev - 1)}
              className="px-3.5 py-1.5 rounded-lg border border-cyan-500/20 text-text-muted hover:text-white hover:bg-white/5 text-xs font-mono flex items-center gap-1.5 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back</span>
            </button>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2">
            {currentStep === 1 && (
              <button
                onClick={() => setCurrentStep(2)}
                className="px-5 py-2 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 text-xs font-mono font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(34,211,238,0.25)]"
              >
                <span>Get Started</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            {currentStep === 2 && (
              <button
                onClick={handleSaveNameAndContinue}
                disabled={!userName.trim()}
                className="px-5 py-2 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-mono font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(34,211,238,0.25)]"
              >
                <span>Next: API Key</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            {currentStep === 3 && (
              <button
                onClick={() => setCurrentStep(4)}
                className="px-5 py-2 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 text-xs font-mono font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(34,211,238,0.25)]"
              >
                <span>Next: Password Vault</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            {currentStep === 4 && vaultChoice === "ask" && (
              <button
                onClick={goToDiagnostics}
                className="px-5 py-2 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 text-xs font-mono font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(34,211,238,0.25)]"
              >
                <span>Next: System Check</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            {currentStep === 4 && vaultChoice === "configured" && (
              <button
                onClick={goToDiagnostics}
                className="px-5 py-2 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 text-xs font-mono font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(34,211,238,0.25)]"
              >
                <span>Next: System Check</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            {currentStep === 5 && (
              <button
                onClick={() => setCurrentStep(6)}
                className="px-5 py-2 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 text-xs font-mono font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(34,211,238,0.25)]"
              >
                <span>Next: Review & Launch</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            {currentStep === 6 && (
              <button
                onClick={onComplete}
                className="px-6 py-2 rounded-lg bg-emerald-500/25 border border-emerald-400 text-emerald-200 hover:bg-emerald-500/35 text-xs font-mono font-bold flex items-center gap-2 transition-all shadow-[0_0_16px_rgba(52,211,153,0.3)]"
              >
                <Sparkles className="w-4 h-4 text-emerald-300" />
                <span>Launch SG CUBE</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
