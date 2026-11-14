const vscode = require('vscode');
const http = require('http');

const CODEDEE_API_BASE = 'http://127.0.0.1:8000';

/**
 * Call CodeDEE local FastAPI backend
 */
function postRequest(endpoint, payload) {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify(payload);
        const url = new URL(endpoint, CODEDEE_API_BASE);

        const options = {
            hostname: url.hostname,
            port: url.port,
            path: url.pathname,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(data),
            },
            timeout: 180000,
        };

        const req = http.request(options, (res) => {
            let body = '';
            res.on('data', (chunk) => (body += chunk));
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        resolve(JSON.parse(body));
                    } catch (e) {
                        resolve(body);
                    }
                } else {
                    reject(new Error(`API Error: ${res.statusCode} - ${body}`));
                }
            });
        });

        req.on('error', (e) => reject(e));
        req.on('timeout', () => {
            req.destroy();
            reject(new Error('CodeDEE Server request timed out.'));
        });

        req.write(data);
        req.end();
    });
}

/**
 * Extension Activation Entrypoint
 */
function activate(context) {
    let currentPanel = undefined;

    // Command: Scan Current Active File
    let scanDisposable = vscode.commands.registerCommand('codedee.scanCurrentFile', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('No active editor open to scan.');
            return;
        }

        const document = editor.document;
        const code = document.getText();
        const lang = document.languageId;

        vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'CodeDEE: Scanning with Tree-sitter & Neural Oracle...',
                cancellable: false,
            },
            async (progress) => {
                try {
                    const result = await postRequest('/api/v1/analyze', {
                        code: code,
                        language: lang,
                        enable_oracle: true,
                    });

                    // Open or update Webview panel
                    if (!currentPanel) {
                        currentPanel = vscode.window.createWebviewPanel(
                            'codedeeDashboard',
                            'CodeDEE Security & Quality Report',
                            vscode.ViewColumn.Beside,
                            { enableScripts: true }
                        );
                        currentPanel.onDidDispose(() => (currentPanel = undefined), null, context.subscriptions);
                    }

                    currentPanel.webview.html = getWebviewContent(result, document.fileName);

                    // Handle messages from Webview (e.g. Request AI Patches & Apply Diff)
                    currentPanel.webview.onDidReceiveMessage(
                        async (message) => {
                            if (message.command === 'requestPatches') {
                                vscode.window.withProgress(
                                    {
                                        location: vscode.ProgressLocation.Notification,
                                        title: 'CodeDEE: Generating Multi-Gate Verified Patches...',
                                    },
                                    async () => {
                                        try {
                                            const patchRes = await postRequest('/api/v1/request-patches', {
                                                code_slice: message.vuln.code_slice,
                                                language: lang,
                                                cwe_id: message.vuln.cwe_id,
                                                source_param: message.vuln.source_param,
                                                sink_callee: message.vuln.sink_callee,
                                            });

                                            currentPanel.webview.postMessage({
                                                command: 'displayPatches',
                                                patches: patchRes.patches,
                                            });
                                        } catch (err) {
                                            vscode.window.showErrorMessage(`Patch generation failed: ${err.message}`);
                                        }
                                    }
                                );
                            } else if (message.command === 'applyPatch') {
                                const edit = new vscode.WorkspaceEdit();
                                const fullRange = new vscode.Range(
                                    document.positionAt(0),
                                    document.positionAt(code.length)
                                );
                                // In production, replace specific function slice
                                edit.replace(document.uri, fullRange, message.fixedCode);
                                await vscode.workspace.applyEdit(edit);
                                vscode.window.showInformationMessage('CodeDEE: Patch applied to editor successfully!');
                            }
                        },
                        undefined,
                        context.subscriptions
                    );
                } catch (err) {
                    vscode.window.showErrorMessage(
                        `CodeDEE Scan failed: Make sure server is running at ${CODEDEE_API_BASE}. (${err.message})`
                    );
                }
            }
        );
    });

    context.subscriptions.push(scanDisposable);
}

function getWebviewContent(report, fileName) {
    const metrics = report.maintainability || {};
    const vulns = report.vulnerabilities || [];

    const vulnCards = vulns
        .map(
            (v, idx) => `
        <div class="card ${v.status === 'CONFIRMED' ? 'danger' : 'warning'}">
            <div class="badge ${v.risk_level ? v.risk_level.toLowerCase() : 'med'}">${v.risk_level || 'Medium'}</div>
            <h3>[${v.cwe_id}] ${v.function_name}()</h3>
            <p><strong>Source Parameter:</strong> <code>${v.source_param}</code></p>
            <p><strong>Sensitive Sink:</strong> <code>${v.sink_callee}</code> (Line ${v.sink_line})</p>
            <p><strong>Taint Flow:</strong> ${v.taint_path.join(' &rarr; ')}</p>
            <p class="reason">${v.reason}</p>
            <button class="btn fix-btn" onclick="requestPatches(${idx})">Request AI Patches (Multi-Gate Verifier)</button>
            <div id="patches-container-${idx}" class="patches-container"></div>
        </div>
    `
        )
        .join('');

    return `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 20px; color: var(--vscode-editor-foreground); background-color: var(--vscode-editor-background); }
            h2 { border-bottom: 1px solid var(--vscode-widget-border); padding-bottom: 8px; }
            .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 25px; }
            .stat-box { background: var(--vscode-editorWidget-background); padding: 12px; border-radius: 6px; border: 1px solid var(--vscode-widget-border); }
            .stat-val { font-size: 22px; font-weight: bold; color: var(--vscode-textLink-foreground); }
            .card { background: var(--vscode-editorWidget-background); border-left: 4px solid #4CAF50; padding: 16px; margin-bottom: 16px; border-radius: 4px; }
            .card.danger { border-left-color: #f44336; }
            .card.warning { border-left-color: #ff9800; }
            .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; text-transform: uppercase; margin-bottom: 8px; background: #333; color: #fff; }
            .badge.critical, .badge.high { background: #d32f2f; }
            .badge.medium { background: #f57c00; }
            .btn { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 500; }
            .btn:hover { background: var(--vscode-button-hoverBackground); }
            .patches-container { margin-top: 15px; }
            pre { background: var(--vscode-textCodeBlock-background); padding: 10px; border-radius: 4px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h2>CodeDEE Quality & Security Report</h2>
        <p>File: <code>${fileName}</code> | Language: <strong>${report.language}</strong></p>

        <h3>Maintainability Metrics (ISO/IEC 25010)</h3>
        <div class="grid">
            <div class="stat-box"><div>Source Lines (SLOC)</div><div class="stat-val">${metrics.file_sloc || 0}</div></div>
            <div class="stat-box"><div>Comment Density</div><div class="stat-val">${metrics.comment_density || 0}%</div></div>
            <div class="stat-box"><div>Module Coupling (Ce)</div><div class="stat-val">${metrics.module_coupling_ce || 0}</div></div>
            <div class="stat-box"><div>Duplicated Blocks</div><div class="stat-val">${metrics.duplicated_blocks_count || 0}</div></div>
        </div>

        <h3>Detected Security Findings (${vulns.length})</h3>
        ${vulnCards || '<p>No vulnerabilities detected. All taint paths neutralized or safe!</p>'}

        <script>
            const vscode = acquireVsCodeApi();
            const rawVulns = ${JSON.stringify(vulns)};

            function requestPatches(idx) {
                const v = rawVulns[idx];
                vscode.postMessage({ command: 'requestPatches', vuln: v, index: idx });
                const container = document.getElementById('patches-container-' + idx);
                container.innerHTML = '<p>Generating 3-4 candidate fixes & verifying through Multi-Gate (Gates 1, 2, 3, 4, 6)...</p>';
            }

            window.addEventListener('message', event => {
                const msg = event.data;
                if (msg.command === 'displayPatches') {
                    // Render patches in UI
                    const container = document.querySelector('.patches-container');
                    if (msg.patches.length === 0) {
                        container.innerHTML = '<p style="color: #f44336;">No generated patch passed 100% of the verification gates. Rejected for developer safety.</p>';
                        return;
                    }

                    let html = '<h4>100% Multi-Gate Verified Patches (' + msg.patches.length + '):</h4>';
                    msg.patches.forEach((p, i) => {
                        html += '<div style="margin-bottom: 12px; padding: 10px; border: 1px solid #4CAF50; border-radius: 4px;">';
                        html += '<strong>Fix #' + (i + 1) + ': ' + p.description + '</strong>';
                        html += '<pre>' + p.fixed_code + '</pre>';
                        html += '<button class="btn" onclick="applyPatch(' + i + ')">Apply Diff to Editor</button>';
                        html += '</div>';
                    });
                    container.innerHTML = html;
                    window._lastPatches = msg.patches;
                }
            });

            function applyPatch(index) {
                if (window._lastPatches && window._lastPatches[index]) {
                    vscode.postMessage({ command: 'applyPatch', fixedCode: window._lastPatches[index].fixed_code });
                }
            }
        </script>
    </body>
    </html>
    `;
}

function deactivate() {}

module.exports = { activate, deactivate };
