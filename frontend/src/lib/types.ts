export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  searchUsed?: boolean;
  citations?: CitationItem[];
  source?: "web" | "telegram";
  id?: number;
}

export interface PlannerData {
  needs_search: boolean;
  reasoning: string;
  search_queries: string[];
  query_type: "temporal" | "factual" | "conversational";
}

export interface SearchingData {
  query: string;
  status: "searching" | "done";
  results_count?: number;
}

export interface ChunkData {
  content: string;
}

export interface CitationItem {
  index: number;
  title: string;
  url: string;
  snippet: string;
}

export interface CitationsData {
  citations: CitationItem[];
}

export interface VerificationData {
  is_consistent: boolean;
  confidence: number;
  issues: string[];
  suggestion: string;
}

export type SSEEvent =
  | { event: "planner"; data: PlannerData }
  | { event: "searching"; data: SearchingData }
  | { event: "chunk"; data: ChunkData }
  | { event: "citations"; data: CitationsData }
  | { event: "search_failed"; data: { message: string } }
  | { event: "verification"; data: VerificationData }
  | { event: "done"; data: Record<string, unknown> }
  | { event: "error"; data: { message: string } };

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  citations?: CitationItem[];
  createdAt: string;
  telegram_chat_id?: number | null;
}
