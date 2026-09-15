import type { AIConfig, AIProvider, StructuredGenerationOptions, StructuredSchema } from "./types.js";
import { GeminiProvider } from "./gemini-provider.js";

export class AIService {
  private readonly provider: AIProvider;

  constructor(configOrProvider: AIConfig | AIProvider) {
    if ("generateText" in configOrProvider) {
      this.provider = configOrProvider;
      return;
    }

    switch (configOrProvider.provider) {
      case "gemini":
        this.provider = new GeminiProvider(configOrProvider);
        break;
      case "deepseek":
        throw new Error("DeepSeek provider is not implemented yet in this repository.");
      default:
        throw new Error(`Unsupported AI provider: ${(configOrProvider as { provider?: string }).provider}`);
    }
  }

  async generateText(prompt: string): Promise<string> {
    return this.provider.generateText(prompt);
  }

  async generateStructured<T>(
    prompt: string,
    schema: StructuredSchema,
    options: StructuredGenerationOptions = {},
  ): Promise<T> {
    const maxRetries = options.maxRetries ?? 1;
    let attempts = 0;

    while (attempts <= maxRetries) {
      const raw = await this.provider.generateText(prompt);

      try {
        const parsed = JSON.parse(raw);
        return schema.parse(parsed) as T;
      } catch (error) {
        attempts += 1;
        if (attempts > maxRetries) {
          throw error;
        }
      }
    }

    throw new Error("Structured generation failed after retries.");
  }
}
