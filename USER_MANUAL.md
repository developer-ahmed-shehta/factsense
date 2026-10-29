# FactSense MES / IIoT Web Application — Comprehensive User Manual & Operations Runbook

**System Version:** FactSense MES 2.0-2026.10  
**Specification Reference:** FACTSENSE_NEW_WEB_APP_SPECIFICATION (1).md  
**Visual & Design Token Standard:** Light Industrial Interface (Green `#16A34A`, Background `#F3F4F6`, Surfaces `#FFFFFF`, Borders `#E5E7EB`, Tabular Numerals)  
**Localization:** Full Native Bilingual Support (English LTR and Arabic RTL with dynamic switcher)

---

## 1. System Overview & Role-Based Access Control (RBAC)

FactSense MES is a real-time Manufacturing Execution System and Industrial Internet of Things (IIoT) telemetry platform designed for high-speed automated packaging and discrete manufacturing facilities.

### 1.1 The 10 Canonical Personas
The system enforces strict server-side authorization (`@role_required`, `@scope_required`) mapped to 10 canonical roles:

| Role Code | English Persona | Arabic Persona | Primary Landing Path | Key Responsibilities |
|---|---|---|---|---|
| `operator` | Line Operator | مشغل ماكينة | `/operator/` | Glove-friendly HMI, scrap counting, stoppage classification, scale weight logging, maintenance dispatch. |
| `supervisor` | Shift Supervisor | مشرف وردية | `/floor/` | 20-machine plant matrix, bottleneck cadence, stoppage splitting, 3-step shift handover, SMED stopwatch. |
| `maintenance` | Maintenance Technician | فني صيانة | `/maintenance/` | 5-stage Kanban incident board, repair clock-in, spare parts requisitions, testing evidence, force-lockout release. |
| `engineer` | Process Engineer | مهندس عمليات | `/stoppages/reliability/` | Asset health diagnostics, MTBF/MTTR/MTTF calculations, line balancing, speed matrix optimization. |
| `quality` | Quality Inspector | مفتش جودة | `/quality/` | ISO 22400-2 SPC X-bar/R charts, Gaussian normal distribution, Cp/Cpk, weight giveaway analysis, quarantine hold. |
| `planner` | Production Planner | مخطط إنتاج | `/planning/products/` | Product SKU master, process routing stages, rated machine speeds, shift assignment calendars. |
| `supply_chain` | Supply Chain & Materials | سلاسل الإمداد والخامات | `/work-orders/` | Work order central dispatch, material staging checklists, BOM shortage flagging, Odoo ERP synchronization. |
| `manager` | Plant Manager / Executive | مدير المصنع | `/dashboard/` | Executive command center, "So What?" operational banner, World-Class benchmark gauges, TPM Six Big Losses. |
| `admin` | System Administrator | مسؤول النظام | `/administration/` | User role scoping, plant topology, Moxa IoT gateway pairing, system settings, security audit log. |
| `controller` | Simulation Controller | مسؤول المحاكاة | `/controller/` | Telemetry signal generator, 5 failure scenarios, clock multiplier (1x-10x), isolated demo telemetry. |

### 1.2 Multi-Role Persona Switcher
Users assigned multiple roles (e.g. Supervisor who also acts as Planner) can switch personas instantly without re-logging in by clicking the active role badge in the top navigation bar. Every request is verified server-side against `UserRoleAssignment` records to prevent privilege escalation.

### 1.3 Localization & Language Switching
Clicking `English` or `العربية` in the top utility bar toggles between English (LTR) and Arabic (RTL). The session state, form parameters, and active view persist across language toggles.

---

## 2. Initial Setup & Plant Hierarchy Wizard (F01, F11, F19)

### 2.1 The 60-Second Onboarding Wizard (`/masterdata/wizard/`)
Quickly provision a greenfield plant hierarchy in three clicks:
1. Select an industrial template:
   - **Bottled Water (500ml PET):** 6-machine line (Blow Molder, Rinser, Filler, Capper, Labeler, Case Packer) rated at 120 CPM.
   - **Carbonated Soft Drinks (CSD 330ml Can):** Can Depalletizer, Rinser, Counter-Pressure Filler, Seamer, Tunnel Pasteurizer, Tray Shrinkwrapper rated at 180 CPM.
   - **Edible Cooking Oil (1L PET):** Bottle Unscrambler, Piston Filler, ROPP Capper, Induction Cap Sealer, Rotary Labeler, Carton Packer rated at 90 CPM.
2. Enter the factory name, plant code, and initial line identifier.
3. Click **Deploy Complete Plant Hierarchy**: The system creates the Factory, Line, Machines, initial SKU, and speed matrix automatically.

### 2.2 Hardware Kiosk & Moxa IoT Gateway Pairing (`/masterdata/kiosks/`)
Shop-floor tablets and IoT gateways are paired using 8-character claim codes:
1. The hardware boots into pairing mode displaying a unique 8-character code (e.g., `FL01-8842`).
2. An Administrator or Supervisor visits `/administration/gateways/` (or `/masterdata/kiosks/`), inputs the claim code, and binds the device to a specific machine.
3. Once paired, the tablet enters kiosk-exclusive mode locked to that machine console.

---

## 3. Shop-Floor Operations Guide (F05, F06, F19, F20)

### 3.1 Operator Touch Console (`/operator/`)
Designed for glove-friendly touchscreens (48px+ touch targets):
- **Machine Carousel Tabs:** Switch between machines along the line sequence with live state dots.
- **State Banner:** High-contrast banner displaying primary machine state (`RUNNING`, `UNPLANNED_DOWNTIME`, `BLOCKED`, `STARVED`, `CHANGEOVER`), instant CPM, and target speed.
- **Quick-Tap Production:** +1, +5, +10 unit buttons for manual piece input.
- **Scrap Numpad:** Tap **Log Scrap** to open the touch numpad, select defect category (Dent, Underfill, Cap Leak, Torn Label), and record scrap.
- **Scale Checkweigher Input:** Tap **Log Weight Sample** to record inline checkweigher weight measurements in grams against USL and LSL tolerances.

### 3.2 Kiosk Session Exclusivity & Safety Force-Logout
- **Exclusivity Enforcement:** Only one operator may claim active control of a machine at a time. If Operator B opens a console claimed by Operator A, the console displays an **Exclusive Session Active** warning and operates in read-only monitoring mode.
- **Supervisor Override:** A supervisor can click **Supervisor Override & Claim** to terminate the previous session and reassign the machine.
- **Operator Sign-Off:** Operators can release their session at shift end by clicking **Sign Off / Release Machine**.
- **Safety Force-Logout Lockout:** When a critical stoppage occurs with `force_logout=True` (e.g., Spindle Bearing Overheat) or when a maintenance technician locks the machine, the console engages a safety lockout overlay blocking all operator inputs until maintenance releases the equipment.

### 3.3 1-Touch Stoppage Classification & Interval Splitting
When a stoppage occurs, the operator taps **Classify Stoppage**:
- Level 1: Reason Category (Mechanical, Electrical, Operational, Quality).
- Level 2: Specific Stoppage Reason (Jam, Bearing Overheat, Sensor Fault, Changeover, Starvation).
- **Stoppage Splitting:** If an outage consisted of two different events (e.g. 15 minutes mechanical repair followed by 10 minutes line sanitization), tap **Split Stoppage**, set the split duration, and assign distinct reasons to each interval without gaps or overlaps.

### 3.4 Urgent Maintenance Dispatch & Lockout Release
- Tap **Call Maintenance** to dispatch an urgent technician ticket. The machine enters force-lockout status.
- Technician clocks in via the Maintenance Hub, enters diagnostics, requests spare parts if needed, completes repair testing, and clicks **Resolve & Release Machine** to clear the lockout.

---

## 4. Shift Supervision & Reliability Engineering (F06, F15)

### 4.1 Live Floor Matrix (`/floor/`)
Displays a 20-machine factory grid:
- Status indicators for all line machines.
- Highlighted **Bottleneck Machine** indicator (`is_bottleneck=True`).
- Bottleneck cadence tracking showing line pace constraints.
- Quick links to open operator consoles or dispatch maintenance.

### 4.2 Guided 3-Step Shift Handover Wizard (`/shifts/`)
At the end of every operational shift:
1. **Step 1 - Production Reconciliation:** Review total output counts, scrap percentages, and unclassified stops.
2. **Step 2 - Open Incidents & Maintenance:** Review open work orders and ongoing repair tickets.
3. **Step 3 - Safety & Quality Sign-Off:** Enter supervisor turnover notes and click **Submit & Lock Shift Handover**. Open events carry over into the next shift without data loss.

### 4.3 Digital SMED 4-Phase Changeover Stopwatch (`/smed/`)
Tracks Single-Minute Exchange of Die (SMED) changeovers across 4 standardized phases:
1. **Phase 1: Run-down & Clearing (Preparation)**
2. **Phase 2: Mechanical Tooling & Mold Swap**
3. **Phase 3: Settings Adjustment & Recipe Load**
4. **Phase 4: Ramp-up & Quality First-Piece Inspection**
The live stopwatch records duration per phase against benchmark targets to identify changeover waste.

### 4.4 Juran 80/20 Pareto & Reliability KPIs (`/stoppages/`)
- **80/20 Pareto Chart:** Isolates the vital few stoppage reasons accounting for 80% of total downtime duration and frequency.
- **Reliability KPIs (`/stoppages/reliability/`):**
  - **MTBF (Mean Time Between Failures):** Operating hours divided by failure count.
  - **MTTR (Mean Time To Repair):** Total breakdown downtime divided by failure count.
  - **MTTF (Mean Time To Failure):** Expected operational lifespan between incidents.
  - **Failure Rate ($\lambda$):** Failures per operating hour.

---

## 5. Quality SPC & Weight Giveaway Analysis (F07)

### 5.1 ISO 22400-2 SPC Control Charts (`/quality/`)
Statistical Process Control tracking container net fill weight:
- **$\bar{X}$ Chart (Subgroup Averages):** Plots average weight per subgroup against Upper Control Limit (UCL), Nominal Target, and Lower Control Limit (LCL).
- **$R$ Chart (Subgroup Ranges):** Plots weight dispersion (variability) across samples.
- **Gaussian Normal Distribution:** Bell curve overlaying sample distribution against specification limits (USL and LSL).
- **Process Capability ($C_p$ and $C_{pk}$):**
  $$C_p = \frac{\text{USL} - \text{LSL}}{6\sigma}$$
  $$C_{pk} = \min\left(\frac{\text{USL} - \mu}{3\sigma}, \frac{\mu - \text{LSL}}{3\sigma}\right)$$
  - $C_{pk} \ge 1.33$: Capable and centered.
  - $1.00 \le C_{pk} < 1.33$: Marginally capable; requires tight monitoring.
  - $C_{pk} < 1.00$: Incapable; producing out-of-specification units.

### 5.2 Overfill Giveaway Financial Simulator (`/quality/giveaway/`)
Calculates the hidden cost of product giveaway (filling bottles above nominal label weight):
- Calculates total excess grams, conversion to liquid volume, and financial loss based on ingredient cost per kilogram.
- **Interactive Recalibration Slider:** Model shifting target mean filling weight closer to nominal weight while validating underfill risk compliance.

---

## 6. Real-Time Alerts & Deduplication Engine (F08)

### 6.1 Alert Taxonomies & Thresholds (`/alerts/`)
Automated monitoring rules across 6 operational categories:
- **Downtime Duration Alert:** Triggers when an unclassified stop exceeds 5 minutes.
- **Speed Degradation Alert:** Triggers when instant CPM drops below 70% of rated speed for 3 consecutive minutes.
- **Defect Burst Alert:** Triggers when scrap count exceeds 15 units within a 10-minute window.
- **Quality Out-of-Spec Alert:** Triggers when checkweigher sample breaches USL or LSL limits.
- **Vibration Anomaly Alert:** Triggers when machine accelerometer exceeds 4.5 mm/s RMS.
- **Temperature Spike Alert:** Triggers when spindle or bearing temperature exceeds 75°C.

### 6.2 Alarm Storm Suppression & Auto-Resolution
- **Suppression Window (Cooldown):** Prevents duplicate alerts from spamming operators while an issue is already active.
- **Auto-Resolve Watchdog:** Automatically closes alerts when operating telemetry returns to nominal thresholds.
- **Global Notification Drawer:** Header bell icon with live unread badge and 1-click acknowledge.

---

## 7. Production Planning, Work Orders & ERP Sync (F18)

### 7.1 Work Order Lifecycle (`/work-orders/`)
- States: `PLANNED` -> `RELEASED` -> `IN_PROGRESS` -> `COMPLETED` (or `SHORT_CLOSED`).
- Ordered Process Routing: 3-stage progression (Blow Molding -> Filling & Capping -> Labeling & Packaging).
- Short-Close Protection: Mandates supervisor justification notes before an incomplete order can be closed.

### 7.2 Component Material Staging (`/work-orders/materials/`)
- BOM Staging Checklist: Preforms, Caps, Labels, and Shrink Film.
- Staging Readiness Gauge: Visual percentage of staged raw materials.
- Shortage Flagging: Planners can flag component shortages to block premature floor release.

### 7.3 Upstream ERP / Odoo Synchronization (`/work-orders/erp-sync/`)
- Simulates bidirectional Odoo 17 MRP JSON-RPC integration.
- Idempotent Inbound Pull: Prevents duplicate orders using external ERP IDs.
- **Smart Conflict Queue:** If upstream ERP changes order parameters for an order already in production on the shop floor, the system routes the discrepancy to the Conflict Queue for manual resolution (`Accept ERP` vs `Keep MES Local`).

---

## 8. Industrial AI Copilot & Shift Reports (F09, F10)

### 8.1 Dual-Engine Industrial AI Copilot (`/copilot/`)
- **Dual Architecture:** Cloud Gemini API when key is available; 100% deterministic local heuristic engine offline.
- **Bilingual Natural Language Queries:**
  - *"What is our current OEE and primary loss category?"*
  - *"Which machine is the line bottleneck?"*
  - *"Analyze weight giveaway and scrap defects"*
  - *"ما هو معدل OEE الحالي وما هي أكبر الخسائر؟"*
  - *"ما هي الماكينة الخانقة وأسباب توقفها؟"*
- **Interactive Action Chips:** Instant navigation buttons linking directly to relevant floor monitors, Pareto charts, or dispatch queues.

### 8.2 Standardized Shift Handover Reports (`/reports/`)
- **Printable PDF Export (`/reports/export/pdf/`):** High-resolution ReportLab document with 4-bullet executive synthesis, ISO 22400 OEE scorecard, Top 5 downtime events, and physical sign-off lines.
- **Multi-Tab Excel Workbook (`/reports/export/excel/`):** Structured 4-tab workbook (`Shift Summary`, `Downtime Events`, `Quality & Scrap Defects`, `Work Orders`).
- **Automated Subscriptions (`/reports/subscriptions/`):** Automated delivery over SMTP / Email and Telegram bot webhooks with delivery status logs.
- **Historical Explorer (`/reports/explorer/`):** Date range, shift, and line filtering with live KPI rollups and CSV export.

---

## 9. System Administration & Observability Probes (F19, F20)

### 9.1 System Settings (`/administration/settings/`)
Configure factory name, Arabic title, geographic location, plant timezone (`Africa/Cairo`), default reporting currency (`EGP`), and line OEE benchmark targets.

### 9.2 Integrations Console (`/administration/integrations/`)
Monitor health of ERP Odoo connector, Telegram notifications bot, Gemini AI cloud engine, and Moxa edge hardware, with a **Test Ping All Connectors** diagnostic button.

### 9.3 Immutable System Audit Trail (`/administration/audit/`)
Security log tracking every authentication event, role switch, stoppage classification, maintenance transition, work order release, and configuration update with actor, timestamp, and details. Filterable by action or actor, with full CSV export (`/administration/audit/export/csv/`).

### 9.4 Health & Observability Probes (`/healthz`, `/status/`)
Container readiness and liveness probe returning JSON:
```json
{
  "status": "healthy",
  "timestamp": "2026-10-29T16:30:00Z",
  "version": "2.0.0-2026.10",
  "subsystems": {
    "database": { "status": "connected", "latency_ms": 1.25 },
    "telemetry_pipeline": { "status": "operational", "watchdog_window_seconds": 15 },
    "copilot_engine": { "engine": "Deterministic Python Offline Heuristic", "bilingual_modes": ["en", "ar"] },
    "shop_floor_status": { "active_kiosk_sessions": 1, "open_maintenance_incidents": 0 }
  }
}
```

