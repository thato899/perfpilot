export type AIProviderName = "gemini" | "deepseek";

export interface AIConfig {
  provider: AIProviderName;
  model: string;
  apiKey?: string;
}

export interface AIProvider {
  readonly name: AIProviderName;
  generateText(prompt: string): Promise<string>;
}

export interface StructuredGenerationOptions {
  maxRetries?: number;
}

export type StructuredSchema = {
  parse(value: unknown): unknown;
};
