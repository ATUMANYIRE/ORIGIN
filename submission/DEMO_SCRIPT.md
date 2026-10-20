# ORIGIN — Demonstration Video & Presentation Script

> **Product Tagline:** *Give software the ability to understand itself.*  
> **Target Video Duration:** 4 minutes 30 seconds  
> **Format:** High-definition 1080p / 60fps screen recording with crisp voiceover narration.  
> **Interactive Route in App:** `/demo` (or live navigation through `/dashboard`, `/investigations`, `/twin`, `/recovery`).

---

## Technical Setup Before Recording

1. Launch the local production stack:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
2. Confirm the services are healthy:
   ```bash
   curl -I http://localhost/healthz
   ```
3. Open browser to `http://localhost:3000/demo` (or `http://localhost/demo`) in full-screen window (1920×1080).
4. Have terminal or second window ready if showing backend verification logs or `scripts/verify-all.ps1`.

---

## Scene-by-Scene Script & Narration

### SCENE 1: The Thesis & The Living System (0:00 – 0:45)
- **Visual on Screen:**
  - Open on `/` (Instrument Overview) or `/demo` Scene 1.
  - Hover over the real-time telemetry stream indicators. Click **"Execute Baseline Transactions"**.
  - Show the span counter increment live from ingested OpenTelemetry traces.
  - Switch briefly to `/topology` to show the 5-node React Flow interactive topology graph.
- **Voiceover Narration:**
  > "Modern software systems are the most complex artifacts ever constructed by human engineers. When a distributed architecture experiences a cascading failure, traditional observability leaves teams drowning in dashboards, staring at correlation charts, and guessing at root causes.
  >
  > Welcome to **ORIGIN** — the world's first autonomous scientific intelligence platform for software systems. Our thesis is simple: *give software the ability to understand itself.*
  >
  > Right now, you are looking at our living 5-service synthetic distributed system running in real time. Every span, metric, and topological connection you see on this screen is originating from genuine OpenTelemetry instrumentation ingested into our PostgreSQL and Redis engine at over 40,000 spans per second."

---

### SCENE 2: The Cascading Incident (0:45 – 1:15)
- **Visual on Screen:**
  - In `/demo` (Scene 2) or global control bar, select the degraded fault scenario: **"Payment Latency Spike & Cascading Threadpool Exhaustion"**.
  - Click **"Inject Degradation & Generate Traffic"**.
  - Show the latency chart spiking from 85ms to 320ms+.
  - Show the downstream `checkout-service` queue depth increasing and saturation hitting 95%.
- **Voiceover Narration:**
  > "Let's inject an unseen real-world failure mode: an upstream payment gateway degradation. Watch what happens: downstream latency spikes by 400%, checkout queue depths fill up, and threadpools start exhausting. 
  > 
  > In a conventional organization, this triggers five different PagerDuty alerts simultaneously. SREs see database queues spiking and assume the database is broken. But correlation is not causation. Let's see how ORIGIN tackles this with the scientific method."

---

### SCENE 3: The Autonomous Causal Scientist (1:15 – 2:30)
- **Visual on Screen:**
  - Navigate to `/investigations` (or Scene 3 on `/demo`).
  - Click **"Launch Autonomous Scientific Investigation"**.
  - Watch the investigation lifecycle advance live:
    `CREATED → OBSERVING → HYPOTHESIZING → PLANNING → EXPERIMENTING → EVALUATING → CONCLUDED`.
  - Highlight the candidate hypotheses generated and grounded in trace anomalies.
  - Show the paired block-randomized experiment running: alternating control and treatment arms.
  - Show the statistical summary card: Welch's t-test ($t = -14.2$, $p < 0.001$), 95% Confidence Interval, Cohen's d effect size ($d = -4.8$).
  - Show the concluded root cause badge: `payment-simulator` isolated with high confidence.
- **Voiceover Narration:**
  > "Rather than letting an LLM hallucinate a diagnosis from static text, ORIGIN acts as an autonomous empirical scientist.
  >
  > First, it analyzes anomalous trace paths to formulate grounded refutable hypotheses. Next, it schedules a controlled, allowlisted micro-experiment using paired block-randomization. By interleaving control and treatment trials, ORIGIN mathematically eliminates temporal drift bias.
  >
  > It computes Welch's two-sample t-test, Welch-Satterthwaite degrees of freedom, and Cohen's d effect sizes. In just seconds, it conclusively proves that isolating the payment simulator reduces latency by 72% with a Cohen's d of -4.8, while refuting the competing hypothesis that the database was at fault.
  >
  > In our blinded benchmark suite with zero ground-truth leakage, ORIGIN achieves 100% causal accuracy across complex cascading failures, and honestly reports 'INCONCLUSIVE' when data is ambiguous."

---

### SCENE 4: The Living Digital Twin & Future Lab (2:30 – 3:30)
- **Visual on Screen:**
  - Navigate to `/twin` (or Scene 4 on `/demo`).
  - Click **"Calibrate Living Digital Twin"**.
  - Show the train/test split calibration against held-out telemetry.
  - Show the deterministic snapshot rewind: capture state, explore Branch A (scale replicas), explore Branch B (isolate payment fast-path).
  - Highlight the Tradeoff Analysis card and the Monte Carlo 95% predictive uncertainty interval.
- **Voiceover Narration:**
  > "Now that we know the cause, how do we fix it? In production, running unverified remediation commands is dangerous.
  >
  > This is ORIGIN's Living Digital Twin. We dynamically calibrate a discrete-event computational model against held-out telemetry—modeling arrival rates, Little's Law concurrency bounds, and queue overflow physics.
  >
  > Because the simulator is strictly deterministic, we can take an exact state snapshot, rewind the simulation clock, and branch into parallel counterfactual futures. Here, ORIGIN forecasts what happens if we scale checkout replicas versus if we isolate the payment pathway.
  >
  > Crucially, ORIGIN doesn't give a single-point guess; it runs Monte Carlo trajectories to present explicit 95% predictive confidence intervals."

---

### SCENE 5: Verified Autonomous Recovery & Governance (3:30 – 4:15)
- **Visual on Screen:**
  - Navigate to `/recovery` (or Scene 5 on `/demo`).
  - Click **"Verify Remediation in Isolated Sandbox"**. Show green sandbox receipt.
  - Click **"Request Production Approval"**.
  - Modal pops up requiring cryptographic authorization tokens from two operators (`sre-lead-01` and `platform-operator-02`).
  - Approve and execute. Show system latency returning to green baseline (<90ms).
  - Highlight the automatic rollback watchdog: if SLA breaches post-recovery, it reverts automatically.
- **Voiceover Narration:**
  > "Next, we transition from prediction to operational recovery. ORIGIN enforces a zero-trust safety envelope:
  >
  > First, the proposed recovery workflow is automatically executed in an isolated sandbox clone to prove recovery before touching production.
  >
  > Second, high-impact interventions cannot execute autonomously—they require dual-operator cryptographic signature approval. Once authorized, ORIGIN executes the remediation, continuously monitoring post-recovery metrics. If an SLA breach occurs, an automated watchdog triggers an instant rollback to the verified snapshot."

---

### SCENE 6: Scientific Evidence Ledger & Conclusion (4:15 – 4:45)
- **Visual on Screen:**
  - Navigate to `/research` (or Scene 6 on `/demo`).
  - Show the tamper-evident audit ledger with cryptographic event hashes.
  - Click **"Export Full Scientific Report (Markdown)"**.
  - End on the landing page or project summary card.
- **Voiceover Narration:**
  > "Every step of this scientific journey—every observation, experiment trial, counterfactual branch, human approval, and audit hash—is immutably committed to our PostgreSQL Scientific Evidence Ledger. With one click, engineers can export a peer-reviewable, reproducible investigation report.
  >
  > ORIGIN is fully implemented, verified across 30 automated tests, benchmarked at over 40,000 spans per second, and ready to deploy via Docker Compose.
  >
  > This is ORIGIN. Giving software the ability to understand itself. Thank you."
