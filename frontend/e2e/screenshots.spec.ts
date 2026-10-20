import { test } from "@playwright/test";
import path from "path";
import fs from "fs";

const SCREENSHOT_DIR = path.resolve(__dirname, "../../submission/SCREENSHOTS");

test.describe("ORIGIN Hackathon Visual Asset Capture", () => {
  test.beforeAll(() => {
    if (!fs.existsSync(SCREENSHOT_DIR)) {
      fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    }
  });

  test("captures high-resolution production screenshots of all 8 core views", async ({ page }) => {
    test.setTimeout(180000);
    await page.setViewportSize({ width: 1440, height: 900 });

    // 1. Landing / Overview
    await page.goto("/");
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "01_landing_instrument_overview.png"),
      fullPage: false,
    });

    // 2. Guided Scientific Demo
    await page.goto("/demo");
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "02_guided_scientific_demo.png"),
      fullPage: false,
    });

    // 3. Topology Explorer
    await page.goto("/topology");
    await page.waitForTimeout(3000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "03_service_topology_matrix.png"),
      fullPage: false,
    });

    // 4. Telemetry Workspace
    await page.goto("/telemetry");
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "04_telemetry_workspace.png"),
      fullPage: false,
    });

    // 5. Causal Investigation Scientist
    await page.goto("/investigations");
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "05_causal_investigator_experiments.png"),
      fullPage: false,
    });

    // 6. Living Digital Twin
    await page.goto("/twin");
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "06_living_digital_twin_counterfactuals.png"),
      fullPage: false,
    });

    // 7. Recovery Command Center
    await page.goto("/recovery");
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "07_recovery_command_center.png"),
      fullPage: false,
    });

    // 8. Research Contracts
    await page.goto("/research");
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "08_research_contracts_architecture.png"),
      fullPage: false,
    });
  });
});
