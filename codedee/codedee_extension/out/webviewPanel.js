"use strict";
/**
 * webviewPanel.ts - Interactive Webview Panel for CodeDEE Findings and Program Repair.
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
exports.CodeDeeWebviewPanel = void 0;
const vscode = __importStar(require("vscode"));
const diffProvider_1 = require("./diffProvider");
class CodeDeeWebviewPanel {
    extensionUri;
    apiClient;
    diffProvider;
    static currentPanel;
    panel;
    disposables = [];
    currentScan;
    currentPatches = new Map();
    static createOrShow(extensionUri, apiClient, diffProvider) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;
        if (CodeDeeWebviewPanel.currentPanel) {
            CodeDeeWebviewPanel.currentPanel.panel.reveal(column);
            return CodeDeeWebviewPanel.currentPanel;
        }
        const panel = vscode.window.createWebviewPanel('codedeeFindings', 'CodeDEE Security & Quality Findings', column || vscode.ViewColumn.Beside, {
            enableScripts: true,
            retainContextWhenHidden: true,
            localResourceRoots: [extensionUri],
        });
        CodeDeeWebviewPanel.currentPanel = new CodeDeeWebviewPanel(panel, extensionUri, apiClient, diffProvider);
        return CodeDeeWebviewPanel.currentPanel;
    }
    constructor(panel, extensionUri, apiClient, diffProvider) {
        this.extensionUri = extensionUri;
        this.apiClient = apiClient;
        this.diffProvider = diffProvider;
        this.panel = panel;
        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
        this.updateHtml();
        this.panel.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'requestPatches': {
                    await this.handleRequestPatches(message.issueId, message.targetFile);
                    break;
                }
                case 'viewDiff': {
                    await this.handleViewDiff(message.patchId, message.targetFile);
                    break;
                }
                case 'applyPatch': {
                    await this.handleApplyPatch(message.patchId, message.targetFile);
                    break;
                }
                case 'rescan': {
                    await vscode.commands.executeCommand('codedee.scan');
                    break;
                }
            }
        }, null, this.disposables);
    }
    updateScanResults(scan) {
        this.currentScan = scan;
        this.currentPatches.clear();
        this.updateHtml();
    }
    async handleRequestPatches(issueId, targetFile) {
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `CodeDEE: Generating & Verifying AI Patches for ${issueId}...`,
            cancellable: false,
        }, async () => {
            try {
                // Get content of active editor or file if available
                let codeContent;
                const editor = vscode.window.activeTextEditor;
                if (editor && (editor.document.fileName.includes(targetFile) || !targetFile)) {
                    codeContent = editor.document.getText();
                }
                const res = await this.apiClient.generatePatches({
                    issueId,
                    targetFile,
                    codeContent,
                    candidateCount: 3,
                });
                this.currentPatches.set(issueId, res.verified_patches);
                this.panel.webview.postMessage({
                    command: 'patchesLoaded',
                    issueId,
                    patches: res.verified_patches,
                    verifiedCount: res.verified_count,
                    prunedCount: res.pruned_count,
                });
                vscode.window.showInformationMessage(`CodeDEE: Generated ${res.total_generated} candidates, ${res.verified_count} passed 100% of verification gates.`);
            }
            catch (err) {
                vscode.window.showErrorMessage(`CodeDEE Error generating patches: ${err.message}`);
            }
        });
    }
    async handleViewDiff(patchId, targetFile) {
        try {
            let targetPatch;
            for (const patches of this.currentPatches.values()) {
                const found = patches.find((p) => p.patch_id === patchId);
                if (found) {
                    targetPatch = found;
                    break;
                }
            }
            if (!targetPatch) {
                vscode.window.showErrorMessage(`Patch ${patchId} not found.`);
                return;
            }
            let originalUri;
            if (vscode.window.activeTextEditor && vscode.window.activeTextEditor.document.fileName.includes(targetFile)) {
                originalUri = vscode.window.activeTextEditor.document.uri;
            }
            else {
                originalUri = vscode.Uri.file(targetFile);
            }
            const patchUri = vscode.Uri.parse(`${diffProvider_1.CodeDeeDiffContentProvider.scheme}://preview/${patchId}_${encodeURIComponent(targetFile)}`);
            this.diffProvider.setContent(patchUri, targetPatch.remediated_code);
            const title = `Original vs CodeDEE Verified Fix (${patchId})`;
            await vscode.commands.executeCommand('vscode.diff', originalUri, patchUri, title);
        }
        catch (err) {
            vscode.window.showErrorMessage(`Error opening diff: ${err.message}`);
        }
    }
    async handleApplyPatch(patchId, targetFile) {
        try {
            let targetPatch;
            for (const patches of this.currentPatches.values()) {
                const found = patches.find((p) => p.patch_id === patchId);
                if (found) {
                    targetPatch = found;
                    break;
                }
            }
            if (!targetPatch) {
                vscode.window.showErrorMessage(`Patch ${patchId} not found.`);
                return;
            }
            const res = await this.apiClient.applyPatch({
                targetFile,
                patchId,
                diff: targetPatch.diff,
                remediatedCode: targetPatch.remediated_code,
            });
            vscode.window.showInformationMessage(`CodeDEE: ${res.message} (CST Syntax Validated: ${res.verified_cst_valid})`);
            // Refresh editor document if open
            for (const editor of vscode.window.visibleTextEditors) {
                if (editor.document.fileName.includes(targetFile)) {
                    // Re-read file content into active editor
                    const fileData = await vscode.workspace.fs.readFile(editor.document.uri);
                    const fullRange = new vscode.Range(editor.document.positionAt(0), editor.document.positionAt(editor.document.getText().length));
                    await editor.edit((edit) => {
                        edit.replace(fullRange, new TextDecoder().decode(fileData));
                    });
                    break;
                }
            }
            // Trigger automatic re-scan after applying patch
            await vscode.commands.executeCommand('codedee.scan');
        }
        catch (err) {
            vscode.window.showErrorMessage(`Error applying patch: ${err.message}`);
        }
    }
    dispose() {
        CodeDeeWebviewPanel.currentPanel = undefined;
        this.panel.dispose();
        while (this.disposables.length) {
            const d = this.disposables.pop();
            if (d) {
                d.dispose();
            }
        }
    }
    updateHtml() {
        this.panel.webview.html = this.renderHtmlContent();
    }
    renderHtmlContent() {
        const scan = this.currentScan;
        const issues = scan?.issues || [];
        const m = scan?.maintainability;
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CodeDEE Security & Quality Findings</title>
  <style>
    body {
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif);
      font-size: var(--vscode-font-size, 13px);
      color: var(--vscode-editor-foreground);
      background-color: var(--vscode-editor-background);
      padding: 18px;
      line-height: 1.5;
    }
    h1, h2, h3 {
      font-weight: 600;
      margin-top: 0;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--vscode-widget-border, #454545);
      padding-bottom: 12px;
      margin-bottom: 16px;
    }
    .btn {
      background-color: var(--vscode-button-background, #007acc);
      color: var(--vscode-button-foreground, #ffffff);
      border: none;
      padding: 6px 12px;
      cursor: pointer;
      border-radius: 3px;
      font-size: 12px;
      font-weight: 500;
    }
    .btn:hover {
      background-color: var(--vscode-button-hoverBackground, #0062a3);
    }
    .btn-secondary {
      background-color: var(--vscode-button-secondaryBackground, #3a3d41);
      color: var(--vscode-button-secondaryForeground, #ffffff);
    }
    .btn-secondary:hover {
      background-color: var(--vscode-button-secondaryHoverBackground, #45494e);
    }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
      margin-bottom: 20px;
    }
    .metric-card {
      background: var(--vscode-sideBar-background, #252526);
      border: 1px solid var(--vscode-widget-border, #3c3c3c);
      border-radius: 4px;
      padding: 10px;
      text-align: center;
    }
    .metric-value {
      font-size: 18px;
      font-weight: bold;
      color: var(--vscode-textLink-foreground, #3794ff);
    }
    .metric-label {
      font-size: 11px;
      color: var(--vscode-descriptionForeground, #8c8c8c);
      margin-top: 4px;
    }
    .issue-card {
      background: var(--vscode-sideBar-background, #252526);
      border: 1px solid var(--vscode-widget-border, #3c3c3c);
      border-left: 4px solid var(--vscode-errorForeground, #f14c4c);
      border-radius: 4px;
      padding: 14px;
      margin-bottom: 18px;
    }
    .issue-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 11px;
      font-weight: bold;
      text-transform: uppercase;
    }
    .badge-critical {
      background: rgba(241, 76, 76, 0.2);
      color: #f14c4c;
      border: 1px solid #f14c4c;
    }
    .badge-high {
      background: rgba(255, 140, 0, 0.2);
      color: #ff8c00;
      border: 1px solid #ff8c00;
    }
    .badge-verified {
      background: rgba(78, 201, 176, 0.2);
      color: #4ec9b0;
      border: 1px solid #4ec9b0;
    }
    .taint-flow {
      background: var(--vscode-editor-background);
      border: 1px solid var(--vscode-widget-border, #3c3c3c);
      border-radius: 4px;
      padding: 10px;
      margin: 10px 0;
      font-family: var(--vscode-editor-font-family, monospace);
      font-size: 12px;
    }
    .taint-step {
      display: flex;
      align-items: baseline;
      padding: 4px 0;
    }
    .step-arrow {
      margin: 0 8px;
      color: var(--vscode-textLink-foreground, #3794ff);
    }
    .reasoning-box {
      background: rgba(55, 148, 255, 0.1);
      border-left: 3px solid #3794ff;
      padding: 8px 12px;
      margin: 10px 0;
      font-size: 12px;
    }
    .patch-card {
      background: var(--vscode-editor-background);
      border: 1px solid var(--vscode-widget-border, #3c3c3c);
      border-radius: 4px;
      padding: 12px;
      margin-top: 10px;
    }
    .gate-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0;
    }
    .empty-state {
      text-align: center;
      padding: 40px;
      color: var(--vscode-descriptionForeground);
    }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h2>🛡️ CodeDEE Security Audit & Automated Repair</h2>
      <div style="font-size: 12px; color: var(--vscode-descriptionForeground);">
        Vertical Slice: CWE-89 (SQL Injection) | ISO/IEC 25010 Maintainability
      </div>
    </div>
    <button class="btn" onclick="rescan()">🔍 Re-Scan Active Buffer</button>
  </div>

  ${m
            ? `
  <h3>📊 ISO/IEC 25010 Maintainability Metrics (8 Baseline Metrics)</h3>
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-value">${m.cyclomatic_complexity}</div>
      <div class="metric-label">Cyclomatic Complexity</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${m.cognitive_complexity}</div>
      <div class="metric-label">Cognitive Complexity</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${m.parameter_count}</div>
      <div class="metric-label">Parameter Count</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${m.function_sloc}</div>
      <div class="metric-label">Function SLOC</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${m.file_sloc}</div>
      <div class="metric-label">File SLOC</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${m.module_coupling.Ce} / ${m.module_coupling.Ca}</div>
      <div class="metric-label">Coupling (Ce / Ca)</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${m.duplicated_blocks}</div>
      <div class="metric-label">Duplicated Blocks</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${Math.round(m.comment_density * 100)}%</div>
      <div class="metric-label">Comment Density</div>
    </div>
  </div>
  `
            : ''}

  <h3>🚨 Security Findings (${issues.length})</h3>

  ${issues.length === 0
            ? `
    <div class="empty-state">
      <p>No CWE-89 SQL Injection vulnerabilities detected in current scan target.</p>
      <button class="btn" onclick="rescan()">Run Scan on Current Document</button>
    </div>
  `
            : issues
                .map((issue) => `
    <div class="issue-card" id="card-${issue.issue_id}">
      <div class="issue-header">
        <div>
          <span class="badge badge-critical">${issue.neuro_assessment.risk_level || 'CRITICAL'}</span>
          <strong style="margin-left: 8px;">${issue.symbolic_finding.cwe_id}: ${issue.symbolic_finding.cwe_name}</strong>
        </div>
        <span style="font-size: 11px; color: var(--vscode-descriptionForeground);">Confidence: ${Math.round(issue.neuro_assessment.confidence_score * 100)}%</span>
      </div>

      <div style="font-size: 12px; margin: 4px 0;">
        <strong>Target File:</strong> <code>${issue.target_file}</code>
      </div>

      <div class="reasoning-box">
        <strong>🧠 Neural Oracle Review (qwen2.5-coder:7b + ChromaDB RAG):</strong><br>
        ${issue.neuro_assessment.reasoning}
      </div>

      <div><strong>Symbolic Taint Flow:</strong></div>
      <div class="taint-flow">
        ${issue.symbolic_finding.taint_path
                .map((step) => `
          <div class="taint-step">
            <span class="badge ${step.operation === 'taint_source' ? 'badge-high' : 'badge-critical'}">${step.operation}</span>
            <span style="margin-left: 8px;">Line ${step.line}: <code>${escapeHtml(step.code_snippet || step.symbol)}</code></span>
          </div>
        `)
                .join('')}
      </div>

      <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
        <button class="btn" onclick="requestPatches('${issue.issue_id}', '${escapeHtml(issue.target_file)}')">
          ✨ Request AI Patches (Ollama + Multi-Gate Verifier)
        </button>
      </div>

      <div id="patches-${issue.issue_id}" style="margin-top: 14px;"></div>
    </div>
  `)
                .join('')}

  <script>
    const vscode = acquireVsCodeApi();

    function rescan() {
      vscode.postMessage({ command: 'rescan' });
    }

    function requestPatches(issueId, targetFile) {
      const container = document.getElementById('patches-' + issueId);
      if (container) {
        container.innerHTML = '<div style="padding: 10px; color: var(--vscode-textLink-foreground);">⏳ Generating candidate fixes and executing Multi-Gate verification...</div>';
      }
      vscode.postMessage({ command: 'requestPatches', issueId, targetFile });
    }

    function viewDiff(patchId, targetFile) {
      vscode.postMessage({ command: 'viewDiff', patchId, targetFile });
    }

    function applyPatch(patchId, targetFile) {
      vscode.postMessage({ command: 'applyPatch', patchId, targetFile });
    }

    window.addEventListener('message', event => {
      const msg = event.data;
      if (msg.command === 'patchesLoaded') {
        const container = document.getElementById('patches-' + msg.issueId);
        if (!container) return;

        if (!msg.patches || msg.patches.length === 0) {
          container.innerHTML = '<div style="padding: 8px; color: var(--vscode-errorForeground);">No patches achieved 100% pass across all verification gates.</div>';
          return;
        }

        let html = '<div style="font-weight: 600; margin-bottom: 6px;">100% Multi-Gate Verified Patches (' + msg.patches.length + '):</div>';
        msg.patches.forEach((patch, idx) => {
          html += \`
            <div class="patch-card">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>Candidate #\${idx + 1} (\${patch.patch_id})</strong>
                <span class="badge badge-verified">Δ CC = \${patch.delta_cc}</span>
              </div>
              <div class="gate-list">
                \${patch.passed_gates.map(g => '<span class="badge badge-verified">✓ ' + g + '</span>').join('')}
              </div>
              <p style="font-size: 12px; margin: 6px 0;">\${patch.explanation || 'Verified patch neutralizes SQL injection taint path via parameterization.'}</p>
              <div style="display: flex; gap: 8px; margin-top: 8px;">
                <button class="btn btn-secondary" onclick="viewDiff('\${patch.patch_id}', '\${msg.issueId}')">🔍 View Native Diff</button>
                <button class="btn" onclick="applyPatch('\${patch.patch_id}', '\${msg.issueId}')">🚀 Apply Patch</button>
              </div>
            </div>
          \`;
        });
        container.innerHTML = html;
      }
    });

    function escapeHtml(text) {
      if (!text) return '';
      return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }
  </script>
</body>
</html>`;
    }
}
exports.CodeDeeWebviewPanel = CodeDeeWebviewPanel;
function escapeHtml(text) {
    if (!text)
        return '';
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
//# sourceMappingURL=webviewPanel.js.map