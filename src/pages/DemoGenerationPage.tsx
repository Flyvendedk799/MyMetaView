/**
 * MyMetaView 6.0 — Demo generation page (API-wired)
 *
 * Integrates DemoGenerationExperience with batch API.
 * Optimized: two-tier polling, fast batch completion, resilient error handling.
 * Route: /demo-generation
 */

import React, { useCallback, useRef, useState } from "react";
import Seo from "../components/Seo";
import {
  DemoGenerationExperience,
  type DemoItem,
} from "../components/DemoGenerationExperience";
import {
  submitBatchJob,
  getBatchJobStatus,
  getBatchPages,
  getBatchResults,
  DEFAULT_API_BASE,
  type BatchResultItem,
} from "../api/demo-batch-api";
import { getApiBaseUrl } from "../api/client";

function mapBackendStatusToItem(
  status: string
): "pending" | "generating" | "success" | "error" {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    case "running":
      return "generating";
    default:
      return "pending";
  }
}

/** Prefer composited URL on all batch display paths (matches /results + 6.0 engine). */
function pickPreviewImageUrl(r: {
  composited_preview_image_url?: string | null;
  preview_url?: string | null;
  preview_image_url?: string | null;
  screenshot_url?: string | null;
}): string | undefined {
  const u =
    r.composited_preview_image_url ??
    r.preview_image_url ??
    r.preview_url ??
    r.screenshot_url;
  return u ?? undefined;
}

function mapResultToDemoItem(
  r: {
    url: string;
    status: string;
    composited_preview_image_url?: string | null;
    preview_url?: string | null;
    preview_image_url?: string | null;
    screenshot_url?: string | null;
    error?: string | null;
  },
  index: number
): DemoItem {
  const imageUrl = pickPreviewImageUrl(r);
  const failed = r.status === "failed" || Boolean(r.error);
  const completed = r.status === "completed";
  // Do not show success without a real preview URL — avoids masking backend gaps.
  if (failed || (completed && !imageUrl)) {
    return {
      id: `${r.url}-${index}`,
      url: r.url,
      status: "error",
      thumbnailUrl: imageUrl,
      errorMessage:
        r.error ??
        (completed && !imageUrl ? "Preview image unavailable" : undefined),
    };
  }
  if (completed && imageUrl) {
    return {
      id: `${r.url}-${index}`,
      url: r.url,
      status: "success",
      thumbnailUrl: imageUrl,
    };
  }
  return {
    id: `${r.url}-${index}`,
    url: r.url,
    status: mapBackendStatusToItem(r.status),
    thumbnailUrl: imageUrl,
    errorMessage: r.error ?? undefined,
  };
}

function mapBatchResultToDemoItem(r: BatchResultItem, index: number): DemoItem {
  const imageUrl = pickPreviewImageUrl(r);
  const failed = Boolean(r.error);
  const doneWithoutImage =
    !failed && !imageUrl && r.status === "completed";
  if (failed || doneWithoutImage) {
    return {
      id: `${r.url}-${index}`,
      url: r.url,
      status: "error",
      thumbnailUrl: imageUrl,
      errorMessage:
        r.error ?? (doneWithoutImage ? "Preview image unavailable" : undefined),
    };
  }
  const itemStatus = imageUrl ? "completed" : "running";
  return {
    id: `${r.url}-${index}`,
    url: r.url,
    status: mapBackendStatusToItem(itemStatus),
    thumbnailUrl: imageUrl,
    errorMessage: undefined,
  };
}

/** Merge partial results with full URL list so all slots render during rapid parallel completion. */
function mergeResultsWithUrls(
  urls: string[],
  results: BatchResultItem[],
  jobId: string
): DemoItem[] {
  const byUrl = new Map<string, BatchResultItem>();
  for (const r of results) byUrl.set(r.url, r);

  return urls.map((url, i) => {
    const r = byUrl.get(url);
    if (r) {
      return mapBatchResultToDemoItem(r, i);
    }
    return {
      id: `${jobId}-${i}`,
      url,
      status: "generating" as const,
    };
  });
}

async function fetchFullItems(
  jobId: string,
  urls: string[],
  options: { apiBase?: string; apiKey?: string }
): Promise<DemoItem[]> {
  const { apiBase, apiKey } = options;

  // 6.0: Unified status+results in one poll (most efficient)
  try {
    const statusRes = await getBatchJobStatus(jobId, { apiBase, apiKey });
    if (statusRes.results && statusRes.results.length > 0) {
      return mergeResultsWithUrls(urls, statusRes.results, jobId);
    }
    // Job exists but no results yet — show all slots as generating
    if (statusRes.total != null && statusRes.total > 0) {
      return urls.map((url, i) => ({
        id: `${jobId}-${i}`,
        url,
        status: "generating" as const,
      }));
    }
  } catch {
    // Fall through to fallbacks
  }

  // Fallback: /pages for per-URL progress
  const pagesRes = await getBatchPages(jobId, { apiBase, apiKey });
  if (pagesRes?.pages && pagesRes.pages.length > 0) {
    const byUrl = new Map(
      pagesRes.pages.map((p) => [p.url, p])
    );
    return urls.map((url, i) => {
      const p = byUrl.get(url);
      if (p) {
        return mapResultToDemoItem(
          {
            url: p.url,
            status: p.status,
            composited_preview_image_url: p.composited_preview_image_url,
            preview_url: p.preview_url,
            preview_image_url: p.preview_image_url,
            screenshot_url: p.screenshot_url,
            error: p.error,
          },
          i
        );
      }
      return { id: `${jobId}-${i}`, url, status: "generating" as const };
    });
  }

  // Fallback: /results (backend returns "results" array)
  const resultsRes = await getBatchResults(jobId, { apiBase, apiKey });
  const results = resultsRes.results ?? [];
  if (results.length > 0) {
    return mergeResultsWithUrls(urls, results, jobId);
  }

  return urls.map((url, i) => ({
    id: `${jobId}-${i}`,
    url,
    status: "generating" as const,
  }));
}

export type QualityMode = "fast" | "balanced" | "ultra" | "auto";

export interface DemoGenerationPageProps {
  apiBase?: string;
  apiKey?: string;
  initialQualityMode?: QualityMode;
  pollIntervalMs?: number;
}

export const DemoGenerationPage: React.FC<DemoGenerationPageProps> = ({
  apiBase = getApiBaseUrl() || DEFAULT_API_BASE,
  apiKey,
  initialQualityMode = "balanced",
  pollIntervalMs: pollIntervalMsProp,
}) => {
  const [qualityMode, setQualityMode] = useState<QualityMode>(initialQualityMode);
  const jobIdRef = useRef<string | null>(null);
  const urlsRef = useRef<string[]>([]);

  const onCreateJob = useCallback(
    async (urls: string[]) => {
      urlsRef.current = urls;
      const res = await submitBatchJob(urls, {
        apiBase,
        apiKey,
        qualityMode,
      });
      jobIdRef.current = res.job_id;
    },
    [apiBase, apiKey, qualityMode]
  );

  const onPollJob = useCallback(async (): Promise<DemoItem[]> => {
    const jobId = jobIdRef.current;
    const urls = urlsRef.current;
    if (!jobId) return [];
    return fetchFullItems(jobId, urls, { apiBase, apiKey });
  }, [apiBase, apiKey]);

  return (
    <div className="min-h-screen bg-ink">
      <Seo title="Generating your preview" noindex />
      <DemoGenerationExperience
        onCreateJob={onCreateJob}
        onPollJob={onPollJob}
        pollIntervalMs={pollIntervalMsProp ?? 1500}
        qualityMode={qualityMode}
        onQualityModeChange={setQualityMode}
      />
    </div>
  );
};

export default DemoGenerationPage;
