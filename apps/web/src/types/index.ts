/**
 * TypeScript types for LegalLens frontend
 * Mirrors backend Pydantic schemas from architecture.md §7
 */

// ============================================================================
// Document Types
// ============================================================================

export type DocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed';

export type ProcessingStage = 'extracting_text' | 'ocr' | 'chunking' | 'embedding';

export interface Document {
  id: string;
  owner_id: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  storage_key: string;
  file_hash_sha256: string;
  status: DocumentStatus;
  processing_stage?: ProcessingStage;
  page_count?: number;
  language?: string;
  failure_reason?: string;
  created_at: string;
  updated_at: string;
  chunks?: DocumentChunk[];
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  page_number?: number;
  text: string;
  token_count: number;
  embedding?: number[];
  created_at: string;
}

// ============================================================================
// Clause Types
// ============================================================================

export type ClauseType =
  | 'indemnification'
  | 'termination'
  | 'limitation_of_liability'
  | 'confidentiality'
  | 'non_compete'
  | 'arbitration_dispute_resolution'
  | 'payment_terms'
  | 'auto_renewal'
  | 'governing_law'
  | 'other';

export type RiskLevel = 'low' | 'medium' | 'high';

export interface Clause {
  id: string;
  document_id: string;
  source_chunk_id?: string;
  clause_type: ClauseType;
  text_excerpt: string;
  start_offset: number;
  end_offset: number;
  risk_level: RiskLevel;
  risk_rationale: string;
  created_at: string;
}

// ============================================================================
// Comparison Types
// ============================================================================

export type ComparisonStatus = 'queued' | 'running' | 'completed' | 'failed';

export type MaterialityLevel = 'none' | 'minor' | 'significant' | 'critical';

export interface ComparisonJob {
  id: string;
  owner_id: string;
  status: ComparisonStatus;
  created_at: string;
  completed_at?: string;
}

export interface ComparisonResult {
  id: string;
  comparison_job_id: string;
  clause_type: ClauseType;
  excerpts_by_document: Record<string, string>;
  diff_summary: string;
  materiality: MaterialityLevel;
  created_at: string;
}

// ============================================================================
// Chat Types
// ============================================================================

export interface Citation {
  chunk_id: string;
  page_number: number;
  excerpt: string;
}

export interface ChatSession {
  id: string;
  document_id: string;
  owner_id: string;
  created_at: string;
  last_message_at: string;
}

export type MessageRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  citations?: Citation[];
  created_at: string;
}

// ============================================================================
// Export Types
// ============================================================================

export type ExportType = 'summary' | 'checklist' | 'lawyer_brief' | 'comparison_report';

export type ExportFormat = 'pdf' | 'docx' | 'md';

export type ExportStatus = 'queued' | 'generating' | 'ready' | 'failed';

export interface ExportArtifact {
  id: string;
  owner_id: string;
  document_id?: string;
  comparison_job_id?: string;
  export_type: ExportType;
  file_format: ExportFormat;
  status: ExportStatus;
  storage_key?: string;
  created_at: string;
}

// ============================================================================
// Simplification Types
// ============================================================================

export type ReadingLevel = 'elementary' | 'plain_english' | 'detailed';

export interface SimplificationRequest {
  reading_level?: ReadingLevel;
  scope?: 'full_document' | { clause_id: string };
}

export interface SimplificationResponse {
  simplified_text: string;
  citations: Citation[];
  disclaimer: string;
}

// ============================================================================
// Auth Types
// ============================================================================

export type UserRole = 'user' | 'admin';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ApiError {
  detail: string;
  error_code?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress?: number;
  result?: unknown;
  error?: string;
}

// ============================================================================
// UI-Specific Types
// ============================================================================

export interface DocumentExcerpt {
  documentId: string;
  documentName: string;
  text: string;
  changes?: Array<{
    type: 'added' | 'removed' | 'modified';
    text: string;
  }>;
}

export interface UploadProgress {
  file: File;
  progress: number;
  status: 'uploading' | 'processing' | 'complete' | 'error';
  documentId?: string;
  error?: string;
}
