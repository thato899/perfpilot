import type { AIConfig, AIProvider } from "./types.js";

export class GeminiProvider implements AIProvider {
  readonly name = "gemini" as const;

  private readonly model: string;
  private readonly apiKey: string;
  private readonly endpoint = "https://generativelanguage.googleapis.com/v1beta/models";

  constructor(config: AIConfig) {
    if (!config.apiKey) {
      throw new Error("GEMINI_API_KEY is required to use the Gemini provider.");
    }

    this.model = config.model || "gemini-2.5-flash";
    this.apiKey = config.apiKey;
  }

  async generateText(prompt: string): Promise<string> {
    const requestBody = {
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        responseMimeType: "text/plain",
      },
    };

    const response = await fetch(
      `${this.endpoint}/${this.model}:generateContent?key=${this.apiKey}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      },
    );

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Gemini request failed: ${response.status} ${text}`);
    }

    const payload = (await response.json()) as {
      candidates?: Array<{
        content?: {
          parts?: Array<{ text?: string }>;
        };
      }>;
    };

    const text =
      payload.candidates?.[0]?.content?.parts?.map((part) => part.text ?? "").join("") ?? "";
    return text.trim();
  }
}
