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
      const requestPrompt = attempts === 0 ? prompt : this.buildRetryPrompt(prompt, attempts);
      const raw = await this.provider.generateText(requestPrompt);

      try {
        const parsed = JSON.parse(raw);
        return schema.parse(parsed) as T;
      } catch (error) {
        attempts += 1;
        if (attempts > maxRetries) {
          throw error;
        }

        const validationError = error instanceof Error ? error.message : String(error);
        const retryPrompt = this.buildRetryPrompt(prompt, attempts, validationError);
        // The model only gets the plain prompt on the first attempt; subsequent
        // attempts include the actual validation error so it can fix the issue.
        const generated = await this.provider.generateText(retryPrompt);
        const parsed = JSON.parse(generated);
        return schema.parse(parsed) as T;
      }
    }

    throw new Error("Structured generation failed after retries.");
  }

  private buildRetryPrompt(prompt: string, attempts: number, validationError?: string): string {
    return `Your previous response failed schema validation.

Validation error:
${validationError ?? `retry attempt ${attempts}`}

Return only valid JSON.

Original request:
${prompt}
`;
  }
}
