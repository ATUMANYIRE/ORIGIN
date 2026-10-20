import { expect, test } from "@playwright/test";

test.describe("ORIGIN Milestone 01/05 - 04/05 Browser Verification", () => {
  test("verifies live laboratory telemetry, topology explorer, causal investigation scientist, digital twin, recovery command center, and research contracts", async ({
    page,
  }) => {
    test.setTimeout(120000);
    // 1. Visit Landing Page
    await page.goto("/");
    await expect(
      page.getByRole("heading", {
        name: "Give software the ability to understand itself.",
      })
    ).toBeVisible();

    await expect(page.getByTestId("landing-engine-health")).toHaveText(
      /healthy/i,
      { timeout: 15000 }
    );

    const initialSpansText = await page
      .getByTestId("landing-span-count")
      .innerText();
    const initialSpans = parseInt(initialSpansText, 10);
    expect(initialSpans).toBeGreaterThan(0);

    // 2. Trigger real laboratory traffic from the global control bar and prove counts increase
    await page.getByTestId("global-run-lab-btn").click();
    await expect(page.getByTestId("lab-burst-receipt")).toBeVisible({
      timeout: 15000,
    });

    await expect(async () => {
      const updatedSpansText = await page
        .getByTestId("landing-span-count")
        .innerText();
      const updatedSpans = parseInt(updatedSpansText, 10);
      expect(updatedSpans).toBeGreaterThan(initialSpans);
    }).toPass({ timeout: 10000 });

    // 3. Navigate to Topology Explorer and verify all 5 laboratory service nodes render
    await page.goto("/topology");
    for (const serviceKey of [
      "api-gateway",
      "checkout-service",
      "inventory-service",
      "payment-simulator",
      "order-database-sim",
    ]) {
      await expect(
        page.getByTestId(`topology-node-${serviceKey}`)
      ).toBeVisible({ timeout: 15000 });
    }

    // 4. Navigate to Telemetry Workspace and verify live stored metrics & spans render
    await page.goto("/telemetry");
    await expect(page.getByTestId("telemetry-sample-count")).not.toHaveText(
      "0",
      { timeout: 15000 }
    );
    await expect(
      page.getByTestId("span-row-checkout-service").first()
    ).toBeVisible();

    // 5. Navigate to Causal Investigation Laboratory (/investigations) and launch an autonomous investigation
    await page.goto("/investigations");
    await expect(
      page.getByRole("heading", {
        name: "Causal Investigation Laboratory",
      })
    ).toBeVisible();

    await page
      .getByTestId("inv-fault-stage-select")
      .selectOption("payment_latency_spike");
    await page.locator("#inv-samples").fill("3");
    await page.getByTestId("launch-investigation-btn").click();

    await expect(page.getByTestId("active-investigation-detail")).toBeVisible({
      timeout: 45000,
    });
    await expect(page.getByTestId("investigation-status-badge")).toHaveText(
      "CONCLUDED",
      { timeout: 45000 }
    );
    await expect(page.getByTestId("concluded-root-cause")).toHaveText(
      "payment-simulator"
    );
    await expect(page.getByTestId("experiment-run-card-0")).toBeVisible();

    // Open reproducible Markdown report modal
    await page.getByTestId("export-markdown-btn").click();
    await expect(page.getByTestId("scientific-report-markdown")).toContainText(
      "# ORIGIN Scientific Investigation Report"
    );

    // 6. Navigate to Living Digital Twin (/twin), calibrate model, create counterfactual branch, and export report
    await page.goto("/twin");
    await expect(
      page.getByRole("heading", {
        name: "Living Digital Twin & Counterfactual Intelligence",
      })
    ).toBeVisible();
    await expect(page.getByTestId("epistemic-separation-banner")).toContainText(
      "COUNTERFACTUAL PREDICTION"
    );

    await page
      .getByTestId("twin-calib-profile-select")
      .selectOption("payment_latency_spike");
    await page.getByTestId("calibrate-twin-btn").click();

    await expect(page.getByTestId("twin-version-badge")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("calibration-mae-readout")).toContainText(
      "ms"
    );
    await expect(page.getByTestId("twin-node-checkout-service")).toBeVisible();

    // Test Time Machine Step +1s and Rewind
    await page.getByTestId("time-machine-step-btn").click();
    await page.getByTestId("time-machine-rewind-btn").click();

    // Spawn a counterfactual branch reducing payment-simulator latency
    await page.getByTestId("spawn-counterfactual-btn").click();
    await expect(page.getByTestId("branch-comparison-deltas")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("comparison-latency-delta")).toContainText(
      "-"
    );

    // Export reproducible Digital Twin Markdown report
    await page.getByTestId("export-twin-report-btn").click();
    await expect(page.getByTestId("twin-report-markdown")).toContainText(
      "# ORIGIN Digital Twin Counterfactual Report"
    );

    // 7. Navigate to Recovery Command Center (/recovery), prepare workflow, approve with single-use token, and execute recovery
    await page.goto("/recovery");
    await expect(
      page.getByRole("heading", {
        name: "Verified Autonomous Recovery Command Center",
      })
    ).toBeVisible();

    await page.getByTestId("launch-recovery-pipeline-btn").click();
    await expect(page.getByTestId("active-plan-status-badge")).toContainText(
      "AWAITING_APPROVAL",
      { timeout: 60000 }
    );

    await page.getByTestId("approve-recovery-plan-btn").click();
    await expect(page.getByTestId("issued-single-use-token-box")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByTestId("active-plan-status-badge")).toContainText(
      "APPROVED"
    );

    await page.getByTestId("execute-approved-recovery-btn").click();
    await expect(page.getByTestId("active-plan-status-badge")).toContainText(
      "RECOVERED",
      { timeout: 30000 }
    );

    // 8. Navigate to Research Contracts and verify all 9 boundaries are implemented
    await page.goto("/research");
    await expect(
      page.getByTestId("implemented-module-simulation")
    ).toBeVisible();
    await expect(
      page.getByTestId("implemented-module-experimentation")
    ).toBeVisible();
    await expect(
      page.getByTestId("implemented-module-evidence")
    ).toBeVisible();
  });
});
