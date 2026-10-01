using System;
using System.IO;
using System.Diagnostics;
using System.Windows.Forms;
using System.Reflection;

[assembly: AssemblyTitle("AutoPortal Keeper Uninstaller")]
[assembly: AssemblyCompany("Raman Tondro")]
[assembly: AssemblyProduct("AutoPortal Keeper")]
[assembly: AssemblyCopyright("Copyright © Raman Tondro (@RMNO21)")]
[assembly: AssemblyVersion("3.0.0.0")]
[assembly: AssemblyFileVersion("3.0.0.0")]

namespace AutoPortalUninstall
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            string msg = "آیا مطمئن هستید که می‌خواهید AutoPortal Keeper را به طور کامل از سیستم حذف کنید؟\n\n"
                       + "Are you sure you want to completely uninstall AutoPortal Keeper?\n\n"
                       + "Developer: Raman Tondro (@RMNO21)";
            string title = "Uninstall AutoPortal Keeper | حذف نرم‌افزار";

            DialogResult result = MessageBox.Show(msg, title, MessageBoxButtons.YesNo, MessageBoxIcon.Question);

            if (result == DialogResult.Yes)
            {
                try
                {
                    // 1. Terminate background processes
                    ProcessStartInfo psiKill = new ProcessStartInfo("taskkill", "/F /IM python.exe /FI \"WINDOWTITLE eq AutoPortal*\"")
                    {
                        CreateNoWindow = true,
                        UseShellExecute = false
                    };
                    Process pKill = Process.Start(psiKill);
                    if (pKill != null) { pKill.WaitForExit(2000); }

                    // 2. Remove from Windows Startup
                    string startupFolder = Environment.GetFolderPath(Environment.SpecialFolder.Startup);
                    string startupShortcut = Path.Combine(startupFolder, "AutoPortalKeeper.vbs");
                    if (File.Exists(startupShortcut))
                    {
                        File.Delete(startupShortcut);
                    }

                    // 3. Remove Start Menu folder
                    string startMenu = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
                    string menuFolder = Path.Combine(startMenu, "AutoPortal Keeper");
                    if (Directory.Exists(menuFolder))
                    {
                        Directory.Delete(menuFolder, true);
                    }

                    // 4. Delete app directory with delayed cleanup
                    string installDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AutoPortalKeeper");
                    ProcessStartInfo psiDel = new ProcessStartInfo("cmd.exe", string.Format("/c timeout /t 1 >nul & rd /s /q \"{0}\"", installDir))
                    {
                        CreateNoWindow = true,
                        UseShellExecute = false
                    };
                    Process.Start(psiDel);

                    MessageBox.Show(
                        "برنامه با موفقیت کامل از سیستم شما حذف شد.\n"
                        + "AutoPortal Keeper has been successfully uninstalled from your system.\n\n"
                        + "Developed by Raman Tondro (@RMNO21)",
                        "حذف تکمیل شد | Uninstalled",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show("خطا در هنگام حذف: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }
    }
}
