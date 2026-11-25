export interface ClientOptions {
  baseUrl?: string;
  apiKey?: string;
  token?: string;
  timeoutMs?: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp?: string;
}

export interface ChatRequest {
  message: string;
  model?: string;
  sessionId?: string;
  stream?: boolean;
}

export interface ChatResponse {
  reply: string;
  model: string;
  sessionId?: string;
  tokensUsed?: number;
}

export interface StreamChunk {
  content: string;
  index: number;
  finishReason?: string | null;
}

export interface AgentDescriptor {
  id: string;
  name: string;
  status: string;
  workspace: string;
}

export interface GovernanceTicket {
  ticketId: string;
  action: string;
  status: "pending" | "approved" | "rejected";
  createdAt?: string;
}
