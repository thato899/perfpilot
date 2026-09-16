import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { AIService } from "../src/ai-service.js";
import { GeminiProvider } from "../src/gemini-provider.js";
import { resolveAIConfig } from "../src/config.js";

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

  it("rejects unsupported providers", () => {
    expect(() => resolveAIConfig({ AI_PROVIDER: "banana" })).toThrow("Unsupported AI provider: banana");
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

  it("is callable through AIService", async () => {
    const originalFetch = global.fetch;
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        candidates: [{ content: { parts: [{ text: "hello through service" }] } }],
      }),
    });

    global.fetch = fetchMock as typeof fetch;

    try {
      const service = new AIService({ provider: "gemini", model: "gemini-2.5-flash", apiKey: "test-key" });
      await expect(service.generateText("hello")).resolves.toBe("hello through service");
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
    const retryPrompt = String(provider.generateText.mock.calls[1][0]);
    expect(retryPrompt).toContain("Validation error:");
    expect(retryPrompt).toContain("confidence");
    expect(retryPrompt).toContain("Original request:");
    expect(retryPrompt).toContain("Return a JSON result");
  });

  it("honors multiple retries before succeeding", async () => {
    const provider = {
      name: "gemini",
      generateText: vi
        .fn()
        .mockResolvedValueOnce('{"status":"ok"}')
        .mockResolvedValueOnce('{"status":"still invalid"}')
        .mockResolvedValueOnce('{"status":"ok","confidence":0.91}'),
    };

    const service = new AIService(provider as any);

    const result = await service.generateStructured(
      "Return a JSON result",
      z.object({
        status: z.string(),
        confidence: z.number(),
      }),
      { maxRetries: 2 },
    );

    expect(result).toEqual({ status: "ok", confidence: 0.91 });
    expect(provider.generateText).toHaveBeenCalledTimes(3);
    expect(String(provider.generateText.mock.calls[1][0])).toContain("confidence");
    expect(String(provider.generateText.mock.calls[2][0])).toContain("confidence");
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});
