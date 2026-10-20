import { expect, test } from "@playwright/test";

test.describe("ORIGIN Milestone 01/05 Browser Smoke Verification", () => {
  test("verifies live laboratory telemetry, topology explorer, and research contracts", async ({
    page,
  }) => {
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

    // 5. Navigate to Future Research Contracts and verify honest contract-only labeling
    await page.goto("/research");
    await expect(
      page.getByTestId("research-contract-experimentation")
    ).toContainText("CONTRACT ONLY IN M01/05");
    await expect(page.getByTestId("research-contract-evidence")).toContainText(
      "CONTRACT ONLY IN M01/05"
    );
  });
});
