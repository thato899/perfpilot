export type AIEnvironment = {
  AI_PROVIDER?: string;
  AI_PROVIDER_MODEL?: string;
  GEMINI_API_KEY?: string;
  DEEPSEEK_API_KEY?: string;
};

export interface ResolvedAIConfig {
  provider: "gemini" | "deepseek";
  model: string;
  apiKey?: string;
}

export function resolveAIConfig(env: AIEnvironment = process.env): ResolvedAIConfig {
  const provider = (env.AI_PROVIDER ?? "gemini").toLowerCase();
  const normalizedProvider = provider === "deepseek" ? "deepseek" : "gemini";

  const model = env.AI_PROVIDER_MODEL ?? (normalizedProvider === "gemini" ? "gemini-2.5-flash" : "deepseek-chat");
  const apiKey = normalizedProvider === "gemini" ? env.GEMINI_API_KEY : env.DEEPSEEK_API_KEY;

  return {
    provider: normalizedProvider,
    model,
    apiKey,
  };
}
