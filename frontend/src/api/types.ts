export interface UploadResponse {
  upload_id: string;
  document_id: string;
  filename: string;
  total_pages: number;
  thumbnails: string[]; // base64 PNG per page
}

export interface DocumentSummary {
  id: string;
  filename: string;
  total_pages: number;
  extracted_pages: number;
  status: string;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
  page: number;
  per_page: number;
}

export interface DocumentDetail {
  id: string;
  filename: string;
  total_pages: number;
  status: string;
  created_at: string;
  pages: Record<string, PageResult & { edited: boolean; updated_at: string }>;
}

export interface Pair {
  key: string;
  value: string;
}

export interface TableSection {
  type: 'table';
  title?: string;
  columns: string[];
  rows: string[][];
}

export interface KeyValueSection {
  type: 'key_value';
  title?: string;
  pairs: Pair[];
}

export interface QAItem {
  question: string;
  answer: string;
}

export interface QAPairSection {
  type: 'qa_pair';
  title?: string;
  items: QAItem[];
}

export interface ParagraphSection {
  type: 'paragraph';
  title?: string;
  text: string;
}

export type Section =
  | KeyValueSection
  | TableSection
  | QAPairSection
  | ParagraphSection;

export interface SectionIssue {
  section_index: number;
  confidence: number;
  issues: string[];
}

export interface Validation {
  overall_confidence: number;
  section_issues: SectionIssue[];
}

export interface PageResult {
  doc_type: string;
  title: string;
  sections: Section[];
  validation: Validation;
}

// SSE event shapes
export type SSEEvent =
  | { type: 'progress';       page: number; stage: 'parsing' | 'validating' }
  | { type: 'result';         page: number; data: PageResult }
  | { type: 'error';          page: number; error: string }
  | { type: 'quota_exceeded'; daily_limit: number; reset_at: string }
  | { type: 'done' };

export type ExportFormat = 'pdf' | 'word' | 'excel' | 'json';
