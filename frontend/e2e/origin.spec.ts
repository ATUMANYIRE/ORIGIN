import { expect, test } from "@playwright/test";

test.describe("ORIGIN Milestone 01/05 & 02/05 Browser Verification", () => {
  test("verifies live laboratory telemetry, topology explorer, causal investigation scientist, and research contracts", async ({
    page,
  }) => {
    test.setTimeout(90000);
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

    // 6. Navigate to Future Research Contracts and verify honest boundary status
    await page.goto("/research");
    await expect(
      page.getByTestId("research-contract-simulation")
    ).toContainText("CONTRACT ONLY");
    await expect(
      page.getByTestId("implemented-module-experimentation")
    ).toBeVisible();
    await expect(
      page.getByTestId("implemented-module-evidence")
    ).toBeVisible();
  });
});
