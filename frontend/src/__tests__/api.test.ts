import { describe, expect, it } from "vitest";
import {
  formatProvenanceBadge,
  groupMetricPointsByTimestamp,
} from "../lib/api";
import type { MetricPointRead } from "../lib/types";

describe("ORIGIN Frontend Telemetry & Provenance Utilities", () => {
  it("formats provenance badges accurately for registered, observed, and verified edges", () => {
    const verified = formatProvenanceBadge("registered_and_observed");
    expect(verified.label).toBe("VERIFIED (REG + OBS)");

    const observed = formatProvenanceBadge("observed");
    expect(observed.label).toBe("OBSERVED ONLY");

    const registered = formatProvenanceBadge("registered");
    expect(registered.label).toBe("DECLARED ONLY");
  });

  it("groups time-series metric observations by correlation window for Recharts", () => {
    const samplePoints: MetricPointRead[] = [
      {
        id: "pt-1",
        system_id: "sys-1",
        service_key: "api-gateway",
        metric_name: "request_latency_ms",
        metric_unit: "ms",
        value: 84.5,
        correlation_id: "corr-abc-1",
        trace_id: "tr-1",
        is_synthetic: true,
        attributes_json: {},
        observed_at: "2026-10-20T09:00:00Z",
      },
      {
        id: "pt-2",
        system_id: "sys-1",
        service_key: "payment-simulator",
        metric_name: "request_latency_ms",
        metric_unit: "ms",
        value: 31.2,
        correlation_id: "corr-abc-1",
        trace_id: "tr-1",
        is_synthetic: true,
        attributes_json: {},
        observed_at: "2026-10-20T09:00:00Z",
      },
    ];

    const grouped = groupMetricPointsByTimestamp(samplePoints);
    expect(grouped).toHaveLength(1);
    expect(grouped[0]?.["api-gateway"]).toBe(84.5);
    expect(grouped[0]?.["payment-simulator"]).toBe(31.2);
    expect(grouped[0]?.correlationId).toBe("corr-abc-1");
  });
});
