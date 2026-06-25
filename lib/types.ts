export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type UsageEvent = {
  label: string;
  model?: string;
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
  estimatedTokens?: number;
  costUsd?: number;
};

export type StreamEvent =
  | { type: "status"; message: string }
  | { type: "token"; text: string }
  | {
      type: "usage";
      usage: UsageEvent[];
      totals: {
        estimatedCostUsd: number;
        webFetches: number;
        searches: number;
      };
    }
  | { type: "error"; message: string };
