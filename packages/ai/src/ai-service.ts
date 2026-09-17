import type {
  AIConfig,
  AIProvider,
  StructuredGenerationOptions,
  StructuredSchema,
} from "./types.js";
import { resolveAIConfig } from "./config.js";
import { GeminiProvider } from "./gemini-provider.js";

export class AIService {
  private readonly provider: AIProvider;

  constructor(configOrProvider: AIConfig | AIProvider = resolveAIConfig()) {
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
        throw new Error(
          `Unsupported AI provider: ${(configOrProvider as { provider?: string }).provider}`,
        );
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
    let lastError: unknown;

    for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
      const requestPrompt = attempt === 0 ? prompt : this.buildRetryPrompt(prompt, lastError);
      const raw = await this.provider.generateText(requestPrompt);

      try {
        const parsed = JSON.parse(raw);
        return schema.parse(parsed) as T;
      } catch (error) {
        lastError = error;
        if (attempt === maxRetries) {
          throw error;
        }
      }
    }

    throw new Error("Structured generation failed after retries.");
  }

  private buildRetryPrompt(prompt: string, error: unknown): string {
    const validationError = error instanceof Error ? error.message : String(error);
    return `Your previous response failed schema validation.

Validation error:
${validationError}

Return only valid JSON.

Original request:
${prompt}
`;
  }
}
