"use strict";
/**
 * apiClient.ts - REST API client for communicating with the CodeDEE backend.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.CodeDeeApiClient = void 0;
class CodeDeeApiClient {
    baseUrl;
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
        this.baseUrl = baseUrl.replace(/\/+$/, '');
    }
    setBaseUrl(url) {
        this.baseUrl = url.replace(/\/+$/, '');
    }
    async checkHealth() {
        const url = `${this.baseUrl}/health`;
        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(`Health check failed with status ${res.status}: ${res.statusText}`);
        }
        return (await res.json());
    }
    async scanCode(params) {
        const url = `${this.baseUrl}/api/scan`;
        const payload = {
            target_path: params.targetPath,
            code_content: params.codeContent,
            file_name: params.fileName,
            language: params.language,
        };
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`Scan request failed (${res.status}): ${errText}`);
        }
        return (await res.json());
    }
    async generatePatches(params) {
        const url = `${this.baseUrl}/api/generate-patches`;
        const payload = {
            issue_id: params.issueId,
            target_file: params.targetFile,
            code_content: params.codeContent,
            candidate_count: params.candidateCount || 3,
        };
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`Patch generation failed (${res.status}): ${errText}`);
        }
        return (await res.json());
    }
    async applyPatch(params) {
        const url = `${this.baseUrl}/api/apply-patch`;
        const payload = {
            target_file: params.targetFile,
            patch_id: params.patchId,
            diff: params.diff,
            remediated_code: params.remediatedCode,
            create_backup: params.createBackup ?? true,
        };
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`Apply patch failed (${res.status}): ${errText}`);
        }
        return (await res.json());
    }
}
exports.CodeDeeApiClient = CodeDeeApiClient;
//# sourceMappingURL=apiClient.js.map