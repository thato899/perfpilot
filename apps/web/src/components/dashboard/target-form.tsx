"use client";

import { useState } from "react";
import type { Target } from "@perfpilot/schemas/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createTarget } from "@/lib/api";

export function TargetForm({
  projectId,
  onCreated,
  onCancel,
}: {
  projectId: string;
  onCreated: (target: Target) => void;
  onCancel?: () => void;
}) {
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
      setError("Confirm that you own this application or have permission to test it.");
      return;
    }

    setSubmitting(true);
    try {
      const target = await createTarget(projectId, {
        name,
        baseUrl,
        authorizationConfirmed,
        authorizationConfirmedBy: confirmedBy,
      });
      onCreated(target);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The application could not be added.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add an application</CardTitle>
        <CardDescription>
          Register an application you own or have permission to test. Authorization is recorded
          before a test can run.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="target-name">Application name</Label>
            <Input
              id="target-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Demo storefront"
              autoComplete="organization"
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
              placeholder="https://demo.example.com"
              autoComplete="url"
              required
            />
            <p className="text-xs text-muted-foreground">
              Enter the origin you are authorized to test. You can configure journeys separately.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirmed-by">Your name</Label>
            <Input
              id="confirmed-by"
              value={confirmedBy}
              onChange={(e) => setConfirmedBy(e.target.value)}
              placeholder="Name of the person authorizing this test"
              autoComplete="name"
              required
            />
          </div>
          <label className="flex items-start gap-3 rounded-lg border bg-muted/40 p-3 text-sm leading-relaxed">
            <input
              type="checkbox"
              className="mt-1 size-4 accent-primary"
              checked={authorizationConfirmed}
              onChange={(e) => setAuthorizationConfirmed(e.target.checked)}
            />
            <span>
              I confirm I own this application or have explicit permission to run performance tests
              against it.
            </span>
          </label>
          {error && (
            <p role="alert" className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            {onCancel && (
              <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
                Cancel
              </Button>
            )}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Adding application..." : "Add application"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
