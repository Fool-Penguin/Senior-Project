/**
 * types.ts - TypeScript contracts matching CodeDEE backend Pydantic schemas.
 */

export interface MaintainabilityMetricsSummary {
  cyclomatic_complexity: number;
  cognitive_complexity: number;
  parameter_count: number;
  function_sloc: number;
  file_sloc: number;
  module_coupling: {
    Ce: number;
    Ca: number;
    instability: number;
  };
  duplicated_blocks: number;
  comment_density: number;
}

export interface CodeLocation {
  file: string;
  line: number;
  column?: number;
  symbol: string;
  expression?: string;
}

export interface TaintStep {
  step_index: number;
  file: string;
  line: number;
  symbol: string;
  operation: string;
  code_snippet?: string;
}

export interface SymbolicFinding {
  cwe_id: string;
  cwe_name: string;
  severity: string;
  source_node: CodeLocation;
  sink_node: CodeLocation;
  taint_path: TaintStep[];
  sanitized: boolean;
  symbolic_confidence: number;
  code_slice?: string;
}

export interface NeuroAssessment {
  confidence_score: number;
  risk_level: string;
  sanitizer_detected: boolean;
  sanitizer_details?: string;
  is_false_positive: boolean;
  reasoning: string;
  flagged_for_review: boolean;
  suggested_remediation?: string;
}

export interface PipelineMetadata {
  scan_timestamp: string;
  file_path: string;
  language: string;
  maintainability_metrics: MaintainabilityMetricsSummary;
  execution_time_ms: number;
  stage: string;
  model_name: string;
}

export interface SecurityNodeOutput {
  issue_id: string;
  target_file: string;
  symbolic_finding: SymbolicFinding;
  neuro_assessment: NeuroAssessment;
  pipeline_metadata: PipelineMetadata;
}

export interface ScanResponse {
  status: string;
  target_path: string;
  files_scanned: number;
  issues_count: number;
  issues: SecurityNodeOutput[];
  maintainability: MaintainabilityMetricsSummary;
  execution_time_ms: number;
}

export interface GateResult {
  passed: boolean;
  details: string;
}

export interface VerifiedPatch {
  patch_id: string;
  diff: string;
  remediated_code: string;
  passed_gates: string[];
  delta_cc: number;
  explanation?: string;
  gate1_syntax?: GateResult;
  gate2_interface?: GateResult;
  gate3_taint_neutralized?: GateResult;
  gate4_maintainability?: GateResult;
  gate6_sast_rescan?: GateResult;
}

export interface GeneratePatchesResponse {
  issue_id: string;
  target_file: string;
  total_generated: number;
  verified_count: number;
  pruned_count: number;
  verified_patches: VerifiedPatch[];
}

export interface ApplyPatchResponse {
  status: string;
  patch_id: string;
  target_file: string;
  backup_file?: string;
  message: string;
  verified_cst_valid: boolean;
}
