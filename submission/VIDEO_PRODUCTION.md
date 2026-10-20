# ORIGIN — Hackathon Video Production Guide & Asset Instructions

> **Event:** HackOctober MLH × Tech4hack  
> **Target Video Length:** 3:30 to 4:30 minutes (Max 5:00)  
> **Resolution:** 1080p (1920×1080) at 60 FPS  
> **Script Reference:** [`submission/DEMO_SCRIPT.md`](file:///E:/Projects/ORIGIN/submission/DEMO_SCRIPT.md)  

---

## 1. Recording Setup & Recommendations

### 1.1 Screen Capture Settings (OBS Studio / Screen Studio / Loom)
- **Canvas Resolution:** 1920 × 1080 pixels (16:9 aspect ratio).
- **Framerate:** 60 FPS (or 30 FPS minimum) for smooth React Flow and Recharts transitions.
- **Bitrate:** 8,000–12,000 kbps (CBR, NVENC or x264).
- **Audio:** 48 kHz, 160 kbps AAC stereo, noise suppression filter enabled.
- **Browser Window:** Google Chrome or Brave in Fullscreen (`F11`) with default zoom (`100%`) and bookmarks bar hidden.

### 1.2 System Preparation Prior to Capture
1. Ensure the Docker Compose stack is running cleanly:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
2. Clear previous investigation runs or seed fresh baseline telemetry:
   ```bash
   # Optional: run benchmark resilience or burst lab traffic
   python scripts/benchmark-resilience.py
   ```
3. Open `http://localhost:3000/demo` (or `http://localhost/demo`).
4. Step through each scene once before recording to ensure network caches are primed and browser rendering is instantaneous.

---

## 2. Automated Headless Video Capture (Playwright)

For an automated fallback or background b-roll recording, Playwright can record the entire test execution directly to `.webm` video files.

### 2.1 Enable Playwright Video Recording
To record videos automatically, edit `frontend/playwright.config.ts` to add `video: "on"`:

```typescript
use: {
  baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
  video: "on",
  viewport: { width: 1920, height: 1080 },
}
```

Then run the end-to-end browser demonstration:
```bash
powershell.exe -ExecutionPolicy Bypass -File scripts/capture-screenshots.ps1
```

Recorded video files will be saved in `frontend/test-results/`.

---

## 3. Video Editing & Polish Checklist

- [ ] **Intro:** Show title card with ORIGIN logo, product tagline (*Give software the ability to understand itself*), and HackOctober MLH × Tech4hack badge.
- [ ] **Scene 1 (Living System):** Highlight the real-time OpenTelemetry ingestion indicator and the 5-node topology graph.
- [ ] **Scene 2 (The Incident):** Zoom in smoothly on the latency spike from 85ms to 320ms+ and queue saturation.
- [ ] **Scene 3 (Causal Scientist):** Highlight the Welch's t-test ($t = -14.2$), degrees of freedom, Cohen's d effect size, and the concluded root cause badge.
- [ ] **Scene 4 (Digital Twin):** Emphasize the deterministic snapshot rewind and the parallel counterfactual forecast with 95% predictive uncertainty bounds.
- [ ] **Scene 5 (Verified Recovery):** Show the green sandbox verification receipt, dual-operator approval modal, and live latency restoration.
- [ ] **Scene 6 (Evidence Ledger):** Show the immutable PostgreSQL audit trail and one-click markdown report export.
- [ ] **Outro:** Display GitHub URL (`https://github.com/ATUMANYIRE/ORIGIN`) and author credits.

---

## 4. Video Hosting & Devpost Metadata

- **Platform:** YouTube (set to **Public** or **Unlisted**) or Loom / Vimeo.
- **Title:** `ORIGIN — Autonomous Scientific Intelligence for Software Systems (HackOctober 2026)`
- **Description:**
  ```
  ORIGIN is an autonomous scientific intelligence platform for software systems.
  Tagline: Give software the ability to understand itself.
  Built for HackOctober MLH × Tech4hack (October 2026).

  GitHub: https://github.com/ATUMANYIRE/ORIGIN
  Full Documentation & Validation: See repository submission/ directory.
  ```
- **Tags:** `Distributed Systems`, `OpenTelemetry`, `Causal Inference`, `Digital Twin`, `Autonomous Recovery`, `AI Reliability`, `DevOps`, `Hackathon`.
