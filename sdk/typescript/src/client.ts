import {
  AmberClawAPIError,
  AmberClawAuthError,
  AmberClawError,
  AmberClawTimeoutError,
} from "./errors.js";
import type {
  AgentDescriptor,
  ChatRequest,
  ChatResponse,
  ClientOptions,
  GovernanceTicket,
  HealthResponse,
  StreamChunk,
} from "./types.js";

export class AmberClawClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly token?: string;
  private readonly timeoutMs: number;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = (options.baseUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.token = options.token;
    this.timeoutMs = options.timeoutMs ?? 30000;
  }

  private buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    } else if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    return headers;
  }

  private async request<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        ...init,
        headers: {
          ...this.buildHeaders(),
          ...((init.headers as Record<string, string>) || {}),
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        let code = "UNKNOWN_ERROR";
        let message = `HTTP ${response.status}: ${response.statusText}`;
        let requestId: string | undefined;

        try {
          const body = (await response.json()) as any;
          if (body?.error) {
            code = body.error.code || code;
            message = body.error.message || message;
            requestId = body.error.request_id;
          }
        } catch {
          // Non-JSON response
        }

        if (response.status === 401 || response.status === 403) {
          throw new AmberClawAuthError(message, requestId);
        }
        throw new AmberClawAPIError(message, code, response.status, requestId);
      }

      return (await response.json()) as T;
    } catch (err: any) {
      if (err.name === "AbortError") {
        throw new AmberClawTimeoutError(`Request exceeded timeout of ${this.timeoutMs}ms`);
      }
      if (err instanceof AmberClawError) {
        throw err;
      }
      throw new AmberClawError(`Network request failed: ${err.message}`);
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/healthz");
  }

  async chat(req: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>("/api/v1/chat", {
      method: "POST",
      body: JSON.stringify({
        message: req.message,
        model: req.model,
        session_id: req.sessionId,
      }),
    });
  }

  async *chatStream(req: ChatRequest): AsyncIterableIterator<StreamChunk> {
    const url = `${this.baseUrl}/api/v1/chat/stream`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        ...this.buildHeaders(),
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        message: req.message,
        model: req.model,
        session_id: req.sessionId,
      }),
    });

    if (!response.ok || !response.body) {
      throw new AmberClawAPIError(`Stream failed with status ${response.status}`, "STREAM_ERROR", response.status);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let chunkIndex = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const block of lines) {
        const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
        if (dataLine) {
          try {
            const data = JSON.parse(dataLine.slice(6));
            yield {
              content: data.content || "",
              index: chunkIndex++,
              finishReason: data.finish_reason || null,
            };
          } catch {
            yield {
              content: dataLine.slice(6),
              index: chunkIndex++,
              finishReason: null,
            };
          }
        }
      }
    }
  }

  async listAgents(): Promise<AgentDescriptor[]> {
    return this.request<AgentDescriptor[]>("/api/v1/agents");
  }

  async listGovernanceTickets(): Promise<GovernanceTicket[]> {
    return this.request<GovernanceTicket[]>("/api/v1/tickets");
  }

  async approveTicket(ticketId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/v1/tickets/${ticketId}/approve`, {
      method: "POST",
    });
  }

  async rejectTicket(ticketId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/v1/tickets/${ticketId}/reject`, {
      method: "POST",
    });
  }
}
