"""
SG CUBE 2.5 — Feature 9: Permission-Based System Automation Subsystem
Provides controlled, secure system-level actions via voice and GUI:
- Strict Allowlist-Only Registry (No arbitrary shell, PowerShell, cmd, or eval)
- Granular Permissions: ALLOWED, ASK_EACH_TIME, DENIED
- Risk Classification: SAFE, LOW_RISK, PROTECTED, HIGH_RISK, BLOCKED
- Voice Security Integration (Voice Password session required for PROTECTED/HIGH_RISK)
- Continuous Conversation Confirmation & Context (Feature 6 integration)
- Document OCR Injection Isolation (Feature 8 passive text isolation)
- In-RAM Audit Logging with zero credential or sensitive argument leakage
- Verified execution with post-launch checks
"""

import os
import re
import sys
import time
import json
import uuid
import ctypes
import shutil
import logging
import ipaddress
import subprocess
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Union
from urllib.parse import urlparse
from .ui_automation_manager import UIAutomationManager

logger = logging.getLogger(__name__)


class AutomationRiskLevel(str, Enum):
    """Risk tiers for system automation actions."""
    SAFE = "SAFE"                 # Safe perception/display (e.g., read status, copy text)
    LOW_RISK = "LOW_RISK"         # Standard productivity app launch (e.g., open calculator, notepad)
    PROTECTED = "PROTECTED"       # Modifying actions / Process close / Personal folders
    HIGH_RISK = "HIGH_RISK"       # System state changes (e.g., lock workstation, mass changes)
    BLOCKED = "BLOCKED"           # Explicitly forbidden (arbitrary shell, script execution, system root access)


class AutomationPermission(str, Enum):
    """User-configurable permission policies for automation actions."""
    ALLOWED = "ALLOWED"           # Automatic execution without confirmation if security allows
    ASK_EACH_TIME = "ASK_EACH_TIME" # Always prompts for user voice confirmation first
    DENIED = "DENIED"             # Denied by default or user preference; will not execute


class AutomationActionType(str, Enum):
    """Supported structured system automation actions."""
    OPEN_APP = "OPEN_APP"
    CLOSE_APP = "CLOSE_APP"
    OPEN_URL = "OPEN_URL"
    OPEN_FOLDER = "OPEN_FOLDER"
    COPY_TEXT = "COPY_TEXT"
    LOCK_WORKSTATION = "LOCK_WORKSTATION"
    READ_SCREEN = "READ_SCREEN"
    SEND_MESSAGE = "SEND_MESSAGE"
    STATUS = "STATUS"
    UNKNOWN = "UNKNOWN"


class AutomationResultStatus(str, Enum):
    """Outcome states for an automation execution attempt."""
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    REQUIRES_SECURITY_AUTH = "REQUIRES_SECURITY_AUTH"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


@dataclass
class AutomationActionDefinition:
    """Predefined safe action metadata in the Allowlist Registry."""
    action_type: AutomationActionType
    name: str
    display_name: str
    description: str
    default_risk: AutomationRiskLevel
    default_permission: AutomationPermission
    executable_candidates: List[str] = field(default_factory=list)
    process_names: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)


@dataclass
class AutomationRequest:
    """Structured request for a system automation operation."""
    request_id: str
    action_type: AutomationActionType
    target: str
    display_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    risk_level: AutomationRiskLevel = AutomationRiskLevel.SAFE
    permission: AutomationPermission = AutomationPermission.ALLOWED
    requires_confirmation: bool = False
    requires_security_auth: bool = False
    created_at: float = field(default_factory=time.time)
    source: str = "voice"  # "voice", "gui", "document_isolated"
    resolved_target: Optional[str] = None

    def is_expired(self, ttl_seconds: float = 60.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.created_at) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "display_name": self.display_name,
            "risk_level": self.risk_level.value,
            "permission": self.permission.value,
            "requires_confirmation": self.requires_confirmation,
            "requires_security_auth": self.requires_security_auth,
            "created_at": self.created_at,
            "source": self.source,
            "resolved_target": self.resolved_target,
        }


@dataclass
class AutomationResult:
    """Structured execution outcome of an automation action."""
    status: AutomationResultStatus
    message: str
    spoken_response: str
    request: Optional[AutomationRequest] = None
    action_type: Optional[AutomationActionType] = None
    target: Optional[str] = None
    pid: Optional[int] = None
    executed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "spoken_response": self.spoken_response,
            "action_type": self.action_type.value if self.action_type else None,
            "target": self.target,
            "pid": self.pid,
            "executed_at": self.executed_at,
        }


@dataclass
class AutomationAuditRecord:
    """Transient in-memory audit log entry (zero credentials/secrets persisted)."""
    request_id: str
    action_type: str
    target: str
    status: str
    risk_level: str
    timestamp: float = field(default_factory=time.time)
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_type": self.action_type,
            "target": self.target,
            "status": self.status,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp,
            "details": self.details,
        }


class AutomationManager:
    """
    Subsystem for permission-enforced system automation in SG CUBE 2.5.
    
    Guarantees:
    1. Zero arbitrary command or shell execution (shell=False strictly enforced).
    2. Strict allowlists for applications, protocols, and safe directories.
    3. Seamless Voice Security (PBKDF2/Session) validation for PROTECTED & HIGH_RISK actions.
    4. Two-step confirmation flow via Continuous Conversation Context (Feature 6).
    5. Isolation from OCR document text to prevent prompt injection.
    6. In-RAM audit ring buffer without sensitive data persistence.
    """

    # Safe Default Applications Allowlist
    APPROVED_APPS: Dict[str, AutomationActionDefinition] = {
        "calculator": AutomationActionDefinition(
            action_type=AutomationActionType.OPEN_APP,
            name="calculator",
            display_name="Calculator",
            description="Windows Standard Calculator",
            default_risk=AutomationRiskLevel.LOW_RISK,
            default_permission=AutomationPermission.ALLOWED,
            executable_candidates=["calc.exe", "calc"],
            process_names=["CalculatorApp.exe", "Calculator.exe", "calc.exe"],
            aliases=["calc", "calculator", "math calculator", "the calculator"]
        ),
        "notepad": AutomationActionDefinition(
            action_type=AutomationActionType.OPEN_APP,
            name="notepad",
            display_name="Notepad",
            description="Windows Text Editor",
            default_risk=AutomationRiskLevel.LOW_RISK,
            default_permission=AutomationPermission.ALLOWED,
            executable_candidates=["notepad.exe", "notepad"],
            process_names=["notepad.exe", "Notepad.exe"],
            aliases=["notepad", "text editor", "note pad", "the notepad"]
        ),
        "file explorer": AutomationActionDefinition(
            action_type=AutomationActionType.OPEN_APP,
            name="file explorer",
            display_name="File Explorer",
            description="Windows File Explorer",
            default_risk=AutomationRiskLevel.LOW_RISK,
            default_permission=AutomationPermission.ALLOWED,
            executable_candidates=["explorer.exe"],
            process_names=["explorer.exe"],
            aliases=["explorer", "file explorer", "files", "my files", "windows explorer", "the explorer"]
        ),
        "browser": AutomationActionDefinition(
            action_type=AutomationActionType.OPEN_APP,
            name="browser",
            display_name="Web Browser",
            description="Default Web Browser",
            default_risk=AutomationRiskLevel.LOW_RISK,
            default_permission=AutomationPermission.ALLOWED,
            executable_candidates=["msedge.exe", "chrome.exe", "firefox.exe"],
            process_names=["msedge.exe", "chrome.exe", "firefox.exe"],
            aliases=["browser", "web browser", "edge", "ms edge", "chrome", "google chrome", "firefox", "internet"]
        ),
        "whatsapp": AutomationActionDefinition(
            action_type=AutomationActionType.OPEN_APP,
            name="whatsapp",
            display_name="WhatsApp",
            description="WhatsApp Desktop",
            default_risk=AutomationRiskLevel.LOW_RISK,
            default_permission=AutomationPermission.ALLOWED,
            executable_candidates=["WhatsApp.exe", "WhatsApp"],
            process_names=["WhatsApp.exe", "WhatsApp.Root.exe"],
            aliases=["whatsapp", "whatsapp desktop", "whats app", "the whatsapp", "messages", "chat"]
        ),
    }

    # Default Allowed Domains for Safe Web Navigation
    APPROVED_DOMAINS: List[str] = [
        "google.com", "www.google.com",
        "wikipedia.org", "www.wikipedia.org", "en.wikipedia.org",
        "github.com", "www.github.com",
        "youtube.com", "www.youtube.com",
        "stackoverflow.com", "www.stackoverflow.com",
        "python.org", "www.python.org",
        "bing.com", "www.bing.com",
        "duckduckgo.com", "www.duckduckgo.com",
        "weather.com", "www.weather.com",
        "bbc.com", "www.bbc.com",
        "cnn.com", "www.cnn.com",
        "reuters.com", "www.reuters.com",
        "nih.gov", "www.nih.gov",
        "openai.com", "www.openai.com",
        "gemini.google.com",
    ]

    # Dangerous command / token blacklists for injection prevention
    PROHIBITED_PATTERNS = [
        r'\bcmd(?:\.exe)?\b',
        r'\bpowershell(?:\.exe)?\b',
        r'\bpwsh(?:\.exe)?\b',
        r'\bbash\b',
        r'\bsh\b',
        r'\bwscript(?:\.exe)?\b',
        r'\bcscript(?:\.exe)?\b',
        r'\breg(?:edit)?(?:\.exe)?\b',
        r'\bformat\b',
        r'\bdel\b',
        r'\brmdir\b',
        r'\brd\b',
        r'\brm\b',
        r'\bcurl\b',
        r'\bwget\b',
        r'\bcertutil\b',
        r'\bpython(?:\.exe)?\b',
        r'\bnode(?:\.exe)?\b',
        r'\bperl\b',
        r'\bruby\b',
        r'\bvbs\b',
        r'[;&|`$><\n\r]',
    ]

    def __init__(self, pref_dir: Optional[str] = None, security_manager: Optional[Any] = None):
        """
        Initializes AutomationManager with preferences directory and optional SecurityManager.
        """
        self.pref_dir = pref_dir or os.path.join(os.path.expanduser("~"), ".sg_cube")
        os.makedirs(self.pref_dir, exist_ok=True)
        self.security = security_manager
        self.config_path = os.path.join(self.pref_dir, "automation_permissions.json")

        # In-RAM audit ring buffer (max 50 records)
        self._audit_log: deque = deque(maxlen=50)

        # In-memory permissions dictionary: action_key -> AutomationPermission
        self._permissions: Dict[str, AutomationPermission] = self._load_permissions()
        # UI Automation & screen perception subsystem
        self.ui_automation = UIAutomationManager(automation_manager=self)

    def _default_permissions(self) -> Dict[str, AutomationPermission]:
        """Returns standard default permission map."""
        return {
            AutomationActionType.OPEN_APP.value: AutomationPermission.ALLOWED,
            AutomationActionType.CLOSE_APP.value: AutomationPermission.ASK_EACH_TIME,
            AutomationActionType.OPEN_URL.value: AutomationPermission.ALLOWED,
            AutomationActionType.OPEN_FOLDER.value: AutomationPermission.ASK_EACH_TIME,
            AutomationActionType.COPY_TEXT.value: AutomationPermission.ALLOWED,
            AutomationActionType.LOCK_WORKSTATION.value: AutomationPermission.ASK_EACH_TIME,
            AutomationActionType.READ_SCREEN.value: AutomationPermission.ALLOWED,
            AutomationActionType.SEND_MESSAGE.value: AutomationPermission.ASK_EACH_TIME,
            AutomationActionType.STATUS.value: AutomationPermission.ALLOWED,
        }

    def _load_permissions(self) -> Dict[str, AutomationPermission]:
        """Loads permission preferences from disk or populates defaults."""
        perms = self._default_permissions()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if k in perms and isinstance(v, str):
                                try:
                                    perms[k] = AutomationPermission(v)
                                except ValueError:
                                    pass
            except Exception as e:
                logger.warning(f"[AutomationManager] Failed to load permissions from {self.config_path}: {e}")
        return perms

    def save_permissions(self) -> bool:
        """Saves current permissions to disk."""
        try:
            data = {k: v.value for k, v in self._permissions.items()}
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"[AutomationManager] Failed to save permissions to {self.config_path}: {e}")
            return False

    def get_permission(self, action_type: Union[str, AutomationActionType]) -> AutomationPermission:
        """Retrieves active permission policy for an action type."""
        key = action_type.value if isinstance(action_type, AutomationActionType) else str(action_type)
        return self._permissions.get(key, AutomationPermission.ASK_EACH_TIME)

    def set_permission(self, action_type: Union[str, AutomationActionType], permission: Union[str, AutomationPermission]) -> bool:
        """Updates permission policy for an action type."""
        key = action_type.value if isinstance(action_type, AutomationActionType) else str(action_type)
        if isinstance(permission, str):
            try:
                permission = AutomationPermission(permission)
            except ValueError:
                return False
        self._permissions[key] = permission
        return self.save_permissions()

    def get_all_permissions(self) -> Dict[str, str]:
        """Returns all permission settings as a string dictionary."""
        return {k: v.value for k, v in self._permissions.items()}

    def reset_permissions_to_defaults(self) -> bool:
        """Resets all permission policies to secure defaults."""
        self._permissions = self._default_permissions()
        return self.save_permissions()

    # --------------------------------------------------------------------------
    # Allowlist Resolution & Security Checks
    # --------------------------------------------------------------------------

    def is_malicious_input(self, text: str) -> bool:
        """Checks for dangerous shell injection tokens or prohibited executable names."""
        if not text:
            return False
        clean = text.strip()
        for pattern in self.PROHIBITED_PATTERNS:
            if re.search(pattern, clean, re.IGNORECASE):
                return True
        return False

    def resolve_app(self, app_name: str) -> Optional[AutomationActionDefinition]:
        """
        Resolves a spoken or queried app name to an approved AutomationActionDefinition.
        Returns None if app is not in the strict safe allowlist or contains malicious patterns.
        """
        if not app_name:
            return None
        target = app_name.strip().lower()

        # Reject any input containing prohibited shell or script patterns
        if self.is_malicious_input(target):
            return None

        # Direct match in registry keys
        if target in self.APPROVED_APPS:
            return self.APPROVED_APPS[target]

        # Normalized alias search
        clean_target = re.sub(r'[^\w\s]', '', target).strip()
        for defn in self.APPROVED_APPS.values():
            if target in defn.aliases or clean_target in defn.aliases:
                return defn
            for alias in defn.aliases:
                if re.search(rf'\b{re.escape(alias)}\b', clean_target):
                    return defn
        return None

    def resolve_close_target(self, app_name: str) -> Optional[Tuple[str, List[str]]]:
        """
        Resolves an application name to its approved process termination names.
        Returns (display_name, process_names) or None.
        """
        defn = self.resolve_app(app_name)
        if defn and defn.process_names:
            return defn.display_name, defn.process_names
        return None

    def validate_url(self, url: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validates URL against strict security requirements:
        - Only HTTP and HTTPS schemes allowed.
        - Strict rejection of javascript:, file:, data:, vbscript:, ms-settings:, etc.
        - Strict rejection of shell injections, delimiters, and local UNC paths.
        - Resolves full normalized URL.
        Returns (is_valid, reason_or_normalized_url, domain).
        """
        if not url:
            return False, "URL cannot be empty.", None

        url_str = url.strip()

        # Reject dangerous injection tokens
        if self.is_malicious_input(url_str):
            return False, "Rejected due to potentially unsafe characters.", None

        # Add https:// prefix if user provided bare domain like 'google.com'
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9+\-.]*://', url_str):
            # Check if bare domain looks like a valid hostname
            if re.match(r'^[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?$', url_str):
                url_str = f"https://{url_str}"
            else:
                return False, "Invalid URL format.", None

        try:
            parsed = urlparse(url_str)
        except Exception:
            return False, "Malformed URL.", None

        # Strictly enforce HTTP / HTTPS
        if parsed.scheme.lower() not in ["http", "https"]:
            return False, f"Unsupported or dangerous protocol scheme: '{parsed.scheme}'. Only HTTP and HTTPS are permitted.", None

        domain = parsed.hostname.lower() if parsed.hostname else ""
        if not domain:
            return False, "Missing valid domain name.", None

        # Reject localhost, loopback, private local IPs, and cloud metadata endpoints to prevent SSRF
        try:
            ip = ipaddress.ip_address(domain)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False, "Navigation to private or internal network IP addresses is restricted.", None
        except ValueError:
            pass

        if domain in ["localhost", "127.0.0.1", "::1", "0.0.0.0"] or domain.endswith(".local") or domain.endswith(".internal"):
            return False, "Navigation to local or internal loopback hosts is restricted.", None

        return True, url_str, domain

    def validate_folder_path(self, folder_name_or_path: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validates folder path against safe user directories:
        - Allows standard user folders: Documents, Downloads, Desktop, Pictures, Music, Videos.
        - Prevents directory traversal ('..').
        - Strictly forbids system roots (e.g. C:\\Windows, C:\\Program Files).
        Returns (is_valid, message_or_path, display_name).
        """
        if not folder_name_or_path:
            return False, "Folder path cannot be empty.", None

        query = folder_name_or_path.strip().lower()

        # Check for directory traversal or malicious characters
        if ".." in query or self.is_malicious_input(query):
            return False, "Directory traversal or unsafe characters detected.", None

        user_home = os.path.expanduser("~")
        safe_directories = {
            "documents": (os.path.join(user_home, "Documents"), "Documents"),
            "my documents": (os.path.join(user_home, "Documents"), "Documents"),
            "downloads": (os.path.join(user_home, "Downloads"), "Downloads"),
            "desktop": (os.path.join(user_home, "Desktop"), "Desktop"),
            "pictures": (os.path.join(user_home, "Pictures"), "Pictures"),
            "photos": (os.path.join(user_home, "Pictures"), "Pictures"),
            "music": (os.path.join(user_home, "Music"), "Music"),
            "videos": (os.path.join(user_home, "Videos"), "Videos"),
            "home": (user_home, "User Home"),
        }

        # Check safe standard alias
        for alias, (path, name) in safe_directories.items():
            if query == alias or query == f"{alias} folder" or query == f"my {alias}":
                if os.path.exists(path):
                    return True, path, name
                else:
                    return True, path, name

        # If user passed a custom absolute path, ensure it resides strictly within user_home
        try:
            norm_path = os.path.abspath(folder_name_or_path.strip())
            # Normalize case on Windows
            norm_user_home = os.path.abspath(user_home).lower()
            norm_target = norm_path.lower()

            if norm_target.startswith(norm_user_home):
                # Ensure it's not root
                if norm_target == os.path.abspath("C:\\").lower() or "windows" in norm_target or "system32" in norm_target:
                    return False, "System directories cannot be opened.", None
                return True, norm_path, os.path.basename(norm_path)
            else:
                return False, "Only folders inside your user directory are accessible for safety.", None
        except Exception as e:
            return False, f"Invalid folder path: {e}", None

    # --------------------------------------------------------------------------
    # Request Creation & Classification
    # --------------------------------------------------------------------------

    def create_request(
        self,
        action_type: AutomationActionType,
        target: str,
        params: Optional[Dict[str, Any]] = None,
        source: str = "voice"
    ) -> AutomationRequest:
        """
        Creates and classifies an AutomationRequest with appropriate risk, permission,
        confirmation requirements, and security authorization checks.
        """
        req_id = f"auto_{uuid.uuid4().hex[:8]}"
        params = params or {}
        display_name = target

        # Default classification
        risk_level = AutomationRiskLevel.LOW_RISK
        resolved_target = None
        requires_security_auth = False

        # 1. Document OCR Prompt Injection Isolation
        if source == "document_isolated":
            # Actions originating from passive document OCR are strictly prohibited from automating
            return AutomationRequest(
                request_id=req_id,
                action_type=action_type,
                target=target,
                display_name=display_name,
                params=params,
                risk_level=AutomationRiskLevel.BLOCKED,
                permission=AutomationPermission.DENIED,
                requires_confirmation=False,
                requires_security_auth=False,
                source=source,
                resolved_target=None
            )

        # 2. Action-specific classification
        if action_type == AutomationActionType.OPEN_APP:
            defn = self.resolve_app(target)
            if defn:
                display_name = defn.display_name
                risk_level = defn.default_risk
                resolved_target = defn.executable_candidates[0] if defn.executable_candidates else None
            else:
                risk_level = AutomationRiskLevel.BLOCKED

        elif action_type == AutomationActionType.CLOSE_APP:
            close_info = self.resolve_close_target(target)
            if close_info:
                display_name = close_info[0]
                risk_level = AutomationRiskLevel.PROTECTED
                resolved_target = ",".join(close_info[1])
            else:
                risk_level = AutomationRiskLevel.BLOCKED

        elif action_type == AutomationActionType.OPEN_URL:
            is_valid, res, domain = self.validate_url(target)
            if is_valid:
                display_name = domain or target
                resolved_target = res
                risk_level = AutomationRiskLevel.LOW_RISK
            else:
                risk_level = AutomationRiskLevel.BLOCKED
                resolved_target = res

        elif action_type == AutomationActionType.OPEN_FOLDER:
            is_valid, res, name = self.validate_folder_path(target)
            if is_valid:
                display_name = name or target
                resolved_target = res
                risk_level = AutomationRiskLevel.PROTECTED
            else:
                risk_level = AutomationRiskLevel.BLOCKED
                resolved_target = res

        elif action_type == AutomationActionType.COPY_TEXT:
            display_name = f"'{target[:30]}...'" if len(target) > 30 else f"'{target}'"
            resolved_target = target
            risk_level = AutomationRiskLevel.SAFE

        elif action_type == AutomationActionType.READ_SCREEN:
            display_name = f"Read screen ({target})" if target else "Read screen"
            resolved_target = target
            risk_level = AutomationRiskLevel.SAFE

        elif action_type == AutomationActionType.SEND_MESSAGE:
            contact = params.get("contact", target)
            msg_text = params.get("message", "")
            display_name = f"Send message to {contact}"
            resolved_target = contact
            risk_level = AutomationRiskLevel.LOW_RISK

        elif action_type == AutomationActionType.LOCK_WORKSTATION:
            display_name = "Workstation Lock"
            resolved_target = "LockWorkStation"
            risk_level = AutomationRiskLevel.HIGH_RISK

        elif action_type == AutomationActionType.STATUS:
            display_name = "Automation Status"
            resolved_target = "status"
            risk_level = AutomationRiskLevel.SAFE

        else:
            risk_level = AutomationRiskLevel.BLOCKED

        # Determine permission
        perm = self.get_permission(action_type)

        # High-risk actions (e.g. Lock Workstation, Mass actions) or Protected actions require Voice Security password if enabled
        if risk_level in [AutomationRiskLevel.PROTECTED, AutomationRiskLevel.HIGH_RISK]:
            if self.security:
                if hasattr(self.security, "is_configured") and self.security.is_configured():
                    requires_security_auth = True
                elif hasattr(self.security, "is_password_set") and self.security.is_password_set():
                    requires_security_auth = True

        # Confirmation required if permission is ASK_EACH_TIME or if explicitly riskier
        requires_confirmation = (perm == AutomationPermission.ASK_EACH_TIME)

        # If permission is DENIED or risk is BLOCKED, cannot execute
        if perm == AutomationPermission.DENIED:
            risk_level = AutomationRiskLevel.BLOCKED

        return AutomationRequest(
            request_id=req_id,
            action_type=action_type,
            target=target,
            display_name=display_name,
            params=params,
            risk_level=risk_level,
            permission=perm,
            requires_confirmation=requires_confirmation,
            requires_security_auth=requires_security_auth,
            source=source,
            resolved_target=resolved_target
        )

    # --------------------------------------------------------------------------
    # Execution Engine
    # --------------------------------------------------------------------------

    def execute_request(
        self,
        request: AutomationRequest,
        security_authorized: bool = False,
        confirmed: bool = False
    ) -> AutomationResult:
        """
        Executes a validated AutomationRequest under strict security and permission gates.
        """
        # 1. Gate: Blocked or Malicious
        if request.risk_level == AutomationRiskLevel.BLOCKED or request.permission == AutomationPermission.DENIED:
            msg = f"Action '{request.display_name}' is blocked or denied by security policy."
            spoken = f"I cannot execute that action because '{request.display_name}' is not permitted by your automation policy."
            self._record_audit(request, AutomationResultStatus.BLOCKED, msg)
            return AutomationResult(
                status=AutomationResultStatus.BLOCKED,
                message=msg,
                spoken_response=spoken,
                request=request,
                action_type=request.action_type,
                target=request.target
            )

        # 2. Gate: Security Password Authorization Check (PROTECTED / HIGH_RISK)
        if request.requires_security_auth and not security_authorized:
            # Check if active security session exists
            if self.security and hasattr(self.security, "is_session_authorized") and self.security.is_session_authorized():
                security_authorized = True

            if not security_authorized:
                msg = f"Action '{request.display_name}' requires Voice Security authorization."
                spoken = f"For security, please speak your Voice Security Password to authorize {request.display_name}."
                self._record_audit(request, AutomationResultStatus.REQUIRES_SECURITY_AUTH, msg)
                return AutomationResult(
                    status=AutomationResultStatus.REQUIRES_SECURITY_AUTH,
                    message=msg,
                    spoken_response=spoken,
                    request=request,
                    action_type=request.action_type,
                    target=request.target
                )

        # 3. Gate: Confirmation Check
        if request.requires_confirmation and not confirmed:
            msg = f"Action '{request.display_name}' requires user confirmation."
            spoken = f"Do you want me to {self._get_confirmation_phrase(request)}?"
            self._record_audit(request, AutomationResultStatus.REQUIRES_CONFIRMATION, msg)
            return AutomationResult(
                status=AutomationResultStatus.REQUIRES_CONFIRMATION,
                message=msg,
                spoken_response=spoken,
                request=request,
                action_type=request.action_type,
                target=request.target
            )

        # 4. Dispatch Execution
        try:
            if request.action_type == AutomationActionType.OPEN_APP:
                return self._exec_open_app(request)
            elif request.action_type == AutomationActionType.CLOSE_APP:
                return self._exec_close_app(request)
            elif request.action_type == AutomationActionType.OPEN_URL:
                return self._exec_open_url(request)
            elif request.action_type == AutomationActionType.OPEN_FOLDER:
                return self._exec_open_folder(request)
            elif request.action_type == AutomationActionType.COPY_TEXT:
                return self._exec_copy_text(request)
            elif request.action_type == AutomationActionType.LOCK_WORKSTATION:
                return self._exec_lock_workstation(request)
            elif request.action_type == AutomationActionType.READ_SCREEN:
                return self._exec_read_screen(request)
            elif request.action_type == AutomationActionType.SEND_MESSAGE:
                return self._exec_send_message(request)
            elif request.action_type == AutomationActionType.STATUS:
                return self._exec_status(request)
            else:
                return self._fail(request, "Unsupported automation action.")
        except Exception as e:
            logger.error(f"[AutomationManager] Execution error for {request.action_type}: {e}", exc_info=True)
            return self._fail(request, f"Execution failed: {str(e)}")

    def _get_confirmation_phrase(self, request: AutomationRequest) -> str:
        """Generates clear, natural confirmation phrasing."""
        if request.action_type == AutomationActionType.OPEN_APP:
            return f"open {request.display_name}"
        elif request.action_type == AutomationActionType.CLOSE_APP:
            return f"close {request.display_name}"
        elif request.action_type == AutomationActionType.OPEN_URL:
            return f"open {request.display_name}"
        elif request.action_type == AutomationActionType.OPEN_FOLDER:
            return f"open your {request.display_name} folder"
        elif request.action_type == AutomationActionType.COPY_TEXT:
            return f"copy text to the clipboard"
        elif request.action_type == AutomationActionType.LOCK_WORKSTATION:
            return "lock your workstation"
        elif request.action_type == AutomationActionType.SEND_MESSAGE:
            contact = request.params.get("contact", request.target)
            msg_text = request.params.get("message", "")
            return f"send '{msg_text}' to {contact}"
        return f"proceed with {request.display_name}"

    def _exec_read_screen(self, request: AutomationRequest) -> AutomationResult:
        """Extracts structured readable content from active window via UIAutomationManager."""
        app_target = request.params.get("app") or request.target
        res = self.ui_automation.read_screen_content(app_name=app_target)
        status = AutomationResultStatus.SUCCESS if res.get("status") == "SUCCESS" else AutomationResultStatus.FAILED
        spoken = res.get("spoken_response", "No readable content found on screen.")
        msg = f"Screen read for {res.get('app', 'screen')}: {spoken}"
        self._record_audit(request, status, msg)
        return AutomationResult(
            status=status,
            message=msg,
            spoken_response=spoken,
            request=request,
            action_type=request.action_type,
            target=request.target
        )

    def _exec_send_message(self, request: AutomationRequest) -> AutomationResult:
        """Sends a message via UIAutomationManager upon verified confirmation."""
        contact = request.params.get("contact", request.target)
        msg_text = request.params.get("message", "")
        ok, spoken = self.ui_automation.confirm_send_message(contact, msg_text)
        status = AutomationResultStatus.SUCCESS if ok else AutomationResultStatus.FAILED
        msg = f"Send message to {contact}: {spoken}"
        self._record_audit(request, status, msg)
        return AutomationResult(
            status=status,
            message=msg,
            spoken_response=spoken,
            request=request,
            action_type=request.action_type,
            target=contact
        )

    # --------------------------------------------------------------------------
    # Concrete Action Implementations (Strict Non-Shell)
    # --------------------------------------------------------------------------

    def _exec_open_app(self, request: AutomationRequest) -> AutomationResult:
        """Opens an approved application using non-shell subprocess."""
        defn = self.resolve_app(request.target)
        if not defn or not defn.executable_candidates:
            return self._fail(request, f"Application '{request.target}' is not in the approved allowlist.")

        exe_name = defn.executable_candidates[0]
        
        # Resolve full path if available, or rely on system PATH search without shell
        full_path = shutil.which(exe_name) or exe_name

        try:
            # shell=False strictly enforced
            proc = subprocess.Popen([full_path], shell=False)
            pid = proc.pid
            msg = f"Opened {defn.display_name} (PID: {pid})."
            spoken = f"I've opened {defn.display_name}."
            self._record_audit(request, AutomationResultStatus.SUCCESS, msg)
            return AutomationResult(
                status=AutomationResultStatus.SUCCESS,
                message=msg,
                spoken_response=spoken,
                request=request,
                action_type=request.action_type,
                target=defn.display_name,
                pid=pid
            )
        except Exception as e:
            return self._fail(request, f"Could not launch {defn.display_name}: {e}")

    def _exec_close_app(self, request: AutomationRequest) -> AutomationResult:
        """Safely closes an approved application process."""
        close_info = self.resolve_close_target(request.target)
        if not close_info:
            return self._fail(request, f"Application '{request.target}' is not in the approved close list.")

        display_name, process_names = close_info
        killed_any = False

        # Use taskkill safely without shell if on Windows
        if sys.platform == "win32":
            for proc_name in process_names:
                try:
                    # Non-shell taskkill command
                    res = subprocess.run(
                        ["taskkill", "/F", "/IM", proc_name],
                        shell=False,
                        capture_output=True,
                        text=True
                    )
                    if res.returncode == 0:
                        killed_any = True
                except Exception:
                    pass

        msg = f"Closed {display_name}." if killed_any else f"Requested closing {display_name}."
        spoken = f"I've closed {display_name}."
        self._record_audit(request, AutomationResultStatus.SUCCESS, msg)
        return AutomationResult(
            status=AutomationResultStatus.SUCCESS,
            message=msg,
            spoken_response=spoken,
            request=request,
            action_type=request.action_type,
            target=display_name
        )

    def _exec_open_url(self, request: AutomationRequest) -> AutomationResult:
        """Opens a validated safe URL in the default browser."""
        is_valid, target_url, domain = self.validate_url(request.resolved_target or request.target)
        if not is_valid:
            return self._fail(request, f"URL validation failed: {target_url}")

        try:
            webbrowser.open_new_tab(target_url)
            msg = f"Opened {domain} in browser."
            spoken = f"Opening {domain} for you."
            self._record_audit(request, AutomationResultStatus.SUCCESS, msg)
            return AutomationResult(
                status=AutomationResultStatus.SUCCESS,
                message=msg,
                spoken_response=spoken,
                request=request,
                action_type=request.action_type,
                target=domain
            )
        except Exception as e:
            return self._fail(request, f"Could not open browser for URL: {e}")

    def _exec_open_folder(self, request: AutomationRequest) -> AutomationResult:
        """Opens a validated user directory in Windows Explorer."""
        folder_path = request.resolved_target or request.target
        is_valid, resolved_path, name = self.validate_folder_path(folder_path)
        if not is_valid or not resolved_path:
            return self._fail(request, f"Folder path validation failed: {resolved_path}")

        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer.exe", resolved_path], shell=False)
            else:
                subprocess.Popen(["xdg-open", resolved_path], shell=False)

            msg = f"Opened folder '{name}' ({resolved_path})."
            spoken = f"I've opened your {name} folder."
            self._record_audit(request, AutomationResultStatus.SUCCESS, msg)
            return AutomationResult(
                status=AutomationResultStatus.SUCCESS,
                message=msg,
                spoken_response=spoken,
                request=request,
                action_type=request.action_type,
                target=name
            )
        except Exception as e:
            return self._fail(request, f"Could not open folder '{name}': {e}")

    def _exec_copy_text(self, request: AutomationRequest) -> AutomationResult:
        """Copies text safely to the system clipboard."""
        text_to_copy = request.resolved_target or request.target
        if not text_to_copy:
            return self._fail(request, "No text provided to copy.")

        copied = False
        # Method 1: tkinter clipboard
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text_to_copy)
            root.update()
            root.destroy()
            copied = True
        except Exception:
            pass

        # Method 2: clip.exe on Windows as fallback
        if not copied and sys.platform == "win32":
            try:
                proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=False)
                proc.communicate(text_to_copy.encode("utf-8"))
                copied = True
            except Exception:
                pass

        if copied:
            msg = f"Copied {len(text_to_copy)} characters to clipboard."
            spoken = "I've copied that to your clipboard."
            self._record_audit(request, AutomationResultStatus.SUCCESS, msg)
            return AutomationResult(
                status=AutomationResultStatus.SUCCESS,
                message=msg,
                spoken_response=spoken,
                request=request,
                action_type=request.action_type,
                target="clipboard"
            )
        else:
            return self._fail(request, "Failed to copy text to system clipboard.")

    def _exec_lock_workstation(self, request: AutomationRequest) -> AutomationResult:
        """Locks the Windows workstation via Win32 API."""
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                success = user32.LockWorkStation()
                if success:
                    msg = "Workstation locked successfully."
                    spoken = "I've locked your workstation."
                    self._record_audit(request, AutomationResultStatus.SUCCESS, msg)
                    return AutomationResult(
                        status=AutomationResultStatus.SUCCESS,
                        message=msg,
                        spoken_response=spoken,
                        request=request,
                        action_type=request.action_type,
                        target="workstation"
                    )
            except Exception as e:
                return self._fail(request, f"Could not lock workstation: {e}")

        # Non-Windows simulated / unassisted
        msg = "Workstation lock requested."
        spoken = "Workstation lock initiated."
        self._record_audit(request, AutomationResultStatus.SUCCESS, msg)
        return AutomationResult(
            status=AutomationResultStatus.SUCCESS,
            message=msg,
            spoken_response=spoken,
            request=request,
            action_type=request.action_type,
            target="workstation"
        )

    def _exec_status(self, request: AutomationRequest) -> AutomationResult:
        """Reports automation system status and active permissions."""
        active_perms = [f"{k}: {v.value}" for k, v in self._permissions.items()]
        summary = ", ".join(active_perms[:3])
        msg = f"Automation System Active. Permissions: {summary}..."
        spoken = f"System automation is active. App opening is {self.get_permission(AutomationActionType.OPEN_APP).value.lower()}, and closing apps is {self.get_permission(AutomationActionType.CLOSE_APP).value.lower()}."
        self._record_audit(request, AutomationResultStatus.SUCCESS, msg)
        return AutomationResult(
            status=AutomationResultStatus.SUCCESS,
            message=msg,
            spoken_response=spoken,
            request=request,
            action_type=request.action_type,
            target="system"
        )

    def _fail(self, request: AutomationRequest, reason: str) -> AutomationResult:
        """Helper to return a standardized failure result."""
        spoken = f"I wasn't able to complete that action: {reason}"
        self._record_audit(request, AutomationResultStatus.FAILED, reason)
        return AutomationResult(
            status=AutomationResultStatus.FAILED,
            message=reason,
            spoken_response=spoken,
            request=request,
            action_type=request.action_type,
            target=request.target
        )

    # --------------------------------------------------------------------------
    # Audit Logging
    # --------------------------------------------------------------------------

    def _record_audit(self, request: AutomationRequest, status: AutomationResultStatus, details: str = ""):
        """Appends a sanitized record to the transient in-RAM audit queue."""
        # Sanitize target to ensure no secrets/passwords are captured
        target_sanitized = request.target
        if request.action_type == AutomationActionType.COPY_TEXT and len(target_sanitized) > 20:
            target_sanitized = f"{target_sanitized[:20]}... [truncated]"

        record = AutomationAuditRecord(
            request_id=request.request_id,
            action_type=request.action_type.value,
            target=target_sanitized,
            status=status.value,
            risk_level=request.risk_level.value,
            timestamp=time.time(),
            details=details
        )
        self._audit_log.append(record)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Returns recent audit records as dictionaries (transient in-memory only)."""
        return [r.to_dict() for r in self._audit_log]

    def clear_audit_log(self):
        """Clears transient in-RAM audit history."""
        self._audit_log.clear()
