import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { AIService } from "../src/ai-service";
import { GeminiProvider } from "../src/gemini-provider";
import { resolveAIConfig } from "../src/config";

describe("resolveAIConfig", () => {
  it("reads provider and model from the environment", () => {
    const config = resolveAIConfig({
      AI_PROVIDER: "gemini",
      AI_PROVIDER_MODEL: "gemini-2.5-flash",
      GEMINI_API_KEY: "test-key",
    });

    expect(config.provider).toBe("gemini");
    expect(config.model).toBe("gemini-2.5-flash");
    expect(config.apiKey).toBe("test-key");
  });
});

describe("GeminiProvider", () => {
  it("calls the Gemini REST API and returns text", async () => {
    const originalFetch = global.fetch;
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        candidates: [{ content: { parts: [{ text: "hello from gemini" }] } }],
      }),
    });

    global.fetch = fetchMock as typeof fetch;

    try {
      const provider = new GeminiProvider({ provider: "gemini", model: "gemini-2.5-flash", apiKey: "test-key" });
      const result = await provider.generateText("hello");

      expect(result).toBe("hello from gemini");
      expect(fetchMock).toHaveBeenCalledTimes(1);
    } finally {
      global.fetch = originalFetch;
    }
  });
});

describe("AIService", () => {
  it("retries once when the structured payload fails validation", async () => {
    const provider = {
      name: "gemini",
      generateText: vi
        .fn()
        .mockResolvedValueOnce('{"status":"ok"}')
        .mockResolvedValueOnce('{"status":"ok","confidence":0.91}'),
    };

    const service = new AIService(provider as any);

    const result = await service.generateStructured(
      "Return a JSON result",
      z.object({
        status: z.string(),
        confidence: z.number(),
      }),
    );

    expect(result).toEqual({ status: "ok", confidence: 0.91 });
    expect(provider.generateText).toHaveBeenCalledTimes(2);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});
