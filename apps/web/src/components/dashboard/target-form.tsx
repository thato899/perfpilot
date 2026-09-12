"use client";

import { useState } from "react";
import type { Target } from "@perfpilot/schemas/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createTarget } from "@/lib/mock-api";

/** "Create a target" — registers an application and records the
 * authorization confirmation required before any load can be sent to it.
 * Mirrors POST /api/projects/{id}/targets (docs/api/api-contract.md) and
 * its security-model.md#target-authorization rule: there is no
 * "confirm later" state, so the checkbox below is required, not optional. */
export function TargetForm({ onCreated }: { onCreated: (target: Target) => void }) {
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [confirmedBy, setConfirmedBy] = useState("");
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!authorizationConfirmed) {
      setError(
        "You must confirm you own/are authorized to test this target — PerfPilot refuses to " +
          "create a target it can't run load against.",
      );
      return;
    }

    setSubmitting(true);
    try {
      const target = await createTarget({
        name,
        baseUrl,
        authorizationConfirmed,
        authorizationConfirmedBy: confirmedBy,
      });
      onCreated(target);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create target.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Register a target</CardTitle>
        <CardDescription>
          The application PerfPilot will investigate. See{" "}
          <code>docs/security/security-model.md</code> for why authorization confirmation is
          required up front.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="target-name">Name</Label>
            <Input
              id="target-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Demo e-commerce app"
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="target-url">Base URL</Label>
            <Input
              id="target-url"
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://demo.perfpilot.local"
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirmed-by">Authorization confirmed by</Label>
            <Input
              id="confirmed-by"
              value={confirmedBy}
              onChange={(e) => setConfirmedBy(e.target.value)}
              placeholder="Your name"
              required
            />
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={authorizationConfirmed}
              onChange={(e) => setAuthorizationConfirmed(e.target.checked)}
            />
            <span>I confirm this target is owned by the team and authorized for load testing.</span>
          </label>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create target"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
