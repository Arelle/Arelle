using FlaUI.Core;
using FlaUI.Core.AutomationElements;
using FlaUI.Core.Conditions;
using FlaUI.Core.Definitions;
using FlaUI.Core.Input;
using FlaUI.Core.Logging;
using FlaUI.Core.Tools;
using FlaUI.Core.WindowsAPI;
using FlaUI.TestUtilities;
using FlaUI.UIA3;
using System.Diagnostics;
using System.Drawing;
using System.IO.Compression;
using System.Text;

namespace ArelleGUITest
{
    [TestFixture]
    public class ArelleGUITests : FlaUITestBase
    {
        protected override ApplicationStartMode ApplicationStartMode => ApplicationStartMode.OncePerTest;
        protected override VideoRecordingMode VideoRecordingMode => VideoRecordingMode.OnePerTest;

        abstract record ExecutionTypeT(string? ArellePath, string ArelleResourcesPath)
        {
            public record Source(string? ArellePath, string ArelleResourcesPath, bool UseVirtualEnv, string PythonExe)
                : ExecutionTypeT(ArellePath, ArelleResourcesPath);
            public record Build(string? ArellePath, string ArelleResourcesPath) : ExecutionTypeT(ArellePath, ArelleResourcesPath);
        }

        readonly ExecutionTypeT ExecutionType;
        Window Window;

        public ArelleGUITests()
        {
            bool useSource = Environment.GetEnvironmentVariable("ARELLE_USE_BUILD") != "true";
            // ARELLE_PATH
            // source - path to checkout
            // portable build - path to extract directory
            // installed build - absent/empty, checks Program Files
            // convert empty string to null to simplify GitHub Actions conditionals
            string? arellePathEnv1 = Environment.GetEnvironmentVariable("ARELLE_PATH");
            string? arellePathEnv = String.IsNullOrEmpty(arellePathEnv1) ? null : arellePathEnv1;
            string? arelleResourcesPathEnv = Environment.GetEnvironmentVariable("ARELLE_RESOURCES_PATH");
            const string sourceRoot = @"..\..\..\..\..\..\..\..\..";
            if (useSource)
            {
                bool inTree = arellePathEnv == null;
                string? arellePath = inTree ? sourceRoot : arellePathEnv;
                string pythonExe = Environment.GetEnvironmentVariable("ARELLE_PYTHON_EXE") ?? Path.Combine(arellePath!, "venv", "Scripts", "python.exe");
                ExecutionType = new ExecutionTypeT.Source(
                    ArellePath: arellePath,
                    ArelleResourcesPath: arelleResourcesPathEnv ?? Path.GetFullPath(Path.Join(sourceRoot, @"tests\integration_tests\ui_tests\resources")),
                    UseVirtualEnv: inTree,
                    PythonExe: pythonExe);
            }
            else
            {
                if (arelleResourcesPathEnv == null)
                {
                    throw new ArgumentNullException("ARELLE_RESOURCES_PATH", "must be specified for non-source runs");
                }
                ExecutionType = new ExecutionTypeT.Build(ArellePath: arellePathEnv, ArelleResourcesPath: arelleResourcesPathEnv);
            }
        }

        protected override AutomationBase GetAutomation()
        {
            Logger.Default.SetLevel(LogLevel.Debug);
            Retry.DefaultTimeout = TimeSpan.FromSeconds(10);
            UIA3Automation automation = new()
            {
                ConnectionTimeout = TimeSpan.FromSeconds(10),
                TransactionTimeout = TimeSpan.FromSeconds(10),
            };
            return automation;
        }

        void OutputDataReceived(object sender, DataReceivedEventArgs e)
        {
            Logger.Default.Debug("stdout: {0}", e.Data);
        }

        void ErrorDataReceived(object sender, DataReceivedEventArgs e)
        {
            Logger.Default.Debug("stderr: {0}", e.Data);
        }

        Process StartProcess(string cmd) => StartProcess(cmd, null);
        Process StartProcess(string cmd, string? args)
        {
            ProcessStartInfo startInfo = args == null ? new(cmd) : new(cmd, args)
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            Process p = new() { StartInfo = startInfo };
            p.OutputDataReceived += OutputDataReceived;
            p.ErrorDataReceived += ErrorDataReceived;
            p.Start();
            return p;
        }

        protected override Application StartApplication()
        {
            Directory.CreateDirectory(TestsMediaPath);
            Application app;
            switch (ExecutionType)
            {
            case ExecutionTypeT.Source executionType:
            {
                string arelleGUIPyPath = Path.Combine(executionType.ArellePath!, "arelleGUI.pyw");
                Process parentProcess = StartProcess(executionType.PythonExe, arelleGUIPyPath);
                Process? process = executionType.UseVirtualEnv
                    ? Retry.WhileNull(() =>
                        Process.GetProcessesByName("python").FirstOrDefault(p => GetParentProcessId(p) == parentProcess.Id),
                        timeout: TimeSpan.FromSeconds(10), interval: TimeSpan.FromMilliseconds(500)).Result
                    : parentProcess;
                app = Retry.WhileException(() => Application.Attach(process)).Result;
            };
            break;
            case ExecutionTypeT.Build executionType:
            {
                string programFilesPath = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
                string arelleGUIExePath = Path.Join(executionType.ArellePath ?? Path.Join(programFilesPath, "Arelle"), "arelleGUI.exe");
                Process process = StartProcess(arelleGUIExePath);
                app = Retry.WhileException(() => Application.Attach(process)).Result;
            };
            break;
            default:
                throw new ArgumentException();
            }
            return app;
        }

        [SetUp]
        public void Init()
        {
            Window = Application.GetMainWindow(Automation);
        }

        [TearDown]
        public void LogDebugInformation()
        {
            AutomationElement[] descendants = Window.FindAllDescendants();
            foreach (var d in descendants)
            {
                try
                {
                    StringBuilder sb = new($"name='{d.Name}' type={d.ControlType}");
                    if (d.ControlType == ControlType.Window)
                    {
                        sb.Append($" modal={d.AsWindow().IsModal}");
                    }
                    Logger.Default.Debug(sb.ToString());
                }
                // certain properties might not be available on an element, so log and continue
                catch (Exception e)
                {
                    Logger.Default.Error("error dumping element tree", e);
                }
            }
        }

        [Test]
        public void TestOpen()
        {
            string title = Retry.WhileEmpty(() => Window.Title).Result;
            Assert.That(Window.Title, Does.Contain("arelle"));
        }

        [Test]
        public void TestLoadDocument()
        {
            Logger.Default.Info("start TestLoadDocument");
            Keyboard.TypeSimultaneously(VirtualKeyShort.CONTROL, VirtualKeyShort.KEY_O);
            Wait.UntilInputIsProcessed();
            Logger.Default.Info("find the Open File dialog");
            // more reliable than Window.ModalWindows because that searches all descendants whereas this only searches children
            AutomationElement openFileWindow = Retry.WhileNull(() => Window.FindFirstChild(cf =>
                cf.ByControlType(ControlType.Window).And(new PropertyCondition(Automation.PropertyLibrary.Window.IsModal, true))),
                timeout: TimeSpan.FromSeconds(20)).Result;
            Assert.That(openFileWindow, Is.Not.Null);

            string exampleDocumentPath = Path.Join(ExecutionType.ArelleResourcesPath, "workiva.zip");
            string exampleDocumentEntryPoint = "wk-20220331.htm";
            int nFilesInDocumentZip, indexOfEntryPoint;
            using (ZipArchive archive = ZipFile.OpenRead(exampleDocumentPath))
            {
                nFilesInDocumentZip = archive.Entries.Count;
                indexOfEntryPoint = archive.Entries.Select((e, i) => new { e, i }).Where(x => x.e.Name == exampleDocumentEntryPoint).Single().i;
            }
            ComboBox fileNameComboBox = Retry.WhileNull(
                () => openFileWindow.FindFirstDescendant(cf => cf.ByControlType(ControlType.ComboBox).And(cf.ByName("File name:")))).Result.AsComboBox();
            Logger.Default.Info("enter path to document");
            fileNameComboBox.EditableText = exampleDocumentPath;
            Wait.UntilInputIsProcessed();
            Logger.Default.Info("open document");
            Keyboard.Type(VirtualKeyShort.ENTER);
            Wait.UntilInputIsProcessed();

            Logger.Default.Info("select file inside document archive");
            AutomationElement selectFileFromArchiveWindow = Retry.WhileNull(
                () => Window.FindFirstChild(Automation.ConditionFactory.ByControlType(ControlType.Window))).Result;
            AutomationElement selectFileFromArchivePane = selectFileFromArchiveWindow.FindFirstByXPath("/Pane/Pane/Pane/Pane[1]");
            Mouse.LeftClick(new Point(
                (int)(selectFileFromArchivePane.BoundingRectangle.X + selectFileFromArchivePane.BoundingRectangle.Width / 2.0f),
                (int)(selectFileFromArchivePane.BoundingRectangle.Y
                // +1 for the header, +0.5 to end up in the middle
                + selectFileFromArchivePane.BoundingRectangle.Height * (indexOfEntryPoint + 1.5) / (nFilesInDocumentZip + 1))
            ));
            Keyboard.Type(VirtualKeyShort.TAB, VirtualKeyShort.ENTER);

            Logger.Default.Info("wait for document to load and UI to populate");
            // wait for the panes corresponding to tabs and their content to be created,
            // e.g. Tables/DTS on the left and Fact Table/Fact List on the right.
            Retry.WhileNull(() => Window.FindFirstByXPath("/Pane/Pane/Pane/Pane/Pane/Pane/Pane"), timeout: TimeSpan.FromMinutes(1), ignoreException: true);
            AutomationElement iconsAndMainArea = Window.FindFirstByXPath("/Pane/Pane");
            AutomationElement[] iconsAndMainAreaChildren = iconsAndMainArea.FindAllChildren();
            AutomationElement mainArea = iconsAndMainAreaChildren[0];
            AutomationElement icons = iconsAndMainAreaChildren[1];
            AutomationElement statusBar = iconsAndMainAreaChildren[2];
            AutomationElement[] mainAreaChildren = mainArea.FindAllChildren();
            AutomationElement messagesAreaAndTabBar = mainAreaChildren[0];
            AutomationElement tablesAndFactView = mainAreaChildren[1];
            AutomationElement messagesArea = messagesAreaAndTabBar.FindFirstChild();
            AutomationElement[] tablesAndFactViewChildren = tablesAndFactView.FindAllChildren();
            AutomationElement factViewAndTabBar = tablesAndFactViewChildren[0];
            AutomationElement tablesAndTabBar = tablesAndFactViewChildren[1];
            AutomationElement factView = factViewAndTabBar.FindFirstChild();
            AutomationElement tables = tablesAndTabBar.FindFirstChild();

            Logger.Default.Info("copy presentation structure to clipboard");
            Mouse.RightClick(tables.BoundingRectangle.Center());
            Wait.UntilInputIsProcessed();
            MenuItem copyToClipboardMenuItem = Window.ContextMenu.Items[4];
            copyToClipboardMenuItem.Click();
            Wait.UntilInputIsProcessed();
            Menu copyToClipboardSubMenu = Automation.GetDesktop()
                .FindAllChildren(cf => cf.ByControlType(ControlType.Menu).And(cf.ByProcessId(Application.ProcessId)))
                .Select(e => e.AsMenu())
                .Single(e => e.Items.Length == 3);
            MenuItem copyTableMenuItem = copyToClipboardSubMenu.Items[2];
            copyTableMenuItem.Click();
            Wait.UntilInputIsProcessed();
            Logger.Default.Info("get clipboard text");
            string tableText = GetClipboardText();
            Assert.That(tableText, Is.EqualTo(PRESENTATION_STRUCTURE.Replace("\r", "")));
        }

        static int? GetParentProcessId(Process process)
        {
            return (int?)typeof(Process)
                    .GetProperty("ParentProcessId", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!
                    .GetGetMethod(true)!
                    .Invoke(process, null);
        }

        static string GetClipboardText()
        {
            string s = "";
            Thread t = new(() => { s = System.Windows.Forms.Clipboard.GetText(); });
            t.SetApartmentState(ApartmentState.STA);
            t.Start();
            t.Join();
            return s;
        }

        const string PRESENTATION_STRUCTURE =
@"Table Index
Cover
    Cover Page
Financial Statements
    CONDENSED CONSOLIDATED BALANCE SHEETS
        CONDENSED CONSOLIDATED BALANCE SHEETS (Parenthetical)
    CONDENSED CONSOLIDATED BALANCE SHEETS (Parenthetical)
    CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS
        CONDENSED CONSOLIDATED STATEMENTS OF COMPREHENSIVE LOSS
            CONDENSED CONSOLIDATED STATEMENTS OF CASH FLOWS
    CONDENSED CONSOLIDATED STATEMENTS OF COMPREHENSIVE LOSS
        CONDENSED CONSOLIDATED STATEMENTS OF CASH FLOWS
    CONSOLIDATED STATEMENTS OF CHANGES IN STOCKHOLDERS' EQUITY
    CONDENSED CONSOLIDATED STATEMENTS OF CASH FLOWS
Notes to Financial Statements
    Organization and Significant Accounting Policies
        Organization and Significant Accounting Policies (Policies)
            Organization and Significant Accounting Policies - Accounting Pronouncements (Details)
    Supplemental Consolidated Balance Sheet Information
        Supplemental Consolidated Balance Sheet Information (Tables)
            Supplemental Consolidated Balance Sheet Information - Accrued Expenses and Other Current Liabilities (Details)
    Cash Equivalents and Marketable Securities
        Cash Equivalents and Marketable Securities (Tables)
            Cash Equivalents and Marketable Securities - Schedule of Marketable Securities (Details)
                Cash Equivalents and Marketable Securities - Schedule of Contractual Maturities (Details)
    Fair Value Measurements
        Fair Value Measurements (Tables)
            Fair Value Measurements (Details)
    Convertible Senior Notes
        Convertible Senior Notes (Tables)
            Convertible Senior Notes (Details)
                Convertible Senior Notes - Summary of Convertible Debt (Details)
                    Convertible Senior Notes - Summary of Interest Expense (Details)
    Commitments and Contingencies
    Stock-Based Compensation
        Stock-Based Compensation (Tables)
            Stock-Based Compensation - Expense (Details)
                Stock-Based Compensation - Employee Stock Purchase Plan (Details)
    Revenue Recognition
        Revenue Recognition (Tables)
            Revenue Recognition - Disaggregation of Revenue (Details)
                Revenue Recognition - Deferred Revenue and Transaction Price Allocated to the Remaining Performance Obligations (Details)
    Net Loss Per Share
        Net Loss Per Share (Tables)
            Net Loss Per Share - Earnings Per Share Basic and Diluted (Details)
                Net Loss Per Share - Antidilutive Securities Excluded from Computation of Earnings Per Share (Details)
    Intangible Assets
        Intangible Assets (Tables)
            Intangible Assets - Intangible Asset Components (Details)
                Intangible Assets - Amortization of Intangible Assets by Fiscal Year (Details)
    Subsequent Events
        Subsequent Events (Details)
Accounting Policies
    Organization and Significant Accounting Policies (Policies)
        Organization and Significant Accounting Policies - Accounting Pronouncements (Details)
Notes Tables
    Supplemental Consolidated Balance Sheet Information (Tables)
        Supplemental Consolidated Balance Sheet Information - Accrued Expenses and Other Current Liabilities (Details)
    Cash Equivalents and Marketable Securities (Tables)
        Cash Equivalents and Marketable Securities - Schedule of Marketable Securities (Details)
            Cash Equivalents and Marketable Securities - Schedule of Contractual Maturities (Details)
    Fair Value Measurements (Tables)
        Fair Value Measurements (Details)
    Convertible Senior Notes (Tables)
        Convertible Senior Notes (Details)
            Convertible Senior Notes - Summary of Convertible Debt (Details)
                Convertible Senior Notes - Summary of Interest Expense (Details)
    Stock-Based Compensation (Tables)
        Stock-Based Compensation - Expense (Details)
            Stock-Based Compensation - Employee Stock Purchase Plan (Details)
    Revenue Recognition (Tables)
        Revenue Recognition - Disaggregation of Revenue (Details)
            Revenue Recognition - Deferred Revenue and Transaction Price Allocated to the Remaining Performance Obligations (Details)
    Net Loss Per Share (Tables)
        Net Loss Per Share - Earnings Per Share Basic and Diluted (Details)
            Net Loss Per Share - Antidilutive Securities Excluded from Computation of Earnings Per Share (Details)
    Intangible Assets (Tables)
        Intangible Assets - Intangible Asset Components (Details)
            Intangible Assets - Amortization of Intangible Assets by Fiscal Year (Details)
Notes Details
    Organization and Significant Accounting Policies - Accounting Pronouncements (Details)
    Supplemental Consolidated Balance Sheet Information - Accrued Expenses and Other Current Liabilities (Details)
    Cash Equivalents and Marketable Securities - Schedule of Marketable Securities (Details)
        Cash Equivalents and Marketable Securities - Schedule of Contractual Maturities (Details)
    Cash Equivalents and Marketable Securities - Schedule of Contractual Maturities (Details)
    Cash Equivalents and Marketable Securities - Continuous Unrealized Loss Position (Details)
    Fair Value Measurements (Details)
    Convertible Senior Notes (Details)
        Convertible Senior Notes - Summary of Convertible Debt (Details)
            Convertible Senior Notes - Summary of Interest Expense (Details)
    Convertible Senior Notes - Summary of Convertible Debt (Details)
        Convertible Senior Notes - Summary of Interest Expense (Details)
    Convertible Senior Notes - Summary of Interest Expense (Details)
    Stock-Based Compensation - Expense (Details)
        Stock-Based Compensation - Employee Stock Purchase Plan (Details)
    Stock-Based Compensation - Stock Options (Details)
        Stock-Based Compensation - Restricted Stock Units (Details)
    Stock-Based Compensation - Restricted Stock Units (Details)
    Stock-Based Compensation - Employee Stock Purchase Plan (Details)
    Revenue Recognition - Disaggregation of Revenue (Details)
        Revenue Recognition - Deferred Revenue and Transaction Price Allocated to the Remaining Performance Obligations (Details)
    Revenue Recognition - Deferred Revenue and Transaction Price Allocated to the Remaining Performance Obligations (Details)
    Net Loss Per Share - Earnings Per Share Basic and Diluted (Details)
        Net Loss Per Share - Antidilutive Securities Excluded from Computation of Earnings Per Share (Details)
    Net Loss Per Share - Antidilutive Securities Excluded from Computation of Earnings Per Share (Details)
    Intangible Assets - Intangible Asset Components (Details)
        Intangible Assets - Amortization of Intangible Assets by Fiscal Year (Details)
    Intangible Assets (Details)
    Intangible Assets - Amortization of Intangible Assets by Fiscal Year (Details)
    Subsequent Events (Details)";
    }
}