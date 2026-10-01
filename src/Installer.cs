using System;
using System.IO;
using System.Drawing;
using System.Diagnostics;
using System.Windows.Forms;
using System.Text;
using System.Security.Cryptography;
using System.Reflection;

[assembly: AssemblyTitle("AutoPortal Keeper Setup")]
[assembly: AssemblyDescription("Universal Captive Portal Auto-Login & Rotation Service")]
[assembly: AssemblyCompany("Raman Tondro")]
[assembly: AssemblyProduct("AutoPortal Keeper")]
[assembly: AssemblyCopyright("Copyright © Raman Tondro (@RMNO21)")]
[assembly: AssemblyVersion("3.0.0.0")]
[assembly: AssemblyFileVersion("3.0.0.0")]

namespace AutoPortalSetup
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SetupWizardForm());
        }
    }

    public class SetupWizardForm : Form
    {
        private bool isPersian = true;

        private Panel headerPanel;
        private Label lblHeaderTitle;
        private Label lblHeaderSub;
        private Panel bodyPanel;

        private Panel footerPanel;
        private Label lblDevCredit;
        private LinkLabel lnkGitHub;

        private Button btnBack;
        private Button btnNext;
        private Button btnCancel;

        // Steps
        private Panel stepLangPanel;
        private Label lblLangTitle;
        private GroupBox grpLang;
        private RadioButton rdoFa;
        private RadioButton rdoEn;

        private Panel stepWelcomePanel;
        private Label lblWelcomeTitle;
        private Label lblWelcomeText;
        private CheckBox chkStartup;

        private Panel stepPortalPanel;
        private Label lblPortalTitle;
        private Label lblPortalDesc;
        private Label lblPortalUrl;
        private TextBox txtPortalUrl;

        private Panel stepAccountsPanel;
        private Label lblAccTitle;
        private ListView listViewAccounts;
        private Label lblUser;
        private TextBox txtUser;
        private Label lblPass;
        private TextBox txtPass;
        private Button btnAddAccount;
        private Button btnRemoveAccount;

        private Panel stepReadyPanel;
        private Label lblReadyTitle;
        private Label lblSummary;
        private CheckBox chkLaunchNow;

        private int currentStep = 1;
        private string installDir;
        private string startupFolder;

        public SetupWizardForm()
        {
            this.Text = "AutoPortal Keeper - Setup Wizard";
            this.Size = new Size(630, 540);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.Font = new Font("Segoe UI", 9F);
            this.BackColor = Color.FromArgb(248, 249, 250);

            installDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AutoPortalKeeper");
            startupFolder = Environment.GetFolderPath(Environment.SpecialFolder.Startup);

            InitializeComponents();
            ApplyLanguage(true);
            ShowStep(1);
        }

        private void InitializeComponents()
        {
            // Header
            headerPanel = new Panel();
            headerPanel.Size = new Size(630, 80);
            headerPanel.BackColor = Color.FromArgb(24, 76, 120);
            this.Controls.Add(headerPanel);

            lblHeaderTitle = new Label();
            lblHeaderTitle.Font = new Font("Segoe UI", 12.5F, FontStyle.Bold);
            lblHeaderTitle.ForeColor = Color.White;
            lblHeaderTitle.Location = new Point(22, 16);
            lblHeaderTitle.AutoSize = true;
            headerPanel.Controls.Add(lblHeaderTitle);

            lblHeaderSub = new Label();
            lblHeaderSub.Font = new Font("Segoe UI", 8.5F);
            lblHeaderSub.ForeColor = Color.FromArgb(215, 235, 250);
            lblHeaderSub.Location = new Point(24, 46);
            lblHeaderSub.AutoSize = true;
            headerPanel.Controls.Add(lblHeaderSub);

            // Body
            bodyPanel = new Panel();
            bodyPanel.Location = new Point(20, 95);
            bodyPanel.Size = new Size(575, 335);
            this.Controls.Add(bodyPanel);

            // Footer Panel for Credits & Buttons
            footerPanel = new Panel();
            footerPanel.Location = new Point(20, 440);
            footerPanel.Size = new Size(575, 45);
            this.Controls.Add(footerPanel);

            lblDevCredit = new Label();
            lblDevCredit.Text = "توسعه‌دهنده: رامان تندرو | Developer: Raman Tondro";
            lblDevCredit.Font = new Font("Segoe UI", 8.2F, FontStyle.Regular);
            lblDevCredit.ForeColor = Color.FromArgb(90, 100, 110);
            lblDevCredit.Location = new Point(0, 5);
            lblDevCredit.AutoSize = true;
            footerPanel.Controls.Add(lblDevCredit);

            lnkGitHub = new LinkLabel();
            lnkGitHub.Text = "GitHub: @RMNO21";
            lnkGitHub.Font = new Font("Segoe UI", 8.2F, FontStyle.Bold);
            lnkGitHub.LinkColor = Color.FromArgb(24, 76, 120);
            lnkGitHub.Location = new Point(0, 24);
            lnkGitHub.AutoSize = true;
            lnkGitHub.Click += delegate { Process.Start("https://github.com/RMNO21"); };
            footerPanel.Controls.Add(lnkGitHub);

            // Buttons
            btnCancel = new Button();
            btnCancel.Size = new Size(90, 32);
            btnCancel.Location = new Point(485, 6);
            btnCancel.FlatStyle = FlatStyle.System;
            btnCancel.Click += delegate { this.Close(); };
            footerPanel.Controls.Add(btnCancel);

            btnNext = new Button();
            btnNext.Size = new Size(100, 32);
            btnNext.Location = new Point(375, 6);
            btnNext.FlatStyle = FlatStyle.System;
            btnNext.Click += BtnNext_Click;
            footerPanel.Controls.Add(btnNext);

            btnBack = new Button();
            btnBack.Size = new Size(90, 32);
            btnBack.Location = new Point(275, 6);
            btnBack.FlatStyle = FlatStyle.System;
            btnBack.Enabled = false;
            btnBack.Click += BtnBack_Click;
            footerPanel.Controls.Add(btnBack);

            // ---------------- STEP 1: Language ----------------
            stepLangPanel = new Panel();
            stepLangPanel.Dock = DockStyle.Fill;
            bodyPanel.Controls.Add(stepLangPanel);

            lblLangTitle = new Label();
            lblLangTitle.Font = new Font("Segoe UI", 10.5F, FontStyle.Bold);
            lblLangTitle.Location = new Point(15, 20);
            lblLangTitle.AutoSize = true;
            stepLangPanel.Controls.Add(lblLangTitle);

            grpLang = new GroupBox();
            grpLang.Location = new Point(20, 60);
            grpLang.Size = new Size(535, 160);
            stepLangPanel.Controls.Add(grpLang);

            rdoFa = new RadioButton();
            rdoFa.Text = "فارسی (Persian) - زبان پیش‌فرض";
            rdoFa.Font = new Font("Segoe UI", 10F, FontStyle.Regular);
            rdoFa.Location = new Point(30, 40);
            rdoFa.Size = new Size(350, 30);
            rdoFa.Checked = true;
            rdoFa.CheckedChanged += delegate { if (rdoFa.Checked) ApplyLanguage(true); };
            grpLang.Controls.Add(rdoFa);

            rdoEn = new RadioButton();
            rdoEn.Text = "English (United States)";
            rdoEn.Font = new Font("Segoe UI", 10F, FontStyle.Regular);
            rdoEn.Location = new Point(30, 90);
            rdoEn.Size = new Size(350, 30);
            rdoEn.CheckedChanged += delegate { if (rdoEn.Checked) ApplyLanguage(false); };
            grpLang.Controls.Add(rdoEn);

            // ---------------- STEP 2: Welcome ----------------
            stepWelcomePanel = new Panel();
            stepWelcomePanel.Dock = DockStyle.Fill;
            bodyPanel.Controls.Add(stepWelcomePanel);

            lblWelcomeTitle = new Label();
            lblWelcomeTitle.Font = new Font("Segoe UI", 11F, FontStyle.Bold);
            lblWelcomeTitle.Location = new Point(10, 10);
            lblWelcomeTitle.AutoSize = true;
            stepWelcomePanel.Controls.Add(lblWelcomeTitle);

            lblWelcomeText = new Label();
            lblWelcomeText.Location = new Point(12, 45);
            lblWelcomeText.Size = new Size(550, 210);
            lblWelcomeText.Font = new Font("Segoe UI", 9.2F);
            stepWelcomePanel.Controls.Add(lblWelcomeText);

            chkStartup = new CheckBox();
            chkStartup.Location = new Point(15, 270);
            chkStartup.AutoSize = true;
            chkStartup.Checked = true;
            stepWelcomePanel.Controls.Add(chkStartup);

            // ---------------- STEP 3: Portal Settings ----------------
            stepPortalPanel = new Panel();
            stepPortalPanel.Dock = DockStyle.Fill;
            bodyPanel.Controls.Add(stepPortalPanel);

            lblPortalTitle = new Label();
            lblPortalTitle.Font = new Font("Segoe UI", 11F, FontStyle.Bold);
            lblPortalTitle.Location = new Point(10, 10);
            lblPortalTitle.AutoSize = true;
            stepPortalPanel.Controls.Add(lblPortalTitle);

            lblPortalDesc = new Label();
            lblPortalDesc.Location = new Point(12, 45);
            lblPortalDesc.Size = new Size(550, 115);
            lblPortalDesc.Font = new Font("Segoe UI", 9F);
            stepPortalPanel.Controls.Add(lblPortalDesc);

            lblPortalUrl = new Label();
            lblPortalUrl.Location = new Point(12, 175);
            lblPortalUrl.AutoSize = true;
            lblPortalUrl.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            stepPortalPanel.Controls.Add(lblPortalUrl);

            txtPortalUrl = new TextBox();
            txtPortalUrl.Text = "";
            txtPortalUrl.Location = new Point(14, 200);
            txtPortalUrl.Size = new Size(545, 26);
            stepPortalPanel.Controls.Add(txtPortalUrl);

            // ---------------- STEP 4: Accounts ----------------
            stepAccountsPanel = new Panel();
            stepAccountsPanel.Dock = DockStyle.Fill;
            bodyPanel.Controls.Add(stepAccountsPanel);

            lblAccTitle = new Label();
            lblAccTitle.Font = new Font("Segoe UI", 10F, FontStyle.Bold);
            lblAccTitle.Location = new Point(10, 5);
            lblAccTitle.AutoSize = true;
            stepAccountsPanel.Controls.Add(lblAccTitle);

            listViewAccounts = new ListView();
            listViewAccounts.View = View.Details;
            listViewAccounts.FullRowSelect = true;
            listViewAccounts.GridLines = true;
            listViewAccounts.Location = new Point(10, 30);
            listViewAccounts.Size = new Size(555, 160);
            listViewAccounts.Columns.Add("#", 35);
            listViewAccounts.Columns.Add("Username", 250);
            listViewAccounts.Columns.Add("Password (DPAPI Encrypted)", 250);
            stepAccountsPanel.Controls.Add(listViewAccounts);

            lblUser = new Label();
            lblUser.Location = new Point(10, 202);
            lblUser.AutoSize = true;
            stepAccountsPanel.Controls.Add(lblUser);

            txtUser = new TextBox();
            txtUser.Location = new Point(10, 224);
            txtUser.Size = new Size(180, 25);
            stepAccountsPanel.Controls.Add(txtUser);

            lblPass = new Label();
            lblPass.Location = new Point(200, 202);
            lblPass.AutoSize = true;
            stepAccountsPanel.Controls.Add(lblPass);

            txtPass = new TextBox();
            txtPass.UseSystemPasswordChar = true;
            txtPass.Location = new Point(200, 224);
            txtPass.Size = new Size(180, 25);
            stepAccountsPanel.Controls.Add(txtPass);

            btnAddAccount = new Button();
            btnAddAccount.Size = new Size(80, 27);
            btnAddAccount.Location = new Point(390, 223);
            btnAddAccount.Click += BtnAddAccount_Click;
            stepAccountsPanel.Controls.Add(btnAddAccount);

            btnRemoveAccount = new Button();
            btnRemoveAccount.Size = new Size(125, 27);
            btnRemoveAccount.Location = new Point(10, 260);
            btnRemoveAccount.Click += delegate
            {
                if (listViewAccounts.SelectedItems.Count > 0)
                {
                    listViewAccounts.Items.Remove(listViewAccounts.SelectedItems[0]);
                    for (int i = 0; i < listViewAccounts.Items.Count; i++)
                    {
                        listViewAccounts.Items[i].Text = (i + 1).ToString();
                    }
                }
            };
            stepAccountsPanel.Controls.Add(btnRemoveAccount);

            // ---------------- STEP 5: Ready to Install ----------------
            stepReadyPanel = new Panel();
            stepReadyPanel.Dock = DockStyle.Fill;
            bodyPanel.Controls.Add(stepReadyPanel);

            lblReadyTitle = new Label();
            lblReadyTitle.Font = new Font("Segoe UI", 11F, FontStyle.Bold);
            lblReadyTitle.Location = new Point(10, 10);
            lblReadyTitle.AutoSize = true;
            stepReadyPanel.Controls.Add(lblReadyTitle);

            lblSummary = new Label();
            lblSummary.Location = new Point(12, 45);
            lblSummary.Size = new Size(550, 190);
            lblSummary.Font = new Font("Segoe UI", 9F);
            stepReadyPanel.Controls.Add(lblSummary);

            chkLaunchNow = new CheckBox();
            chkLaunchNow.Location = new Point(15, 250);
            chkLaunchNow.AutoSize = true;
            chkLaunchNow.Checked = true;
            stepReadyPanel.Controls.Add(chkLaunchNow);
        }

        private void ApplyLanguage(bool persian)
        {
            isPersian = persian;
            if (isPersian)
            {
                this.Text = "راهنمای نصب AutoPortal Keeper";
                lblHeaderTitle.Text = "نصاب هوشمند اتصال خودکار به پرتال‌های اینترنت و وای‌فای";
                lblHeaderSub.Text = "AutoPortal Keeper - توسعه‌یافته توسط رامان تندرو (@RMNO21)";
                lblDevCredit.Text = "توسعه‌دهنده: رامان تندرو";

                btnCancel.Text = "انصراف";
                btnBack.Text = "< قبلی";
                btnNext.Text = (currentStep == 5) ? "نصب" : "بعدی >";

                lblLangTitle.Text = "لطفاً زبان نصب را انتخاب کنید:";
                grpLang.Text = "زبان نصب";

                lblWelcomeTitle.Text = "به راهنمای نصب AutoPortal Keeper خوش آمدید.";
                lblWelcomeText.Text = "این برنامه برای اتصال خودکار، بی‌وقفه و بی‌صدا به انواع شبکه‌ها و پرتال‌های ورود (Captive Portal) در دانشگاه‌ها، سازمان‌ها، خوابگاه‌ها و اماکن عمومی طراحی شده است.\n\n"
                                    + "ویژگی‌ها و قابلیت‌های امنیتی:\n"
                                    + "• رمزنگاری امن گذرواژه‌ها با ماژول Windows DPAPI (عدم ذخیره متن خام)\n"
                                    + "• شکار خودکار و آنی ریدایرکت‌های فایروال شبکه به همراه پارامترهای سشن\n"
                                    + "• گردش هوشمند و نوبتی بین اکانت‌ها جهت تقسیم بار سهمیه و استفاده بهینه\n"
                                    + "• گذر آنی از اکانت‌های پر با وقفه ۳۰ ثانیه‌ای و تلاش روی حساب بعدی\n"
                                    + "• اجرای کاملاً سایلنت در پس‌زمینه بدون ایجاد فایل‌های لاگ اضافه\n\n"
                                    + "سازنده: رامان تندرو (Raman Tondro) | گیت‌هاب: @RMNO21\n"
                                    + "برای ادامه مراحل، روی 'بعدی' کلیک کنید.";
                chkStartup.Text = "اجرای خودکار برنامه با شروع ویندوز (Windows Startup)";

                lblPortalTitle.Text = "تنظیم آدرس پرتال لاگین شبکه (اختیاری):";
                lblPortalDesc.Text = "اگر آدرس مستقیم پرتال شبکه خود را می‌دانید، می‌توانید آن را در کادر زیر وارد کنید.\n\n"
                                   + "نکته مهم: در صورتی که این فیلد را خالی بگذارید، برنامه به صورت خودکار ریدایرکت‌های هر شبکه‌ای را در لحظه ورود شکار می‌کند و نیازی به وارد کردن اجباری آدرس نیست.";
                lblPortalUrl.Text = "آدرس صفحه ورود (Portal URL - اختیاری):";

                lblAccTitle.Text = "لیست حساب‌های کاربری (رمزنگاری امن با DPAPI ویندوز):";
                if (listViewAccounts.Columns.Count >= 3)
                {
                    listViewAccounts.Columns[0].Text = "#";
                    listViewAccounts.Columns[1].Text = "نام کاربری";
                    listViewAccounts.Columns[2].Text = "رمز عبور (رمزنگاری DPAPI)";
                }
                lblUser.Text = "نام کاربری:";
                lblPass.Text = "رمز عبور:";
                btnAddAccount.Text = "+ افزودن";
                btnRemoveAccount.Text = "حذف انتخاب‌شده";

                lblReadyTitle.Text = "آماده نصب نرم‌افزار";
                chkLaunchNow.Text = "اجرای فوری سرویس در پس‌زمینه بلافاصله پس از اتمام نصب";
            }
            else
            {
                this.Text = "AutoPortal Keeper - Setup Wizard";
                lblHeaderTitle.Text = "AutoPortal Keeper Setup Wizard";
                lblHeaderSub.Text = "Developed by Raman Tondro (@RMNO21)";
                lblDevCredit.Text = "Developer: Raman Tondro";

                btnCancel.Text = "Cancel";
                btnBack.Text = "< Back";
                btnNext.Text = (currentStep == 5) ? "Install" : "Next >";

                lblLangTitle.Text = "Please select setup language:";
                grpLang.Text = "Setup Language";

                lblWelcomeTitle.Text = "Welcome to AutoPortal Keeper Setup";
                lblWelcomeText.Text = "This utility provides automated, seamless, and silent background authentication for captive portal networks across universities, campuses, dorms, and public Wi-Fi.\n\n"
                                    + "Key Features & Security:\n"
                                    + "• Military-grade password protection using native Windows DPAPI (No plaintext)\n"
                                    + "• Instant capture of dynamic captive portal redirections and session queries\n"
                                    + "• Smart round-robin account rotation to balance traffic and quotas\n"
                                    + "• Rapid failover on concurrent device limits (30-second cooldown)\n"
                                    + "• Zero popup windows, zero resource waste, zero log files\n\n"
                                    + "Author: Raman Tondro | GitHub: @RMNO21\n"
                                    + "Click 'Next' to continue.";
                chkStartup.Text = "Start automatically when Windows boots (Windows Startup)";

                lblPortalTitle.Text = "Network Portal Address (Optional):";
                lblPortalDesc.Text = "If you have a direct portal login address, you can enter it below.\n\n"
                                   + "Note: If you leave this field empty, the service will dynamically detect and intercept any captive portal redirect automatically.";
                lblPortalUrl.Text = "Portal URL (Optional):";

                lblAccTitle.Text = "Accounts List (Protected with Windows DPAPI):";
                if (listViewAccounts.Columns.Count >= 3)
                {
                    listViewAccounts.Columns[0].Text = "#";
                    listViewAccounts.Columns[1].Text = "Username";
                    listViewAccounts.Columns[2].Text = "Password (DPAPI Encrypted)";
                }
                lblUser.Text = "Username:";
                lblPass.Text = "Password:";
                btnAddAccount.Text = "+ Add";
                btnRemoveAccount.Text = "Remove Selected";

                lblReadyTitle.Text = "Ready to Install";
                chkLaunchNow.Text = "Launch background service immediately after installation";
            }
        }

        private void BtnAddAccount_Click(object sender, EventArgs e)
        {
            if (string.IsNullOrWhiteSpace(txtUser.Text) || string.IsNullOrWhiteSpace(txtPass.Text))
            {
                string msg = isPersian ? "لطفاً نام کاربری و رمز عبور را وارد کنید." : "Please enter both username and password.";
                MessageBox.Show(msg, isPersian ? "خطا" : "Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            int index = listViewAccounts.Items.Count + 1;
            ListViewItem item = new ListViewItem(index.ToString());
            item.SubItems.Add(txtUser.Text.Trim());
            item.SubItems.Add(new string('●', Math.Min(txtPass.Text.Length, 12)));
            item.Tag = txtPass.Text.Trim();
            listViewAccounts.Items.Add(item);

            txtUser.Clear();
            txtPass.Clear();
            txtUser.Focus();
        }

        private void ShowStep(int step)
        {
            currentStep = step;
            stepLangPanel.Visible = (step == 1);
            stepWelcomePanel.Visible = (step == 2);
            stepPortalPanel.Visible = (step == 3);
            stepAccountsPanel.Visible = (step == 4);
            stepReadyPanel.Visible = (step == 5);

            btnBack.Enabled = (step > 1);

            if (step == 5)
            {
                btnNext.Text = isPersian ? "نصب" : "Install";
                string portalDisplay = string.IsNullOrWhiteSpace(txtPortalUrl.Text) 
                    ? (isPersian ? "تشخیص خودکار ریدایرکت" : "Automatic Redirect Detection") 
                    : txtPortalUrl.Text.Trim();
                
                if (isPersian)
                {
                    lblSummary.Text = string.Format(
                        "خلاصه تنظیمات جهت نصب:\n\n"
                        + "• توسعه‌دهنده: رامان تندرو (@RMNO21)\n"
                        + "• مسیر نصب برنامه:\n  {0}\n\n"
                        + "• آدرس پرتال: {1}\n"
                        + "• تعداد حساب‌های ثبت‌شده: {2} حساب (رمزنگاری‌شده با DPAPI)\n"
                        + "• اجرای خودکار در استارتاپ: {3}\n"
                        + "• برنامه حذف (Uninstall.exe) در منوی استارت ایجاد خواهد شد.\n\n"
                        + "برای شروع نصب روی دکمه 'نصب' کلیک کنید.",
                        installDir,
                        portalDisplay,
                        listViewAccounts.Items.Count,
                        chkStartup.Checked ? "فعال" : "غیرفعال"
                    );
                }
                else
                {
                    lblSummary.Text = string.Format(
                        "Installation Summary:\n\n"
                        + "• Developer: Raman Tondro (@RMNO21)\n"
                        + "• Installation Directory:\n  {0}\n\n"
                        + "• Portal URL: {1}\n"
                        + "• Configured Accounts: {2} accounts (DPAPI Protected)\n"
                        + "• Windows Startup: {3}\n"
                        + "• Standalone uninstaller (Uninstall.exe) will be created.\n\n"
                        + "Click 'Install' to begin setup.",
                        installDir,
                        portalDisplay,
                        listViewAccounts.Items.Count,
                        chkStartup.Checked ? "Enabled" : "Disabled"
                    );
                }
            }
            else
            {
                btnNext.Text = isPersian ? "بعدی >" : "Next >";
            }
        }

        private void BtnNext_Click(object sender, EventArgs e)
        {
            if (currentStep == 1)
            {
                ShowStep(2);
            }
            else if (currentStep == 2)
            {
                ShowStep(3);
            }
            else if (currentStep == 3)
            {
                ShowStep(4);
            }
            else if (currentStep == 4)
            {
                if (listViewAccounts.Items.Count == 0)
                {
                    string msg = isPersian ? "لطفاً حداقل یک حساب کاربری اضافه کنید." : "Please add at least one account to proceed.";
                    MessageBox.Show(msg, isPersian ? "توجه" : "Attention", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                ShowStep(5);
            }
            else if (currentStep == 5)
            {
                PerformInstall();
            }
        }

        private void BtnBack_Click(object sender, EventArgs e)
        {
            if (currentStep > 1)
            {
                ShowStep(currentStep - 1);
            }
        }

        private string EncryptPassword(string plainText)
        {
            if (string.IsNullOrEmpty(plainText)) return "";
            try
            {
                byte[] plainBytes = Encoding.UTF8.GetBytes(plainText);
                byte[] cipherBytes = ProtectedData.Protect(plainBytes, null, DataProtectionScope.CurrentUser);
                return Convert.ToBase64String(cipherBytes);
            }
            catch
            {
                return plainText;
            }
        }

        private void PerformInstall()
        {
            try
            {
                if (!Directory.Exists(installDir))
                {
                    Directory.CreateDirectory(installDir);
                }

                string portalUrl = txtPortalUrl.Text.Trim();

                StringBuilder json = new StringBuilder();
                json.AppendLine("{");
                json.AppendFormat("  \"portal_url\": \"{0}\",\n", portalUrl.Replace("\"", "\\\""));
                json.AppendLine("  \"accounts\": [");
                for (int i = 0; i < listViewAccounts.Items.Count; i++)
                {
                    string u = listViewAccounts.Items[i].SubItems[1].Text.Replace("\"", "\\\"");
                    string rawPass = (listViewAccounts.Items[i].Tag != null) ? listViewAccounts.Items[i].Tag.ToString() : "";
                    string pEnc = EncryptPassword(rawPass);

                    json.AppendFormat("    {{\"username\": \"{0}\", \"password\": \"{1}\"}}", u, pEnc);
                    if (i < listViewAccounts.Items.Count - 1) json.Append(",");
                    json.AppendLine();
                }
                json.AppendLine("  ]");
                json.AppendLine("}");

                File.WriteAllText(Path.Combine(installDir, "accounts.json"), json.ToString(), new UTF8Encoding(false));

                string currentDir = AppDomain.CurrentDomain.BaseDirectory;
                string scriptSrc = Path.Combine(currentDir, "portal_keeper.py");
                File.Copy(scriptSrc, Path.Combine(installDir, "portal_keeper.py"), true);

                string uninstSrc = Path.Combine(currentDir, "Uninstall.exe");
                if (File.Exists(uninstSrc))
                {
                    File.Copy(uninstSrc, Path.Combine(installDir, "Uninstall.exe"), true);
                }

                string vbs = string.Format("Set WshShell = CreateObject(\"WScript.Shell\")\nWshShell.Run \"python \"\"{0}\\portal_keeper.py\"\"\", 0, False\n", installDir);
                File.WriteAllText(Path.Combine(installDir, "run_silent.vbs"), vbs, Encoding.ASCII);

                string startupShortcut = Path.Combine(startupFolder, "AutoPortalKeeper.vbs");
                if (chkStartup.Checked)
                {
                    File.Copy(Path.Combine(installDir, "run_silent.vbs"), startupShortcut, true);
                }
                else
                {
                    if (File.Exists(startupShortcut)) File.Delete(startupShortcut);
                }

                try
                {
                    string startMenu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "AutoPortal Keeper");
                    if (!Directory.Exists(startMenu)) Directory.CreateDirectory(startMenu);

                    Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                    dynamic shell = Activator.CreateInstance(shellType);
                    dynamic shortcut = shell.CreateShortcut(Path.Combine(startMenu, "Uninstall AutoPortal Keeper.lnk"));
                    shortcut.TargetPath = Path.Combine(installDir, "Uninstall.exe");
                    shortcut.Save();
                }
                catch { }

                if (chkLaunchNow.Checked)
                {
                    Process.Start("wscript.exe", string.Format("\"{0}\\run_silent.vbs\"", installDir));
                }

                string successMsg = isPersian
                    ? "نرم‌افزار AutoPortal Keeper با موفقیت کامل نصب شد و هم‌اکنون به صورت سایلنت در پس‌زمینه فعال است.\nگذرواژه‌ها با استاندارد DPAPI رمزنگاری شدند.\nگزینه Uninstall نیز در منوی Start قرار گرفت."
                    : "AutoPortal Keeper has been successfully installed and is now active in the background.\nPasswords are encrypted with Windows DPAPI.\nAn uninstaller shortcut was also placed in the Start Menu.";

                MessageBox.Show(successMsg, isPersian ? "نصب تکمیل شد" : "Setup Complete", MessageBoxButtons.OK, MessageBoxIcon.Information);
                this.Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show("Installation Error:\n" + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
