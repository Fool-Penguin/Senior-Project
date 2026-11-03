"use strict";
/**
 * extension.ts - Entry point for the CodeDEE VS Code Extension.
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const apiClient_1 = require("./apiClient");
const diffProvider_1 = require("./diffProvider");
const webviewPanel_1 = require("./webviewPanel");
let diagnosticCollection;
let statusBarItem;
function activate(context) {
    const config = vscode.workspace.getConfiguration('codedee');
    const serverUrl = config.get('serverUrl', 'http://127.0.0.1:8000');
    const apiClient = new apiClient_1.CodeDeeApiClient(serverUrl);
    const diffProvider = new diffProvider_1.CodeDeeDiffContentProvider();
    // Register virtual document diff provider
    context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider(diffProvider_1.CodeDeeDiffContentProvider.scheme, diffProvider));
    // Diagnostic collection for editor squiggles
    diagnosticCollection = vscode.languages.createDiagnosticCollection('codedee');
    context.subscriptions.push(diagnosticCollection);
    // Status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'codedee.showPanel';
    statusBarItem.text = '$(shield) CodeDEE: Ready';
    statusBarItem.tooltip = 'Click to show CodeDEE findings panel';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);
    // Register command: CodeDEE: Scan Current File / Project
    const scanCommand = vscode.commands.registerCommand('codedee.scan', async () => {
        const editor = vscode.window.activeTextEditor;
        const currentUrl = vscode.workspace.getConfiguration('codedee').get('serverUrl', 'http://127.0.0.1:8000');
        apiClient.setBaseUrl(currentUrl);
        try {
            statusBarItem.text = '$(sync~spin) CodeDEE: Scanning...';
            let targetPath;
            let codeContent;
            let fileName;
            if (editor) {
                targetPath = editor.document.fileName;
                codeContent = editor.document.getText();
                fileName = editor.document.fileName;
            }
            else if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
                targetPath = vscode.workspace.workspaceFolders[0].uri.fsPath;
            }
            else {
                vscode.window.showWarningMessage('CodeDEE: Please open a file or workspace to scan.');
                statusBarItem.text = '$(shield) CodeDEE: Ready';
                return;
            }
            const scanResult = await apiClient.scanCode({
                targetPath,
                codeContent,
                fileName,
            });
            // Update diagnostics in active file
            diagnosticCollection.clear();
            if (editor && scanResult.issues.length > 0) {
                const diagnostics = [];
                for (const issue of scanResult.issues) {
                    const sinkLine = Math.max(0, (issue.symbolic_finding.sink_node.line || 1) - 1);
                    const range = new vscode.Range(sinkLine, 0, sinkLine, 120);
                    const diag = new vscode.Diagnostic(range, `[CWE-89 SQL Injection] ${issue.neuro_assessment.reasoning}`, vscode.DiagnosticSeverity.Error);
                    diag.source = 'CodeDEE';
                    diag.code = issue.issue_id;
                    diagnostics.push(diag);
                }
                diagnosticCollection.set(editor.document.uri, diagnostics);
            }
            // Show/update Webview panel
            const panel = webviewPanel_1.CodeDeeWebviewPanel.createOrShow(context.extensionUri, apiClient, diffProvider);
            panel.updateScanResults(scanResult);
            statusBarItem.text = `$(shield) CodeDEE: ${scanResult.issues_count} flaw(s)`;
            if (scanResult.issues_count > 0) {
                vscode.window.showWarningMessage(`CodeDEE: Detected ${scanResult.issues_count} CWE-89 SQL Injection issue(s). Review in findings panel.`);
            }
            else {
                vscode.window.showInformationMessage('CodeDEE: Zero SQL Injection vulnerabilities found!');
            }
        }
        catch (err) {
            statusBarItem.text = '$(alert) CodeDEE: Error';
            vscode.window.showErrorMessage(`CodeDEE Scan Error: ${err.message}`);
        }
    });
    // Register command: CodeDEE: Show Findings Panel
    const showPanelCommand = vscode.commands.registerCommand('codedee.showPanel', () => {
        webviewPanel_1.CodeDeeWebviewPanel.createOrShow(context.extensionUri, apiClient, diffProvider);
    });
    context.subscriptions.push(scanCommand, showPanelCommand);
}
function deactivate() {
    if (diagnosticCollection) {
        diagnosticCollection.clear();
        diagnosticCollection.dispose();
    }
    if (statusBarItem) {
        statusBarItem.dispose();
    }
}
//# sourceMappingURL=extension.js.map