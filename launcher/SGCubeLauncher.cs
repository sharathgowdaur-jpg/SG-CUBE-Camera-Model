using System;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace SGCubeLauncher
{
    static class Program
    {
        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern int GetWindowTextLength(IntPtr hWnd);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool IsWindowVisible(IntPtr hWnd);

        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

        private const int SW_RESTORE = 9;
        private const int SW_SHOW = 5;
        private const int IPC_PORT_GUI = 49152;
        private const string MUTEX_NAME = "Local\\SG_CUBE_APP_PRIMARY_MUTEX";

        private static IntPtr _foundWindow = IntPtr.Zero;

        [STAThread]
        static void Main(string[] args)
        {
            bool createdNew;
            using (Mutex mutex = new Mutex(true, MUTEX_NAME, out createdNew))
            {
                if (!createdNew)
                {
                    // Existing instance running. Bring window forward and/or wake from sleep.
                    TryWakeAndFocusExistingInstance();
                    return;
                }

                string appDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/');

                string pythonExe = ResolvePythonRuntime(appDir);
                if (string.IsNullOrEmpty(pythonExe) || !File.Exists(pythonExe))
                {
                    MessageBox.Show(
                        "Unable to find the Python runtime for SG CUBE.\n\n" +
                        "Checked paths include:\n" +
                        "- " + Path.Combine(appDir, ".venv", "Scripts", "pythonw.exe") + "\n" +
                        "- " + Path.Combine(appDir, "runtime", "Scripts", "pythonw.exe") + "\n" +
                        "- System PATH (pythonw.exe / python.exe)\n\n" +
                        "Please run 'Install-SG-CUBE.bat' or set up your virtual environment.",
                        "SG CUBE — Python Runtime Missing",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning
                    );
                    return;
                }

                string mainScript = Path.Combine(appDir, "visionclaw_gui.py");
                if (!File.Exists(mainScript))
                {
                    MessageBox.Show(
                        "Could not locate the SG CUBE application script:\n" + mainScript,
                        "SG CUBE — Missing Component",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }

                // Build argument string
                StringBuilder argBuilder = new StringBuilder();
                argBuilder.AppendFormat("\"{0}\"", mainScript);

                bool guiSpecified = false;
                foreach (string arg in args)
                {
                    if (arg.StartsWith("--gui")) guiSpecified = true;
                    argBuilder.Append(" ");
                    if (arg.Contains(" ") && !arg.StartsWith("\""))
                    {
                        argBuilder.AppendFormat("\"{0}\"", arg);
                    }
                    else
                    {
                        argBuilder.Append(arg);
                    }
                }

                // Default to web presentation mode if not provided
                if (!guiSpecified)
                {
                    argBuilder.Append(" --gui=web");
                }

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pythonExe;
                psi.Arguments = argBuilder.ToString();
                psi.WorkingDirectory = appDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                psi.WindowStyle = ProcessWindowStyle.Hidden;

                psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
                psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";

                try
                {
                    psi.RedirectStandardError = true;
                    using (Process proc = Process.Start(psi))
                    {
                        if (proc != null)
                        {
                            string stderr = proc.StandardError.ReadToEnd();
                            proc.WaitForExit();
                            if (proc.ExitCode != 0 && !string.IsNullOrEmpty(stderr))
                            {
                                MessageBox.Show(
                                    "SG CUBE encountered an error during startup:\n\n" + stderr,
                                    "SG CUBE — Startup Error",
                                    MessageBoxButtons.OK,
                                    MessageBoxIcon.Error
                                );
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show(
                        "Failed to launch SG CUBE desktop process:\n" + ex.Message,
                        "SG CUBE — Launch Error",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                }
            }
        }

        private static void TryWakeAndFocusExistingInstance()
        {
            // 1. Try sending WAKE signal to IPC port 49152 (in case it is dormant/sleeping)
            try
            {
                using (TcpClient client = new TcpClient())
                {
                    IAsyncResult ar = client.BeginConnect("127.0.0.1", IPC_PORT_GUI, null, null);
                    bool success = ar.AsyncWaitHandle.WaitOne(TimeSpan.FromMilliseconds(500));
                    if (success && client.Connected)
                    {
                        client.EndConnect(ar);
                        using (NetworkStream stream = client.GetStream())
                        {
                            byte[] wakeBytes = Encoding.UTF8.GetBytes("WAKE\n");
                            stream.Write(wakeBytes, 0, wakeBytes.Length);
                            stream.Flush();
                        }
                    }
                }
            }
            catch
            {
                // IPC wake optional if already active
            }

            // 2. Find and bring window to front
            _foundWindow = IntPtr.Zero;
            EnumWindows(EnumWindowCallback, IntPtr.Zero);

            if (_foundWindow != IntPtr.Zero)
            {
                ShowWindow(_foundWindow, SW_RESTORE);
                SetForegroundWindow(_foundWindow);
            }
        }

        private static bool EnumWindowCallback(IntPtr hWnd, IntPtr lParam)
        {
            int length = GetWindowTextLength(hWnd);
            if (length > 0)
            {
                StringBuilder builder = new StringBuilder(length + 1);
                GetWindowText(hWnd, builder, builder.Capacity);
                string title = builder.ToString();

                if ((title.IndexOf("SG CUBE", StringComparison.OrdinalIgnoreCase) >= 0 ||
                     title.IndexOf("VisionClaw", StringComparison.OrdinalIgnoreCase) >= 0) &&
                    title.IndexOf("Backend Engine", StringComparison.OrdinalIgnoreCase) < 0)
                {
                    _foundWindow = hWnd;
                    return false; // Stop enumeration
                }
            }
            return true;
        }

        private static string ResolvePythonRuntime(string appDir)
        {
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string installedDir = Path.Combine(localAppData, "Programs", "SG-CUBE");

            string[] candidates = new string[]
            {
                // App directory runtimes (silent pythonw first)
                Path.Combine(appDir, ".venv", "Scripts", "pythonw.exe"),
                Path.Combine(appDir, "runtime", "Scripts", "pythonw.exe"),
                Path.Combine(appDir, "runtime", "pythonw.exe"),
                Path.Combine(appDir, ".venv", "Scripts", "python.exe"),
                Path.Combine(appDir, "runtime", "Scripts", "python.exe"),
                Path.Combine(appDir, "runtime", "python.exe"),

                // Installed directory runtimes
                Path.Combine(installedDir, ".venv", "Scripts", "pythonw.exe"),
                Path.Combine(installedDir, "runtime", "Scripts", "pythonw.exe"),
                Path.Combine(installedDir, "runtime", "pythonw.exe"),
                Path.Combine(installedDir, ".venv", "Scripts", "python.exe"),
                Path.Combine(installedDir, "runtime", "Scripts", "python.exe"),
                Path.Combine(installedDir, "runtime", "python.exe"),
            };

            foreach (string candidate in candidates)
            {
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }

            // Check PATH for pythonw.exe or python.exe
            string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
            string[] paths = pathEnv.Split(Path.PathSeparator);

            foreach (string dir in paths)
            {
                if (string.IsNullOrEmpty(dir)) continue;
                string pw = Path.Combine(dir, "pythonw.exe");
                if (File.Exists(pw)) return pw;
            }

            foreach (string dir in paths)
            {
                if (string.IsNullOrEmpty(dir)) continue;
                string p = Path.Combine(dir, "python.exe");
                if (File.Exists(p)) return p;
            }

            return null;
        }
    }
}
