/**
 * diffProvider.ts - In-memory virtual document provider for side-by-side patch diffing.
 */

import * as vscode from 'vscode';

export class CodeDeeDiffContentProvider implements vscode.TextDocumentContentProvider {
  public static readonly scheme = 'codedee-patch';

  private contentMap = new Map<string, string>();
  private onDidChangeEmitter = new vscode.EventEmitter<vscode.Uri>();

  public readonly onDidChange = this.onDidChangeEmitter.event;

  public setContent(uri: vscode.Uri, content: string): void {
    this.contentMap.set(uri.toString(), content);
    this.onDidChangeEmitter.fire(uri);
  }

  public provideTextDocumentContent(uri: vscode.Uri): string {
    return this.contentMap.get(uri.toString()) || '';
  }

  public clear(): void {
    this.contentMap.clear();
  }
}
