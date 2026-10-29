# FactSense MES / IIoT Web Application — Master Implementation Plan

**Date:** 29 October 2026  
**Status:** In Progress — Batch 1 Active  
**Master Specification:** [FACTSENSE_NEW_WEB_APP_SPECIFICATION (1).md](file:///d:/others/PycharmProjects/factsense_demo_2/FACTSENSE_NEW_WEB_APP_SPECIFICATION%20(1).md)

---

## 1. Source Precedence & Conflict Resolutions

As established in Section 1 and Section 12 of the Master Specification, the following hierarchy of precedence governs all design, architecture, and feature decisions:

1. **Visual Precedence:** The reference Product Management screenshot takes precedence over legacy dashboard styling, permanent sidebar navigations, dark-mode-only assumptions, or decorative visual treatments in the appendices. The visual standard is a clean, modern, light UI:
   - Crisp white horizontal navigation bar with role workspace brand and account/locale utilities.
   - Pale gray page background (`#F3F4F6`), pristine white card/table surfaces (`#FFFFFF`), subtle borders (`#E5E7EB`).
   - Clear page headings with concise subheadings and prominent green primary call-to-action buttons (`#16A34A`).
   - Wide, readable data tables with alternating row shading, compact status/process pills (`#DBEAFE` / `#1D4ED8`), and visible permitted actions.
2. **Structural Precedence (Sections 1–12):** Takes precedence over legacy implementation details in Appendices A and B. Specifically:
   - Canonical 10-role architecture (`operator`, `supervisor`, `maintenance`, `engineer`, `quality`, `planner`, `supply_chain`, `manager`, `admin`, `controller`).
   - Multi-role persona switching without re-login; active role validated server-side on every request.
   - Dynamic landing page resolution (no hardcoded cascade `if/elif` role redirection).
   - Strict backend enforcement: URL tampering or parameter guessing never bypasses role or scope checks.
   - Separation of simulation (`controller`) from real plant configurations.
3. **Feature Completeness (Appendix A):** Defines the exhaustive baseline for telemetry ingestion, OEE ISO 22400 calculations, TPM Six Big Losses, SPC ISO 22400-2, alarms, copilot, and REST/SSE endpoints. No feature is deleted; advanced views reside on contextual tabs or detail views.
4. **UI Workflows (Appendix B):** Preserves specialized operational workflows including glove-friendly touch ergonomics, digital SMED 4-phase stopwatch, maintenance Kanban with repair clock-in, sequential document approvals, work order dispatch, and kiosk device locking.
5. **Honesty & Integrity Rule:** No mock functionality is presented as complete. Features scheduled for subsequent batches are cleanly labeled as "Under Development (Batch X)" with informative, structured industrial empty states.

---

## 2. Technical Architecture & Decisions

- **Backend Framework:** Django 5.x on Python 3.13.
- **Database:** SQLite (local development / testing / demo zero-dependency verification) with schema designed for PostgreSQL production readiness.
- **Frontend Core:**
  - Modern, responsive HTML5 with semantic tags and accessible IDs.
  - Curated industrial design token CSS system matching the reference screenshot:
    - Primary Action: `#16A34A` (Green)
    - Brand / Links: `#2563EB` (Blue)
    - Page Background: `#F3F4F6` (Cool Gray)
    - Surface: `#FFFFFF` (White)
    - Borders: `#E5E7EB`
    - Body Text: `#111827`, Secondary: `#64748B`
    - Status Tokens: Running (`#10B981`), Downtime (`#EF4444`), Planned/Setup (`#F59E0B`), Maintenance (`#8B5CF6`), Quality Alert (`#F97316`), Standby (`#6B7280`).
  - Native Bidirectional Support: English (LTR) and Arabic (RTL) with dynamic language switcher that preserves session state and form data.
  - Tabular Numerals: Tabular monospace font styling for counters, cycle times, and metrics.
  - Interactive Layer: HTMX & Alpine.js for snappy, single-page feel without monolithic client overhead.
- **Security & Authorization Model:**
  - Custom User model with Scoped Role Assignments (`UserRoleAssignment`).
  - Active role persisted in session (`request.session['active_role']`).
  - Role-switching view (`/accounts/switch-role/`) with strict validation against user assignments.
  - Role-based and scope-based decorators and mixins (`@role_required`, `@scope_required`) enforcing authorization server-side on every view and API.
  - Automatic landing redirection based on `active_role`.

---

## 3. Delivery Batches Roadmap

| Batch | Deliverable & Scope | Gate Before Completion | Status |
|:---:|---|---|:---:|
| **1** | **Foundation, Shell, Multi-Role RBAC & Localization**<br>• Project structure, base templates, design system tokens.<br>• Reference light UI layout with horizontal top navigation.<br>• All 9 canonical roles, scoped assignments, multi-role persona switcher.<br>• Dynamic role landing pages, role-filtered navigation.<br>• English / Arabic (LTR / RTL) localization engine.<br>• Seeded demo users for every role.<br>• Reference Product Management view matching screenshot.<br>• Server-side permission guards and test suite. | Each persona reaches correct home; direct unauthorized requests blocked with 403; RTL toggles cleanly; UI review approval. | **COMPLETED** (10/10 Automated Tests Passed; Awaiting UI Review) |
| **2** | **Master Data, Shifts, Rates & Factory Topology Wizard**<br>• Factory, Line, Machine hierarchy models and CRUD.<br>• SKU / Products, MachineProductRate speed matrix.<br>• Shift schedules, planned breaks, shift calendar.<br>• 60-Second Onboarding Wizard with industry presets (Water, CSD, Oil).<br>• SVG Topology Viewer with machine node sequence.<br>• Kiosk hardware pairing & QR code enrollment. | Usable line created via wizard; scoped kiosk device paired; rate matrix functional. | Pending |
| **3** | **Telemetry Pipeline, OEE Engine, SSE & Demo Controller**<br>• Telemetry ingestion API (pulses, speed, vibration, temperature).<br>• State machine evaluator (8 standardized states).<br>• OEE ISO 22400 engine (A, P, Q, Bottleneck cadence).<br>• TPM Six Big Losses waterfall allocation.<br>• 1 Hz SSE stream and polling fallback.<br>• Signal simulator controller with 5 scenarios & clock multiplier. | Verified reproducible calculations against test fixtures; demo telemetry isolated from live. | Pending |
| **4** | **Operator Touch Console, Floor Monitor, Stoppages & SMED**<br>• Glove-friendly Operator Console (`/operator/`) with giant counters & numpad.<br>• 1-Touch Stoppage classification & split modal.<br>• Maintenance call/cancel dispatch.<br>• Supervisor Floor matrix (`/floor/`) with 20-machine card view.<br>• Juran 80/20 Pareto and MTBF/MTTR reliability analytics.<br>• Digital SMED 4-phase changeover stopwatch.<br>• Shift handover 3-step wizard. | Complete operator breakdown-to-release journey; shift handover closes cleanly. | Pending |
| **5** | **Quality SPC, Weight Giveaway, Alerts & Alarm Storm Engine**<br>• ISO 22400-2 SPC charts (X-bar, R chart).<br>• Gaussian normal distribution bell curve & Cp/Cpk.<br>• Overfill weight giveaway calculator & recalibration slider.<br>• Real-time alerts engine with suppression window & deduplication.<br>• Global notification drawer with live unread badge. | Sample fixtures match statistical calculations; alerts trigger, deduplicate, and auto-resolve. | Pending |
| **6** | **Production Planning, Work Orders & ERP Sync**<br>• Work order central dispatch, routing stages, and progress bars.<br>• Machine assignment matrix and staging progress.<br>• Material delivery & staging checklist.<br>• ERP / Odoo synchronization adapter & conflict queue.<br>• *(Note: Engineering Drawings & SOP Approvals removed from system per user request).* | Complete work-order lifecycle and sync retry verified. | Pending |
| **7** | **Industrial AI Copilot, Shift Reports & Notifications**<br>• Dual-Engine AI Copilot (Gemini Cloud API + Offline Deterministic Heuristics).<br>• Bilingual natural language Q&A with interactive action chips.<br>• Standardized Shift Handover PDF and multi-tab Excel (.xlsx) exports.<br>• Automated report subscriptions & email/Telegram dispatch workers.<br>• Historical data explorer with multi-dimensional filters. | Copilot answers scoped queries in EN & AR; reports match UI figures exactly. | Pending |
| **8** | **Integration, Hardening, Observability & Final Acceptance**<br>• Comprehensive end-to-end regression testing across all 9 roles.<br>• Security audit (CSRF, session exclusivity, brute-force protection, audit logs).<br>• Kiosk force-logout lockout validation.<br>• Performance tuning, caching, and production container setup.<br>• Complete user manual and feature acceptance report. | All active features verified against acceptance criteria; zero silent deferrals. | Pending |

---

## 4. Master Feature Checklist (F01 – F20)

- [ ] **F01: Factory Hierarchy & Master Data** — Factory, Line, Machine hierarchy, SKU, rates, shifts, taxonomies. *(Batch 2)*
- [ ] **F02: Telemetry Ingestion & Live Pipeline** — Ingestion endpoint, state machine, watchdog, 1 Hz SSE stream. *(Batch 3)*
- [ ] **F03: OEE & Loss Calculation Engine** — Availability, Performance, Quality, Bottleneck cadence, Six Big Losses, downtime costs. *(Batch 3)*
- [ ] **F04: Executive Overview & Dashboard** — "So What?" banner, benchmark gauges, waterfall, pacing chart, conveyor strip. *(Batch 5)*
- [ ] **F05: Operator Touch Console** — Touch HMI, state banner, 2-level classification, split stops, scrap numpad, scale weight entry, maintenance call. *(Batch 4)*
- [ ] **F06: Stoppages & SMED Intelligence** — Active registry, 80/20 Pareto, MTBF/MTTR/MTTF, 4-phase SMED stopwatch. *(Batch 4)*
- [ ] **F07: Quality SPC & Giveaway Analysis** — X-bar / R charts, Gaussian curve, Cp/Cpk, giveaway financial calculator, recalibration slider. *(Batch 5)*
- [ ] **F08: Real-Time Alerts & Deduplication** — Configurable rules, suppression window, auto-resolve watchdog, notification drawer. *(Batch 5)*
- [ ] **F09: Industrial AI Copilot** — Cloud Gemini function-calling, deterministic offline engine, EN/AR bilingual queries, action chips. *(Batch 7)*
- [ ] **F10: Shift Handover & Production Reporting** — 4-bullet executive summary, PDF/XLSX export, automated subscriptions. *(Batch 7)*
- [ ] **F11: Onboarding Wizard & Topology** — 60-second wizard, presets, SVG node graph, gateway QR claim, KPI glossary. *(Batch 2)*
- [ ] **F12: Signal Simulator & Demo Controller** — Synthetic telemetry, 1x/2x/5x/10x clock multiplier, 5 scenarios, manual overrides, demo badge. *(Batch 3)*
- [ ] **F13: REST & Streaming API Directory** — All API endpoints documented and tested. *(Batches 1–7)*
- [x] **F14: Shared Shell, Theme & Localization** — Reusable application shell, light reference theme, EN/AR with RTL support, responsive layout. *(Batch 1)*
- [ ] **F15: Live Floor Matrix & Shift Handover** — Machine card grid, operator context, shift progress, 3-step handoff wizard. *(Batch 4)*
- [ ] **F16: Maintenance Kanban & Repair Lifecycle** — Incident board, clock-in, spare parts request, root cause logging, release workflow. *(Batch 4)*
- [x] **F17: Engineering Drawings & Document Approvals** — *REMOVED: Feature excluded per explicit user instruction.*
- [ ] **F18: Planning, Work Orders & ERP Sync** — Central dispatch, machine assignment calendar, process routing, material tracking. *(Batch 6)*
- [ ] **F19: Device Enrollment & Alert Automation** — Kiosk pairing, shift copy utility, alert email/bot rules, historical data explorer. *(Batch 2, 7)*
- [x] **F20: Multi-Role RBAC & Kiosk Security** — Canonical personas, scoped permissions, persona switcher, server-side authorization enforcement. *(Batch 1)*

---

## 5. Batch 1 Implementation Scope & Checklist

### 5.1 Project Foundation
- [x] Standardized project structure: Django project `factsense` with modular apps:
  - `core`: Base models, common utilities, context processors, middleware.
  - `accounts`: User authentication, roles, assignments, persona switcher, scoped permissions.
  - `masterdata`: Products reference view matching screenshot, factory/line/machine models skeleton.
  - `portal`: Role-specific landing pages and module routers.
- [x] Static assets & styling:
  - Curated vanilla CSS design system based on the reference Product Management screenshot.
  - Arabic and English typography with full RTL support.
  - Reusable UI component templates (navbar, tables, forms, pills, alerts, badges).

### 5.2 Roles, RBAC & Persona Switching
- [x] Canonical 9 Roles defined (Engineering removed per user request):
  1. `operator` (Operator Touch Console — `/operator/`)
  2. `supervisor` (Floor Monitor — `/floor/`)
  3. `maintenance` (Maintenance Hub — `/maintenance/`)
  4. `quality` (Quality & SPC — `/quality/`)
  5. `planner` (Planning & Products — `/planning/`)
  6. `supply_chain` (Work Orders & ERP — `/work-orders/`)
  7. `manager` (Executive Dashboard — `/dashboard/`)
  8. `admin` (System Administration — `/administration/`)
  9. `controller` (Simulation Controller — `/controller/`)
- [x] Scoped Permissions Model:
  - User assignments with Factory and Line scoping.
  - Active role stored in server-side session.
  - Persona switcher dropdown in top navigation for multi-role users.
  - Role-based server-side view protection (`@role_required`, `RoleRequiredMixin`).
  - Scoped data access validation.
- [x] Seeded Demo Accounts:
  - Single-role demo accounts for all 9 roles.
  - Multi-role demo accounts (e.g. `lead_tech` with supervisor + maintenance, `ops_manager` with manager + planner).
  - Quick-switch demo account bar for effortless developer and reviewer testing.

### 5.3 UI & Localization
- [x] Master Application Shell:
  - Horizontal white top bar with brand workspace title.
  - Role-specific navigation links with active state indicator.
  - Bilingual switcher (`EN` / `العربية`) with seamless RTL layout flip.
  - User account menu with active role, switch role list, and logout.
- [x] Reference Product Management Page (`/planning/products/` and `/masterdata/products/`):
  - Closely matches reference screenshot:
    - Heading "Product Management" with explanatory subtitle.
    - Prominent green "Add Product" button.
    - Full-width table with Product Name, Code, UOM, Design/SOP Link, Ideal Cycle Time, Processes, and permitted Actions.
    - Process badges (`#DBEAFE` with blue text).
    - Permitted action buttons (View, Edit, Archive).
    - Compact search filter and pagination.
- [x] Honest Under-Development States:
  - Pages scheduled for Batches 2–7 display a standardized, informative "Batch X: Under Development" industrial placeholder showing the module's roadmap, planned capabilities, and authorized role access.

---

## 6. Verification and Acceptance Results for Batch 1

### 6.1 Automated Test Execution Summary
Automated test suite `apps.accounts.tests` executed via `python manage.py test apps.accounts.tests`:
- **Total Tests Ran:** 10
- **Failures:** 0
- **Errors:** 0
- **Status:** **OK (All 10 tests passed in 61.2s)**

Verified capabilities:
1. `test_all_10_canonical_roles_exist`: Confirmed `operator`, `supervisor`, `maintenance`, `engineer`, `quality`, `planner`, `supply_chain`, `manager`, `admin`, `controller` all exist with correct defaults.
2. `test_login_and_dynamic_role_landing_resolution`: Confirmed each role logs in and lands directly on their designated workspace without hardcoded cascade `if/elif` statements.
3. `test_multi_role_persona_switching_without_relogin`: Confirmed `lead_tech` (Supervisor + Maintenance) toggles persona dynamically; session `active_role`, workspace home, and audit log update cleanly.
4. `test_unauthorized_role_switch_denied`: Confirmed switching to an unassigned role is rejected server-side.
5. `test_operator_cannot_access_manager_dashboard`: Confirmed operator accessing `/dashboard/` receives **HTTP 403 Forbidden**.
6. `test_operator_cannot_access_administration`: Confirmed operator accessing `/administration/` receives **HTTP 403 Forbidden**.
7. `test_quality_cannot_access_controller`: Confirmed quality specialist accessing `/controller/` receives **HTTP 403 Forbidden**.
8. `test_unauthenticated_request_redirects_to_login`: Confirmed unauthenticated requests redirect to `/login/`.
9. `test_bilingual_language_switching_and_rtl`: Confirmed Arabic mode applies `dir="rtl"` and Arabic typography; English restores `dir="ltr"`.
10. `test_product_management_page_and_archival`: Confirmed Planner can add, edit, and archive products; archival preserves historical records with `is_archived=True`.

### 6.2 Seeded Demo Credentials for UI Review
All accounts use standard password: `Factsense@2026`

| Persona | Username | Landing Page | Key Visibility & Responsibilities |
|---|---|---|---|
| **Production Planner** | `planner_demo` | `/planning/products/` | Product Management reference view, cycle times, process routings |
| **Shift Supervisor** | `supervisor_demo` | `/floor/` | Floor overview, shifts, stoppages, maintenance, reports |
| **Line Operator** | `operator_demo` | `/operator/` | Machine console (#FL-01), good/scrap counters, state banner |
| **Maintenance Tech** | `maintenance_demo` | `/maintenance/` | Maintenance operations center, Kanban incident board |
| **Quality Specialist** | `quality_demo` | `/quality/` | SPC charts (X-bar/R), giveaway calculator, defect logs |
| **Supply Chain Officer** | `supply_demo` | `/work-orders/` | Work orders dispatch, scheduling matrix, ERP sync queue |
| **Plant Director** | `manager_demo` | `/dashboard/` | Executive OEE gauges, Six Big Losses waterfall, costs |
| **System Admin** | `admin_demo` | `/administration/` | User scopes, role boundaries, machine assets, audit trail |
| **Demo Controller** | `controller_demo` | `/controller/` | Telemetry simulation, scenario injection, clock multiplier |
| **Multi-Role Tech** | `lead_tech` | `/floor/` & `/maintenance/` | Switch between Supervisor and Maintenance from account dropdown |
| **Multi-Role Ops Head** | `ops_manager` | `/dashboard/` & `/planning/products/` | Switch between Plant Director and Production Planner |

