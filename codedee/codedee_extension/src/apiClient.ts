/**
 * apiClient.ts - REST API client for communicating with the CodeDEE backend.
 */

import {
  ApplyPatchResponse,
  GeneratePatchesResponse,
  ScanResponse,
} from './types';

export class CodeDeeApiClient {
  constructor(private baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  public setBaseUrl(url: string): void {
    this.baseUrl = url.replace(/\/+$/, '');
  }

  public async checkHealth(): Promise<{
    status: string;
    ollama_reachable: boolean;
    model_available: boolean;
    model_name: string;
  }> {
    const url = `${this.baseUrl}/health`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Health check failed with status ${res.status}: ${res.statusText}`);
    }
    return (await res.json()) as any;
  }

  public async scanCode(params: {
    targetPath?: string;
    codeContent?: string;
    fileName?: string;
    language?: string;
  }): Promise<ScanResponse> {
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

    return (await res.json()) as ScanResponse;
  }

  public async generatePatches(params: {
    issueId: string;
    targetFile?: string;
    codeContent?: string;
    candidateCount?: number;
  }): Promise<GeneratePatchesResponse> {
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

    return (await res.json()) as GeneratePatchesResponse;
  }

  public async applyPatch(params: {
    targetFile: string;
    patchId: string;
    diff: string;
    remediatedCode?: string;
    createBackup?: boolean;
  }): Promise<ApplyPatchResponse> {
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

    return (await res.json()) as ApplyPatchResponse;
  }
}
