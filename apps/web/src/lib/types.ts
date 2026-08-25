export type RAGAnswerRequest = {
  question: string;
  limit?: number;
  filters?: Record<string, unknown> | null;
};

export type RAGAnswerSource = {
  citation: number;
  document_id: string;
  chunk_id: string;
  score: number;
};

export type RAGAnswerResponse = {
  answer: string;
  sanitized_query: string;
  sources: RAGAnswerSource[];
};
