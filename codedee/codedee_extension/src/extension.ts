/**
 * extension.ts - Entry point for the CodeDEE VS Code Extension.
 */

import * as vscode from 'vscode';
import { CodeDeeApiClient } from './apiClient';
import { CodeDeeDiffContentProvider } from './diffProvider';
import { CodeDeeWebviewPanel } from './webviewPanel';

let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration('codedee');
  const serverUrl = config.get<string>('serverUrl', 'http://127.0.0.1:8000');

  const apiClient = new CodeDeeApiClient(serverUrl);
  const diffProvider = new CodeDeeDiffContentProvider();

  // Register virtual document diff provider
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(
      CodeDeeDiffContentProvider.scheme,
      diffProvider
    )
  );

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
    const currentUrl = vscode.workspace.getConfiguration('codedee').get<string>('serverUrl', 'http://127.0.0.1:8000');
    apiClient.setBaseUrl(currentUrl);

    try {
      statusBarItem.text = '$(sync~spin) CodeDEE: Scanning...';

      let targetPath: string | undefined;
      let codeContent: string | undefined;
      let fileName: string | undefined;

      if (editor) {
        targetPath = editor.document.fileName;
        codeContent = editor.document.getText();
        fileName = editor.document.fileName;
      } else if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
        targetPath = vscode.workspace.workspaceFolders[0].uri.fsPath;
      } else {
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
        const diagnostics: vscode.Diagnostic[] = [];
        for (const issue of scanResult.issues) {
          const sinkLine = Math.max(0, (issue.symbolic_finding.sink_node.line || 1) - 1);
          const range = new vscode.Range(sinkLine, 0, sinkLine, 120);
          const diag = new vscode.Diagnostic(
            range,
            `[CWE-89 SQL Injection] ${issue.neuro_assessment.reasoning}`,
            vscode.DiagnosticSeverity.Error
          );
          diag.source = 'CodeDEE';
          diag.code = issue.issue_id;
          diagnostics.push(diag);
        }
        diagnosticCollection.set(editor.document.uri, diagnostics);
      }

      // Show/update Webview panel
      const panel = CodeDeeWebviewPanel.createOrShow(
        context.extensionUri,
        apiClient,
        diffProvider
      );
      panel.updateScanResults(scanResult);

      statusBarItem.text = `$(shield) CodeDEE: ${scanResult.issues_count} flaw(s)`;

      if (scanResult.issues_count > 0) {
        vscode.window.showWarningMessage(
          `CodeDEE: Detected ${scanResult.issues_count} CWE-89 SQL Injection issue(s). Review in findings panel.`
        );
      } else {
        vscode.window.showInformationMessage('CodeDEE: Zero SQL Injection vulnerabilities found!');
      }
    } catch (err: any) {
      statusBarItem.text = '$(alert) CodeDEE: Error';
      vscode.window.showErrorMessage(`CodeDEE Scan Error: ${err.message}`);
    }
  });

  // Register command: CodeDEE: Show Findings Panel
  const showPanelCommand = vscode.commands.registerCommand('codedee.showPanel', () => {
    CodeDeeWebviewPanel.createOrShow(context.extensionUri, apiClient, diffProvider);
  });

  context.subscriptions.push(scanCommand, showPanelCommand);
}

export function deactivate() {
  if (diagnosticCollection) {
    diagnosticCollection.clear();
    diagnosticCollection.dispose();
  }
  if (statusBarItem) {
    statusBarItem.dispose();
  }
}
