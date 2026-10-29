# FactSense — New Web App Build Specification

**Version:** 1.1 · **Date:** 29 October 2026 · **Status:** Proposed implementation specification

## 1. Build objective and source precedence

Build a new, complete industrial MES, IIoT and OEE web application. Use the unified UI structure and user organization from `UI_STRUCTURE_AND_ROLE_ORGANIZATION(1).md`, and implement every feature in `SYSTEM_FEATURES_SPECIFICATION(1).md`. Preserve the additional operational workflows in the UI document as well.

This is a specification for a new application, not a claim that any functionality has been implemented. FactSense is the working product name; branding must be configurable.

The document is self-contained:

- **Sections 1–12:** Integrated implementation decisions, roles, navigation, permissions, delivery plan and acceptance criteria.
- **Appendix A:** Complete, unchanged system feature source, including detailed modules, API directory and data fields.
- **Appendix B:** Complete, unchanged UI and role source, including screens and workflows.

**Precedence:** The user-supplied Product Management screenshot defines the visual direction: a simple light interface with horizontal navigation and table-based pages. Section 2 below takes precedence over complex dashboard styling, permanent navigations and decorative visual treatments in either appendix. Sections 1–12 resolve other conflicts between the sources. Appendix A defines the complete feature baseline. Appendix B defines UI organization and its additional workflows. Historical audit claims, old application names, approval labels and rollout estimates in the appendices describe the original documents, not the new project's verified state. No feature may be silently removed or replaced by a mockup. Delivery phases organize implementation; they do not reduce final scope.

## 2. Core architecture and UI

Recommended implementation baseline: Django with PostgreSQL, Redis, background workers for reports/alerts/simulation, Django templates, compiled CSS, Alpine.js and HTMX. Use SSE for approximately one-second live updates and a polling fallback. Choose supported dependency versions during implementation and pin them; the old version numbers in Appendix B are not binding.

### 2.1 Primary design direction — simple like the supplied screenshot

Build FactSense with the same straightforward structure as the reference Product Management page: white horizontal navigation, pale gray background, clear heading and short description, a green primary action, and a wide white table. Preserve all functionality while making daily work easy to understand. The screenshot is the visual reference; use FactSense branding and the current user's authorized pages.

| Area | Required implementation |
|---|---|
| Header | White bar, FactSense/role workspace name on the left, plain text navigation links, EN/AR and account/logout on the right |
| Navigation | Horizontal, role-specific links; selected page clearly highlighted; no permanent desktop navigation |
| Page heading | Clear title such as “Product Management”, one short description and one main action such as “Add Product” |
| Content | Wide white table or simple form on a pale gray page; comfortable margins, subtle borders, restrained rounding |
| Table | Clear column headings, light alternating rows, readable text, small status/process pills, visible permitted actions |
| Search and filters | Compact row above the table; advanced filters collapsed under “More filters” |
| Forms | Clearly labeled fields, simple validation, Save and Cancel; separate page or straightforward modal according to form size |
| Context | Factory/line/shift selectors only on pages that need them; show fixed assignment as a label when there is no choice |
| Account | Show current role; multi-role switcher only for users with multiple assignments; theme preference inside account menu |
| Mobile | Collapse navigation into a labeled menu; prioritize table columns and allow horizontal scrolling for remaining data |
| Live data | Small Live / Reconnecting / Last updated indicator on operational pages; no distracting continuous animation |

Suggested approximate visual tokens based on the screenshot: page background `#F3F4F6`, surface `#FFFFFF`, body text `#111827`, secondary text `#64748B`, borders `#E5E7EB`, links/brand `#2563EB`, primary Add/Save action `#16A34A`, destructive actions `#EF4444`, process pills `#DBEAFE` with blue text. These are implementation approximations, not exact sampled colors.

Use a clean sans-serif font with Arabic support and 14–16 px body text. Default to the simple light theme. Retain an optional dark theme through account preferences. Support EN/AR and RTL without losing entered values. Use tabular numerals for counters. Ensure keyboard access and labels; keep touch targets at least 48×48 px on kiosk/tablet layouts and primary kiosk actions at least 64 px high.

### 2.2 Role navigation examples

These menus illustrate the existing permissions; showing a link never grants additional access. Keep about five to seven primary links where practical, placing remaining authorized pages in a clearly labeled More menu or a related page's tabs. Do not show unavailable modules.

| Active role | Simple top navigation |
|---|---|
| Operator | My Machine · Production · Stoppages · Documents |
| Supervisor | Floor · Shifts · Stoppages · Maintenance · Reports · More (SMED, Alerts, Copilot) |
| Maintenance | Tickets · Machines · Spare Requests · History · More (Reliability, Alerts, Copilot) |
| Engineer | Documents · Reviews · Floor |
| Quality | Quality · Samples · Defects · Approvals · More (Giveaway, Reports, Alerts, Copilot) |
| Planner | Products · Shifts · Work Orders · Processes · More (Rates, Reasons, Alerts, Reports, Copilot) |
| Supply Chain | Work Orders · Schedule · Materials · ERP Sync · Reports |
| Manager | Overview · Floor · Reports · Approvals · More (Quality, Losses, Alerts, Copilot) |
| Admin | Users · Roles · Machines · Settings · More (Gateways, Integrations, Audit) |
| Controller | Simulation · Scenarios · Machines · Shift Control |

### 2.3 Simple page patterns for every module

| Module | Default presentation | Deeper functionality |
|---|---|---|
| Products/master data | Searchable table and Add button, matching the reference | Edit form, rates, processes and specifications in detail tabs |
| Operator | Machine/order header, good/scrap counters and large task buttons | Classification, weights, changeover and SOP actions opened when needed |
| Floor | Small machine cards or table with machine, state, output and active order | Machine detail page with telemetry and history |
| Stoppages | Event table with duration, reason, status and Classify action | Split/reclassify forms; Pareto and reliability in Analytics tab |
| Maintenance | Ticket list with priority, machine, technician and status | Ticket details and workflow actions; optional Board tab retains Kanban |
| Quality | Sample table and brief quality summary | SPC, distribution, capability and giveaway in clearly named tabs |
| Documents | Document list with revision, approval state and action | Revision comparison and step-by-step approval on detail page |
| Work orders | Order table with product, quantity, machine, shift and status | Routing, allocation calendar, materials and ERP sync in related tabs |
| Executive overview | A small set of useful KPIs, production summary and exceptions | Waterfall, benchmarking and detailed charts on Analytics tabs |
| Reports | Date/shift filters and clear PDF / Excel buttons | Report history and subscriptions in separate tabs |
| Controller | Start/Pause, scenario selector and clock speed | Per-machine overrides and reset behind clearly labeled controls |

All advanced features remain accessible to authorized roles. Simplify their presentation through pages, tabs and details; do not delete them. Keep the topology graph, conveyor view, SPC charts, SMED timer, approval tracker and copilot in their relevant views rather than crowding every page.

### 2.4 Product Management reference acceptance

The default Products page must closely follow the supplied screenshot's structure:

1. White horizontal role navigation at the top.
2. “Product Management” heading with a short explanation below.
3. Green “Add Product” button aligned with the heading for authorized editors.
4. A full-width white table with Product Name, Code, UOM, Design/SOP Link, Ideal Cycle Time, Processes and Actions.
5. Light-blue process pills, blue View/Edit links and a red Delete action only where permitted. Confirm deletion; archive products with referenced history rather than destroying records.
6. Search, pagination and an empty state that explains how to add the first product.
7. Product names support Arabic and English. State cycle-time units explicitly; model machine-specific rates in a detail view instead of implying one universal product rate.

Avoid decorative gauges on CRUD pages, oversized banners, excessive cards, crowded toolbars and technical diagnostics in ordinary users' screens. Give immediate, plain-language feedback such as “Product saved”. Preserve the industrial status colors for operational status, paired with text/icons.

## 3. Users, roles and scoped access

One user can have multiple role assignments. Each assignment includes allowed factories, lines and optionally machines. A user sees only the pages, data and actions allowed by the selected role within that assignment. All grants below are proposed defaults inferred from the two sources.

| Canonical role | Source names mapped to it | Home | Responsibility and visibility |
|---|---|---|---|
| `operator` | operator, operators | `/operator/` | Assigned machine console, active order, production/scrap/weights, own machine events, approved SOPs |
| `supervisor` | supervisor, shift-leaders | `/floor/` | Assigned floor, shift output, exceptions, stoppages, SMED, dispatch and handover approval |
| `maintenance` | maintenance | `/maintenance/` | Assigned assets, alarms, repair tickets, spares, root causes, reliability and release |
| `engineer` | designers (drawing/design duties) | `/engineering/` | Drawings, SOP revisions, review requests and assigned design approval stages |
| `quality` | quality, designers (QC duties) | `/quality/` | SPC, samples, defects, giveaway, quality exports and assigned quality approval stages |
| `planner` | planners | `/planning/` | Products, rates, processes, shifts, production plans and work-order allocation |
| `supply_chain` | supply_chain | `/work-orders/` | ERP synchronization, work orders, material delivery and stage progress |
| `manager` | manager, management | `/dashboard/` | Assigned plant performance, costs, benchmarking, reports and designated final document approvals |
| `admin` | admin | `/administration/` | Users, scoped role assignments, configuration, gateways, integrations, audit and system operations |
| `controller` | controller, Demo Master | `/controller/` | Simulation-only plants, scenarios, speed multiplier, overrides and resets |

Splitting engineering from quality and administration from simulation preserves every source responsibility while avoiding automatic access to unrelated tasks. A combined Design/QC user receives both assignments. The administrator can configure the system but does not automatically act as an operator or business approver; grant the relevant additional role explicitly. This intentionally narrows the legacy admin “Full” cells.

### 3.1 Authorization rules

1. Resolve role assignments on login. If one exists, open its home; if several exist, use the last still-authorized persona or show a role selection page. No first-match `if/elif` role routing.
2. Store `active_role` server-side and validate it on every request. Role switching changes home, navigation, actions and scope without requiring another login. Roles are not combined invisibly in one persona.
3. Every backend operation checks authentication, active-role permission, object scope and workflow state. Hiding navigation is not authorization.
4. Apply the same policy to list/detail APIs, downloads, exports, SSE subscriptions, notification counts, search, report jobs and AI tool calls. A guessed object ID never grants access.
5. No assignment means no operational access. Revocations take effect for existing sessions and streams. Audit actor, active role, scope, timestamp, action and important before/after values.
6. Changing context clears incompatible selected records and subscriptions. Selectors list authorized objects only.

### 3.2 Default action permissions

All permissions are limited to assigned scope. Unlisted actions are denied. Read access does not imply export, editing or approval rights.

| Action | Roles allowed by default | Constraint |
|---|---|---|
| Operate kiosk; enter good pieces, scrap and weights | Operator | Assigned machine and open shift/order |
| View kiosk without operating | Supervisor, maintenance, manager | No production mutations |
| Correct production entries | Supervisor | Reason required; append correction audit |
| Trigger breakdown | Operator, supervisor, maintenance | Assigned asset |
| Read floor status | Supervisor, maintenance, engineer, quality, planner, supply_chain, manager | No unauthorized personal/financial detail |
| Classify/split stops | Operator, supervisor | Operator limited to assigned current-shift events; supervisor reviews |
| Reclassify approved history | Supervisor | Version/audit and reason required |
| Start changeover | Operator, supervisor | Approved target SKU/order |
| Advance SMED and record ramp-up | Operator, supervisor | Assignment and phase-state checks |
| Open maintenance ticket | Operator, supervisor, maintenance, engineer, quality | Assigned asset |
| Repair, wait for spares, test and release | Maintenance | Root cause and solution mandatory; release lock only through workflow |
| Verify maintenance completion | Supervisor | Scoped verification; cannot invent repair records |
| Read SPC, capability and giveaway | Quality, supervisor, manager | Scoped datasets; costs require finance visibility |
| Create/revise drawings or SOPs | Engineer | New revision; never overwrite approved version |
| Approve documents | Assigned engineer, quality or manager approver | Sequential stage; no self-approval |
| Read current approved machine documents | Operator, supervisor, maintenance, engineer, quality | Correct machine/product/process binding |
| Create/schedule/edit work orders | Planner, supply_chain | One shared work-order source of truth |
| View active order | Operator, supervisor, manager | Operator limited to assigned active order |
| Maintain products, rates, routes and shifts | Planner, admin | Changes effective-dated where calculations depend on them |
| Propose maintenance reason | Maintenance | Planner/admin accepts into taxonomy |
| Manage assets, gateway binding and integrations | Admin | Scoped administration; credentials never exposed in UI |
| Configure alert/report rules | Planner, admin | Recipient and data-scope validation |
| Acknowledge/resolve alerts | Maintenance, supervisor; quality for quality alerts | Rule-specific recovery; resolution does not close repair ticket |
| Approve shift handover | Supervisor | Pending issues reconciled or explicitly carried forward |
| Read executive/financial analytics | Manager | Assigned plants and authorized currency/cost fields |
| Export reports | Supervisor, maintenance, quality, planner, supply_chain, manager | Shift, maintenance, QC, planning, order or plant datasets respectively |
| Use copilot | Supervisor, maintenance, quality, planner, manager | Read-only permitted data and permitted action links |
| Manage users/roles and system settings | Admin | Audit every change |
| Read audit | Admin; manager for business audit | Manager cannot see secrets or technical credentials |
| Control simulator | Controller | Simulation environment only |

### 3.3 Kiosk binding and locking

Pair devices using a server-issued identity or enrolled-device token. Retain MAC/IP as asset metadata; do not assume browsers can securely supply a hardware MAC. A supervisor override requires supervisor authentication/PIN, rate limits and an audit record.

Enforce one active operator session per operator and one active operator per machine. Transferring the operator to another machine invalidates the previous session transactionally. Maintenance force-lock invalidates operator sessions, rejects production writes server-side and blocks new logins until authorized release. The app lock is an operational workflow, not a replacement for physical machine safety isolation. Keep production, gateway and manual entry events separately attributable and prevent double counting.

## 4. Page and navigation map

| Navigation group | Pages | Visible personas |
|---|---|---|
| Overview | Executive `/dashboard/`, live floor `/floor/`, topology viewer | Manager; floor viewers as granted above |
| Production | `/operator/`, `/shifts/`, `/stoppages/`, `/smed/` | Operator's console; supervisor operations; maintenance reliability view |
| Maintenance | `/maintenance/`, ticket detail, spares and repair history | Maintenance; supervisor dispatch/verification |
| Quality | `/quality/`, SPC, samples, capability, giveaway | Quality; supervisor/manager authorized analytics |
| Engineering | `/engineering/`, revision comparison, approval inbox | Engineer, quality and manager according to assigned approval stage |
| Planning & Supply Chain | `/planning/`, `/work-orders/`, process routing, material delivery, ERP sync | Planner and supply_chain; scoped read views for operator/supervisor/manager |
| Intelligence | `/alerts/`, `/copilot/`, `/reports/`, KPI glossary/help | Authorized personas only; domain-filtered content |
| Master Data | `/masterdata/`, wizard, topology editor, production masters, shifts, automation | Planner for production/shift/automation; admin for all configuration |
| Administration | Users, role/scope assignments, gateway QR onboarding, integrations, audit, diagnostics | Admin |
| Demo Control | `/controller/`, scenarios, overrides, clock and reset | Controller only |

Preserve the detailed API routes in Appendix A. `/management/` can redirect to the supervisor floor page after permission checks. Existing document routes may be retained as aliases, but do not create duplicate work-order records or separate settings silos.

## 5. Complete feature coverage and ownership

The following checklist links every major source section to the new app. The full subfeatures, payloads and fields remain mandatory in the appendices.

| ID | Required capability | UI owner / implementation destination | Source |
|---|---|---|---|
| F01 | Factory, line, machine hierarchy; asset categories; SKU, rates, shifts, taxonomies | Master Data | A §4 |
| F02 | Telemetry pulses, speed, state, vibration, temperature, recipe; watchdog; 1 Hz SSE | Ingestion services, floor and kiosk | A §5 |
| F03 | A/P/Q/OEE; bottleneck cadence; Six Big Losses; downtime/scrap costs | Calculation services, executive analytics | A §6 |
| F04 | Executive summary, benchmark gauges, waterfall, pacing, hourly chart, conveyor strip, dispatch | Dashboard / Floor | A §7.1 |
| F05 | Machine tabs, state banner, classify/split stops, defects, weights, maintenance call/cancel, changeover | Operator Kiosk | A §7.2; B §4.1 |
| F06 | Active/unclassified stops, duration/frequency Pareto, MTBF/MTTR/MTTF/failure rate, four SMED phases | Stoppages / SMED | A §7.3 |
| F07 | X-bar/R charts, Gaussian distribution, Cp/Cpk, giveaway costs, recalibration slider, raw exports | Quality | A §7.4 |
| F08 | Scoped rules, downtime/speed/defect/weight/vibration/temperature alerts, cooldown, deduplication, recovery, drawer | Alerts / Automation | A §7.5 |
| F09 | Cloud function-calling copilot, deterministic offline fallback, EN/AR questions, scoped context and action chips | Copilot | A §7.6 |
| F10 | Four-bullet shift summary, A/P/Q, counts/targets, top stops, defects, attendance, PDF/XLSX, subscriptions | Reports / Shift Handover | A §7.7 |
| F11 | Water/CSD/oil presets, rapid wizard, SVG topology and telemetry drawer, gateway claim QR, printable plans/orders, glossary | Master Data / Planning / Help | A §7.8 |
| F12 | Synthetic telemetry, pause and 1/2/5/10× clock, five scenarios, overrides, transition/reset, demo badge | Controller | A §7.9 |
| F13 | All REST/stream operations and all core fields | API and database layers | A §8–9 |
| F14 | Shared shell, themes, EN/AR, responsive devices, touch controls, live feedback | Shared frontend | A §10; B §2–3, §6 |
| F15 | Floor matrix, operator/work-order context, shift summary and three-step handover | Floor / Shifts | B §4.2 |
| F16 | Kanban repair workflow, repair clock-in, spare requests, testing, mandatory root cause/solution, release | Maintenance | B §4.3 |
| F17 | Drawing/SOP drafts, revision comparisons, sequential signed approvals, rejection feedback, archival | Engineering | B §4.4 |
| F18 | Odoo/ERP sync, central dispatch, shift/machine assignment calendar, routing and stage progress, material tracking | Planning / Work Orders | B §4.5, §5.1 |
| F19 | Device pairing, production masters, shift copy, email/Telegram rules, subscriptions and historical explorer | Master Data / Administration | B §4.6 |
| F20 | Multi-role personas, scoped access, kiosk session exclusivity and maintenance locking | Identity / authorization | B §5 |

All five simulator scenarios must be available: Cap Chute Jam, Overfill Giveaway Drift, Mechanical Breakdown, Defect Burst and Golden Run. Simulations must feed the same calculation pipeline as live telemetry, with explicit data separation. Golden Run's 95% figure is a scenario target; displayed OEE must be calculated rather than hardcoded.

## 6. Workflow and calculation decisions

These decisions resolve ambiguities in the sources and are the implementation authority.

- **Machine states:** Keep eight primary states: RUNNING, UNPLANNED_DOWNTIME, PLANNED_DOWNTIME, CHANGEOVER, MICRO_STOP, BLOCKED, STARVED, NO_DATA. Map incoming IDLE to MICRO_STOP only when duration/context qualifies; otherwise classify according to configured policy. Record speed loss as a performance condition, not another primary state. Maintenance and waiting-spares are ticket states/overlays.
- **OEE time basis:** Planned production time = scheduled window minus explicitly excluded breaks. Operating time = planned production time minus included availability-loss intervals. Availability = operating/planned production time. Performance = total units/(operating minutes × ideal units/minute). Quality = good/total units. OEE = A×P×Q. Do not subtract breaks twice. Aggregate variable products/rates using interval-specific ideal times; never average percentages blindly.
- **Data validity:** Zero denominators yield N/A with reason; missing telemetry is unknown, not automatically zero output or equipment failure. Expose coverage. Flag performance above 100% as a configuration/data issue rather than silently changing source counts. Rework/quarantine must not be counted as good until accepted; avoid counting the same unit twice.
- **Loss attribution:** Every interval has one primary accounting category. Track upstream/downstream consequences separately so one line outage is not counted once per machine. Splits partition the original interval without gaps/overlaps; preserve parent history and reclassification audit.
- **Costs:** Lost-output opportunity cost = downtime minutes × ideal units/minute × unit margin. Scrap cost = scrap quantity × configured unit cost. Clearly separate opportunity cost, actual scrap cost and giveaway; require margin, density/unit conversions and currency inputs rather than assuming them.
- **SPC:** Configure subgroup size, baseline and limit calculation method; distinguish control limits from product specification limits. Cp/Cpk are unavailable when samples are insufficient or variation is zero. The slider is an estimate based on assumptions and does not prove zero underfill risk or regulatory compliance. Source references to ISO are design intent, not a certification claim.
- **Maintenance:** OPEN → ASSIGNED → IN_PROGRESS → WAITING_SPARES → IN_PROGRESS → TESTING → RESOLVED → CLOSED. Allow direct IN_PROGRESS → TESTING. Supervisor verifies before CLOSED; maintenance releases the machine after successful testing. Waiting may pause configured SLA time, but elapsed downtime continues. A cancelled operator call cannot clear an active repair lock.
- **Alerts:** ACTIVE → ACKNOWLEDGED → RESOLVED. Auto-resolve using each rule's actual recovery condition, not merely RUNNING. Alarm resolution and maintenance ticket closure are separate.
- **Documents:** DRAFT → PENDING_REVIEW → APPROVED → ARCHIVED, with rejection returning to editable draft. Freeze submitted revisions; a new revision cannot displace the current approved version until all required stages pass. Record approver identity, timestamp and revision digest for application-level signatures.
- **Work orders:** SCHEDULED → IN_PRODUCTION → COMPLETED or SHORT_CLOSED. Require short-close reason. Enforce ordered process steps and validated quantities; audit reassignment. ERP sync uses external IDs, idempotency, retry status and a visible conflict queue.
- **Shift closure:** Review unresolved tickets; reconcile counts; capture notes and sign-off. Carry open events into the next shift without duplicating them. Persist dated shift instances including overnight shifts in the factory timezone.

## 7. Data and service additions

Implement all Appendix A models and fields, extending them for the UI workflows:

| Domain | Additional records / requirements |
|---|---|
| Identity | Role, Permission, UserRoleAssignment with scope, DeviceEnrollment, OperatorSession, AuditEvent |
| Time/production | ShiftInstance, ProductionPlan, WorkOrder, WorkOrderOperation, ProductRoute, Operation, ProductionEntry/Correction, OperatorAttendance |
| Telemetry | RawTelemetryEvent with source/event ID/time, gateway credentials, sequence/deduplication state, source type LIVE/DEMO |
| Maintenance | Repair log, spare request, ticket transitions, testing evidence, release record and SLA policy |
| Documents | Document, immutable Revision, ApprovalWorkflow, ApprovalStep and ApprovalDecision |
| Planning/integration | MachineShiftAssignment, MaterialDelivery, ERPMapping, SyncRun/Conflict |
| Quality | Subgroup/baseline, sample audit, quarantine disposition and cost assumptions |
| Reporting/demo | ReportJob, scoped subscription, delivery attempt, SimulationRun and ScenarioExecution |

Extend DefectLog to include QUARANTINE from the reason taxonomy. Unify the source's DowntimeEvent/StoppageEvent terminology under one event model. Store timestamped facts in UTC and display plant-local times. Keep rated-speed and product-cost history sufficient to reproduce old reports. Preserve raw facts when correcting derived values.

Ingestion must authenticate gateways and bind them to machines; validate payloads, deduplicate retries, handle counter resets/rollover and out-of-order events, and record receipt time separately from event time. Service calls and UI mutations need validation, CSRF/session protection where applicable and concurrency controls. Background jobs recheck scope before generating and delivering exports.

Add protected endpoints for user-role switching, maintenance transitions, document revisions/approvals, work-order scheduling, material delivery, ERP sync and master-data changes. Document request/response schemas, error states, permissions and idempotency behavior for these alongside Appendix A's API directory.

## 8. End-to-end user journeys

1. **Operator:** Log in on paired kiosk → open assigned machine/order → enter or receive production counts → report breakdown → maintenance lock blocks writes → technician tests/releases → resume authorized production.
2. **Supervisor:** Open assigned floor → inspect stopped machine → dispatch maintenance → review/split stop → check production totals → complete handover with unresolved issues carried forward.
3. **Maintenance:** Accept ticket → clock in → request spare if needed → record repair/root cause → test → release machine → supervisor verifies closure.
4. **Quality and engineering:** Engineer submits revision → configured design/QC/production approvers review in order → approved revision becomes visible at matching kiosk; quality monitors samples and investigates capability/giveaway separately.
5. **Planner and supply chain:** Create/import one work order → allocate machine/shift and routing → track material delivery → monitor operation completion → complete/short-close with reconciliation.
6. **Manager:** Select authorized plant/shift → inspect OEE/losses/costs → query scoped copilot → export consistent PDF and Excel.
7. **Controller:** Select demo plant → run scenario and clock multiplier → observe real calculation/alert effects → trigger shift report → reset only simulation records.

## 9. Delivery batches and completion gates

| Batch | Deliverable | Gate before completion |
|---|---|---|
| 1 | Project, shared shell, user roles/scopes, seeded personas, EN/AR and themes | Each persona reaches correct home; unauthorized direct requests denied |
| 2 | Master data, shifts, product/rate history, wizard and gateway pairing | Create a usable line and scoped kiosk session |
| 3 | Telemetry, state intervals, OEE/loss engine, SSE and controller | Reproducible fixture calculations; demo/live isolation; reconnect/deduplication work |
| 4 | Operator, floor, stops, SMED and maintenance | Complete breakdown-to-release and shift handover journeys |
| 5 | Quality, SPC, giveaway, executive analytics and alerts | Known sample fixtures match calculations; alerts recover and deduplicate correctly |
| 6 | Engineering approvals, planning, routing, material delivery and ERP sync | Approved-only kiosk documents; complete work-order lifecycle and sync retry |
| 7 | Copilot, PDF/Excel, subscriptions, Telegram/email and explorer | Scoped answers/exports; offline fallback; scheduled delivery retry |
| 8 | Integration, accessibility, security, deployment and business acceptance | All F01–F20 accepted with evidence; no silent feature deferrals |

For each batch provide implemented requirements, changed components, verification results, remaining gaps and next steps. Do not invent delivery-week commitments. Production integrations need configured credentials and mappings; when unavailable, provide an explicitly labeled development adapter and record the integration as pending validation.

## 10. Acceptance criteria

- Products and other administrative pages match Section 2’s simple screenshot-inspired structure. No permanent sidebar or dashboard-style clutter on CRUD pages. Each role sees only relevant navigation and permitted actions.

- Every F01–F20 row and each detailed appendix subfeature has a corresponding implementation and acceptance result.
- Operator sees only assigned machine operations, active order and approved documents; cannot reach financial dashboards, user administration or controller APIs.
- Multi-role supervisor/maintenance user switches persona without login; each persona has its own allowed navigation/actions and scope.
- Editing a URL, object ID, query parameter or API body cannot bypass role, factory, line or machine restrictions. Test list, detail, export, stream and copilot paths.
- Production entry retries do not duplicate counts. Manual adjustments and telemetry are reconciled explicitly. Two concurrent logins cannot violate kiosk exclusivity.
- Maintenance force-lock blocks both visible controls and backend writes until authorized release.
- Test known OEE results, cross-midnight shifts, planned breaks, zero output, product changes, counter reset, missing data and duplicated/out-of-order telemetry.
- Stop splits preserve total time; line losses do not multiply across blocked/starved assets.
- SMED records four phases, durations, benchmarks and ramp-up rejects correctly.
- SPC and giveaway calculations use known sample fixtures, correct units and clearly visible assumptions.
- Alerts have cooldown/recovery rules and do not close repair tickets inadvertently.
- Draft/rejected documents never become production-approved; approval order and no-self-approval are enforced.
- Work orders have one canonical record, enforce operation progress and handle repeated ERP imports without duplication.
- PDF/XLSX totals match the UI for identical context; scheduled reports respect recipient/data scope and configured timezone.
- Copilot respects permissions, labels offline engine use and never fabricates missing metrics; action chips link only to authorized pages.
- Simulator actions cannot mutate live plant records; all demo screens/exports identify simulated data.
- EN/AR, RTL, themes, responsive views, touch targets, validation messages, loading/empty/error states and stale-data indications are reviewed on representative devices.

## 11. Required implementation deliverables

Provide application source, database migrations, seed/demo data for every persona, reusable UI components, documented API contracts, automated checks for calculations/permissions/workflow transitions, deployment configuration, environment variable template without secrets, setup guide, role-based user guide and feature acceptance checklist. Include background-worker and streaming deployment configuration, backup/restore instructions and basic observability.

The final app must include functional backend workflows. Static cards, placeholder chart data and hidden menus alone do not satisfy this specification.

## 12. Build-agent instruction

> Build the new FactSense application using this document as the complete specification. Match the simple Product Management screenshot: light pages, white horizontal role navigation, clear headings, readable tables, simple forms and obvious action buttons. Keep every feature, but show advanced functionality on relevant tabs or detail pages. Follow Sections 1–12 for unified UI, canonical roles, scoped authorization, conflict resolution and delivery gates. Implement every detailed system feature in Appendix A and every additional UI/workflow requirement in Appendix B. Work in the stated batches, preserving full final scope. Keep permissions enforced server-side, use one shared shell, and verify each role's end-to-end journey. Record unresolved external integration requirements explicitly. Do not mark a feature complete solely because its UI is present.

---

# Appendix A — Complete system feature source

The following source is preserved verbatim for full coverage. Where it conflicts with Sections 1–12, the integrated decisions above apply.

# FactSense Platform — Complete Feature Specification & Architecture Catalog
> **Target Use Case:** Comprehensive reference blueprint for rebuilding the FactSense Smart Factory / Industrial IoT & OEE platform in a new project with a fresh, custom User Interface.

---

## Table of Contents
1. [Executive Summary & Core Concept](#1-executive-summary--core-concept)
2. [Global Architecture & Technology Matrix](#2-global-architecture--technology-matrix)
3. [User Personas & Role-Based Access Control (RBAC)](#3-user-personas--role-based-access-control-rbac)
4. [Master Data & Factory Topology](#4-master-data--factory-topology)
5. [Telemetry Ingestion & State Machine Engine](#5-telemetry-ingestion--state-machine-engine)
6. [OEE & Industrial Calculation Engine](#6-oee--industrial-calculation-engine)
7. [Module-by-Module Feature Specifications](#7-module-by-module-feature-specifications)
   - [7.1 Module 1: Management Overview & Executive OEE Dashboard](#71-module-1-management-overview--executive-oee-dashboard)
   - [7.2 Module 2: Operator Touch Console (Shop-Floor HMI)](#72-module-2-operator-touch-console-shop-floor-hmi)
   - [7.3 Module 3: Stoppages & SMED Changeover Intelligence](#73-module-3-stoppages--smed-changeover-intelligence)
   - [7.4 Module 4: Quality & Weight Giveaway SPC](#74-module-4-quality--weight-giveaway-spc)
   - [7.5 Module 5: Real-Time Alerts & Alarm Storm Engine](#75-module-5-real-time-alerts--alarm-storm-engine)
   - [7.6 Module 6: Industrial AI Copilot (Dual-Engine)](#76-module-6-industrial-ai-copilot-dual-engine)
   - [7.7 Module 7: Shift Handover & Production Reporting](#77-module-7-shift-handover--production-reporting)
   - [7.8 Module 8: Master Data Management & Onboarding Wizard](#78-module-8-master-data-management--onboarding-wizard)
   - [7.9 Module 9: Signal Simulator & Demo Controller](#79-module-9-signal-simulator--demo-controller)
8. [Comprehensive REST & Streaming API Directory](#8-comprehensive-rest--streaming-api-directory)
9. [Data Models & Schema Reference](#9-data-models--schema-reference)
10. [Key Frontend & UX Guidelines for the New UI](#10-key-frontend--ux-guidelines-for-the-new-ui)

---

## 1. Executive Summary & Core Concept

**FactSense** is an industrial-grade **Manufacturing Execution & Intelligence Platform (MES / IIoT)** tailored for high-speed automated production and packaging facilities (Food & Beverage, Bottling, FMCG, Pharma, Packaging, Plastics, and Discrete Manufacturing).

The platform bridges the gap between raw shop-floor machine telemetry (PLCs, photoelectric bottle pulse sensors, checkweighers, Modbus/MQTT gateways) and actionable decision-making across three distinct tiers:
1. **Machine Operators (Shop Floor):** Touchscreen-first HMI for one-tap downtime classification, defect scrap entry, scale weight sampling, and maintenance calling.
2. **Line Supervisors & Maintenance Engineers:** Live bottleneck tracking, 80/20 Pareto downtime analysis, digital SMED stopwatch, and MTBF/MTTR reliability metrics.
3. **Plant Directors & Operations Executives:** Plant-wide OEE tracking, TPM Six Big Losses financial waterfall, raw material giveaway overfill cost analysis, and automated shift handover reports.

---

## 2. Global Architecture & Technology Matrix

```
[Shop-Floor PLCs / Sensors / Checkweighers]
       │
       │ (Digital Pulses / Modbus TCP / MQTT / HTTP Webhooks)
       ▼
[Edge Gateway / Simulator Controller]
       │
       │ (JSON Payloads over HTTP POST or SSE / WebSockets)
       ▼
[Ingestion & Signal Pipeline]
       ├─ Machine State Evaluation (Running, Faulted, Micro-Stop, Blocked, Starved)
       ├─ Event Lifecycle Tracker (Start, Classify, Split, Clear Stoppages)
       └─ Telemetry Buffering (Vibration, Temperature, Cycle Times)
       │
       ▼
[Calculation & Analytics Engine]
       ├─ Dynamic Line Bottleneck Detection
       ├─ Standard OEE Engine (Availability × Performance × Quality)
       ├─ TPM Six Big Losses Allocation
       ├─ ISO 22400-2 SPC Engine (X-bar, R, Cp, Cpk, Normal Distribution)
       └─ Financial Downtime & Product Giveaway Calculators
       │
       ▼
[Application Services & Intelligence]
       ├─ Alert Rule Evaluator & Alarm Storm Deduplicator
       ├─ Shift Handover PDF & Excel (.xlsx) Exporter
       └─ Industrial AI Copilot (Google Gemini Function-Calling + Offline Engine)
       │
       ▼
[New Frontend Presentation Layer]
       ├─ Executive Management Dashboard
       ├─ Operator Touch Console (Glove-friendly HMI)
       ├─ SMED Stopwatch & Downtime Pareto Visualizer
       ├─ Quality SPC Distribution & Giveaway Simulator
       ├─ Plant Topology SVG Node Hub
       └─ Telemetry Generator Controller (Demo Master)
```

---

## 3. User Personas & Role-Based Access Control (RBAC)

The system defines 6 specialized industrial roles with distinct permissions:

| Role Code | Role Name | Arabic Title | Default Landing | Primary Responsibilities |
|---|---|---|---|---|
| `operator` | **Line Operator** | مشغل ماكينة | `/operator/` | Log scrap/defects, classify downtime causes, record weight samples, request maintenance dispatch. |
| `maintenance` | **Maintenance Technician** | فني صيانة | `/alerts/`, `/stoppages/` | Acknowledge alarms, respond to repair calls, log mechanical/electrical root causes, update work orders. |
| `supervisor` | **Shift Supervisor** | مشرف وردية | `/management/`, `/stoppages/` | Reclassify and split stoppages, advance SMED changeover phases, approve shift handovers, reallocate operators. |
| `quality` | **Quality Specialist** | أخصائي جودة | `/quality/` | Review real-time SPC control charts ($C_p / C_{pk}$), audit weight batches, model giveaway reduction savings. |
| `manager` | **Plant Director** | مدير المصنع | `/dashboard/` | High-level OEE monitoring, financial loss waterfall, cross-plant benchmark, strategic capacity planning. |
| `admin` / `controller` | **System Admin / Demo Master** | مسؤول النظام | `/masterdata/`, `/controller/` | Configure factory topology, machines, SKUs, IoT gateways, run telemetry simulator scenarios. |

### Global Context Bar
Every screen is governed by a persistent Global Context state:
- **Active Factory Selector:** Switch plant facility (e.g., Cairo Bottling vs. Alexandria).
- **Active Line Selector:** Switch active production line (e.g., Line 1, Line 2).
- **Active Shift Selector:** Switch shift window (Morning `07:00–15:00`, Evening `15:00–23:00`, Night `23:00–07:00`).
- **Active SKU Pill:** Current running recipe code, target speed, and nominal product weight.
- **Language Switcher:** Instant bilingual English / Arabic (`en` / `ar`) with full RTL layout adaptation.
- **Theme Switcher:** High-contrast Dark Mode (shop-floor control room) vs. Light Mode (office).

---

## 4. Master Data & Factory Topology

The factory domain is organized hierarchically:

### 4.1 Hierarchy Tree
1. **Factory (Site / Tenant):** Code, Name, Location, Industry vertical (FMCG, Food & Bev, Pharma, Plastics, etc.), Timezone, Currency (`EGP`, `USD`, `EUR`), Working days mask.
2. **Line (Production Line):** Code, Name, Sequence in plant, Target OEE % (default 85.0%), Designated Bottleneck Machine, Current Running SKU.
3. **Machine (Industrial Asset):**
   - Ordered position in line flow (e.g., 10=Blow Molder, 20=Rinser, 30=Filler, 40=Capper, 50=Labeler, 60=Case Packer, 70=Palletizer).
   - Category: `BLOW_MOLDER`, `FILLER`, `CAPPER`, `LABELER`, `PACKER`, `PALLETIZER`, `CONVEYOR`, `SEALER`, `INSPECTION`, `OTHER`.
   - Criticality index (A=Bottleneck/Critical, B=Major, C=Secondary buffer).
   - Ideal Run Rate (Units Per Minute / CPM).
   - Sensor IP, Modbus address, or pulse input pin.
4. **Product (SKU / Recipe):**
   - Code, Name, Barcode, Category, Unit of Measure (`BOTTLE`, `CAN`, `PACK`, `CARTON`, `KG`, `LITER`).
   - Nominal Target Weight ($g$ or $ml$), Upper Specification Limit (USL), Lower Specification Limit (LSL), Unit Cost, Scrap Cost.
5. **MachineProductRate (Speed Matrix):**
   - Specific rated speed (CPM) and cycle time (seconds/unit) for each combination of Machine $\times$ Product.
6. **Shift Lifecycle:**
   - Name (`Morning`, `Evening`, `Night`), Start time, End time, Unpaid break duration (minutes), Planned operating minutes.
7. **Reason Codes & Taxonomies:**
   - **Stoppage Reasons:** Hierarchical (Category $\to$ Reason). Tagged with TPM Loss Category (`AVAILABILITY_BREAKDOWN`, `AVAILABILITY_CHANGEOVER`, `PERFORMANCE_MINOR_STOP`, `PERFORMANCE_SPEED_LOSS`, `QUALITY_DEFECTS`, `QUALITY_STARTUP_SCRAP`), Responsible Department (`MECHANICAL`, `ELECTRICAL`, `OPERATIONS`, `QUALITY`, `SUPPLY_CHAIN`, `SAFETY`, `UTILITIES`).
   - **Defect Reasons:** Code, Name, Category, Default Disposition (`SCRAP`, `REWORK`, `QUARANTINE`).

---

## 5. Telemetry Ingestion & State Machine Engine

### 5.1 Machine State Machine
Every machine transitions across 8 standardized states:
1. `RUNNING`: Producing at or near rated speed.
2. `UNPLANNED_DOWNTIME`: Machine stopped due to fault, jam, or failure ($>\text{threshold}$, e.g. $> 180\text{s}$).
3. `PLANNED_DOWNTIME`: Scheduled maintenance, planned cleaning, team meetings.
4. `CHANGEOVER`: Active SMED tooling or recipe swap between SKUs.
5. `IDLE` / `MICRO_STOP`: Short momentary halt ($< 180\text{s}$), auto-resumes without operator classification.
6. `BLOCKED`: Machine is ready to produce but downstream conveyor or buffer is full.
7. `STARVED`: Machine is ready to produce but upstream supply is empty.
8. `NO_DATA`: Gateway or sensor disconnected (heartbeat timeout).

### 5.2 Real-time Telemetry Pipeline
- **Ingestion Endpoint:** Accepts pulse counts, instantaneous speed (CPM), machine state code, vibration RMS ($mm/s$), temperature ($^\circ C$), active recipe code.
- **Server-Sent Events (SSE):** Real-time stream pushing live status updates, bottle counts, and state changes to client screens at 1 Hz.
- **Auto-Watchdog:** Detects pulse gaps and automatically opens a `DowntimeEvent` if no bottle pulse is seen within a configurable threshold. When pulses resume, it automatically marks the end timestamp and calculates duration.

---

## 6. OEE & Industrial Calculation Engine

The system strictly implements the international **ISO 22400** and **TPM (Total Productive Maintenance)** standards:

### 6.1 Core OEE Metrics
$$\text{OEE} = \text{Availability} \times \text{Performance} \times \text{Quality}$$

1. **Availability ($A$):**
   $$A = \frac{\text{Operating Time}}{\text{Planned Production Time}} = \frac{\text{Planned Time} - (\text{Unplanned Downtime} + \text{Changeover})}{\text{Planned Time} - \text{Planned Breaks}}$$
2. **Performance ($P$):**
   $$P = \frac{\text{Total Units Produced}}{\text{Operating Time} \times \text{Ideal Run Rate (CPM)}}$$
   *(Accounts for micro-stoppages and reduced machine speed).*
3. **Quality ($Q$):**
   $$Q = \frac{\text{Good Units Produced}}{\text{Total Units Produced}} = \frac{\text{Total Produced} - \text{Scrap Defect Units}}{\text{Total Produced}}$$

### 6.2 Bottleneck Cadence
- In any packaging line, throughput is governed by the **Constraint / Bottleneck Machine** (typically the Filler).
- The engine calculates Line OEE based on the bottleneck machine's performance, preventing misleadingly high ratings from non-critical conveyors or buffers.

### 6.3 TPM Six Big Losses Waterfall
Classifies every lost minute or lost unit into one of six standard buckets:
1. **Unplanned Equipment Breakdown:** Mechanical/electrical faults ($A$ loss).
2. **Setup & Adjustments:** SMED changeover and tooling adjustments ($A$ loss).
3. **Idling & Minor Stops:** Frequent jams under 3 minutes ($P$ loss).
4. **Reduced Speed:** Running below nameplate rated CPM ($P$ loss).
5. **Process Defects:** Bottles rejected during production ($Q$ loss).
6. **Reduced Startup Yield:** Scrap produced during line warmup/ramp-up ($Q$ loss).

### 6.4 Financial Downtime Cost
$$\text{Loss Cost} = \text{Downtime Minutes} \times \left(\frac{\text{Bottleneck Ideal CPM} \times 60 \times \text{Unit Profit/Margin}}{60}\right) + \text{Scrap Units} \times \text{Unit Cost}$$

---

## 7. Module-by-Module Feature Specifications

### 7.1 Module 1: Management Overview & Executive OEE Dashboard
- **Route:** `/` or `/dashboard/`
- **Features:**
  1. **Actionable "So What?" Executive Banner:** Real-time summary stating current line status, active bottleneck constraint, and accumulated shift downtime financial cost.
  2. **Line OEE Benchmark Gauges:** Displays Overall OEE, Availability, Performance, and Quality against the World-Class 85.0% target.
  3. **TPM Six Big Losses Waterfall Visualizer:** Bar chart dissecting lost operational minutes across the 6 TPM categories.
  4. **Shift Progress & Production Pacing:** Current count vs. shift target, expected completion projection, and hourly production run chart.
  5. **Live Conveyor Strip:** Linear visual sequence of all machines on the line with color-coded status badges, current speed, and active alerts.
  6. **Quick Dispatch Actions:** Line supervisors can dispatch technicians or reassign unclassified events directly from the dashboard.

---

### 7.2 Module 2: Operator Touch Console (Shop-Floor HMI)
- **Route:** `/operator/?machine=<MACHINE_CODE>`
- **Design Philosophy:** Touchscreen tablet interface (minimum 48px touch targets, high contrast, industrial glove-friendly, zero mouse needed).
- **Features:**
  1. **Machine Carousel / Flow Tabs:** Instant tabbed navigation across line machines (`Blow Molder` $\to$ `Filler` $\to$ `Capper` $\to$ `Labeler` $\to$ `Case Packer`).
  2. **Prominent Equipment State Display:** Large color-coded pulsing banner (`RUNNING` in Green, `UNPLANNED_DOWNTIME` in Red, `BLOCKED` in Amber, `STARVED` in Yellow).
  3. **One-Touch Stoppage Classification Modal:**
     - When machine stops, an intuitive 2-level selector modal opens.
     - Level 1: Category (e.g., Mechanical, Electrical, Raw Material, Operator).
     - Level 2: Specific Root Cause (e.g., Cap Chute Jam, Low Preform Level, Sensor Misalignment).
     - Save classification directly updates supervisor dashboards instantly.
  4. **Stoppage Splitting:** Allows an operator or supervisor to split a 45-minute stop into two separate causes (e.g., 15 min Mechanical Jam + 30 min Waiting for Technician).
  5. **Defect & Scrap Logger:**
     - Select defect type (Underfill, Missing Cap, Damaged Label, Bottle Leak).
     - Large on-screen numeric touch keypad to enter scrap quantity.
  6. **Manual Scale Weight Entry:** Enter weight measurements in grams for live SPC monitoring.
  7. **Maintenance Dispatch Call:** Operator taps "Call Maintenance", generating an urgent alert and maintenance ticket. Can cancel call once technician arrives.
  8. **Product Changeover Trigger:** Operator initiates changeover to a new SKU recipe.

---

### 7.3 Module 3: Stoppages & SMED Changeover Intelligence
- **Route:** `/stoppages/` and `/smed/`
- **Features:**
  1. **Active Stoppage Registry:** Real-time list of ongoing and unclassified downtime events requiring supervisor sign-off.
  2. **Juran 80/20 Downtime Pareto:**
     - Bar chart + cumulative percentage line identifying the "Vital Few" root causes responsible for 80% of lost production time.
     - Toggle between "By Duration (Minutes)" and "By Frequency (Occurrences)".
  3. **Reliability KPIs:**
     - **MTBF (Mean Time Between Failures):** Operating minutes divided by number of breakdowns.
     - **MTTR (Mean Time To Repair):** Average duration to resolve a breakdown.
     - **MTTF (Mean Time To Failure)** and Failure Rate ($\lambda$).
  4. **Digital SMED Changeover Stopwatch:**
     - Implements Shigeo Shingo's Single-Minute Exchange of Die methodology.
     - Sequential 4-phase tracker:
       - **Phase 1: Line Clearance & CIP:** Cleaning in place, purge old SKU materials.
       - **Phase 2: Mechanical Tooling Change:** Swap starwheels, capping chucks, label guides.
       - **Phase 3: Recipe & Parameter Loading:** Digital setpoints (fill volume, torque, temperature).
       - **Phase 4: Test Run & Ramp-Up to Speed:** Reach full rated speed with zero defects.
     - Digital stopwatch records timestamps per phase, benchmarks against target standard time, and highlights phase variance.

---

### 7.4 Module 4: Quality & Weight Giveaway SPC
- **Route:** `/quality/`
- **Features:**
  1. **Statistical Process Control (SPC) Charts:**
     - Compliant with **ISO 22400-2**.
     - **X-bar Chart (Mean):** Sample subgroup averages with Upper Control Limit (UCL), Lower Control Limit (LCL), and Center Line (CL).
     - **R Chart (Range):** Subgroup dispersion tracking fill stability.
  2. **Gaussian Normal Distribution (Bell Curve):**
     - Computes process mean ($\mu$) and standard deviation ($\sigma$).
     - Visualizes distribution against Lower Specification Limit (LSL) and Upper Specification Limit (USL).
  3. **Process Capability Indices:**
     - **$C_p$ (Capability Spread):** $\frac{\text{USL} - \text{LSL}}{6\sigma}$ (Process potential).
     - **$C_{pk}$ (Centering Index):** $\min\left(\frac{\text{USL} - \mu}{3\sigma}, \frac{\mu - \text{LSL}}{3\sigma}\right)$ (Actual process capability).
     - Real-time rating (e.g. $C_{pk} \ge 1.33$ = Capable, $< 1.0$ = Critical Action Required).
  4. **Overfill Giveaway Financial Calculator:**
     - Overfilling bottles by even $+0.8\text{ g}$ causes significant financial loss.
     - Calculates total product giveaway in kilograms and monetary value (`EGP`/`USD`).
     - **Interactive Recalibration Slider:** Allows quality engineers to simulate shifting the fill mean closer to nominal, calculating annual raw material savings while proving zero legal underfill risk.
  5. **Data Export:** Export all raw weight sample measurements to CSV/Excel.

---

### 7.5 Module 5: Real-Time Alerts & Alarm Storm Engine
- **Route:** `/alerts/`
- **Features:**
  1. **Configurable Alert Rules:**
     - Rule Scopes: Global, Line-specific, or Machine-specific.
     - Rule Types:
       - Continuous Downtime Duration exceeded (e.g., stops $> 15$ min).
       - Low Speed / Speed Loss below threshold (e.g., speed $< 80\%$ rated for 5 min).
       - Defect Rate Spike (e.g., scrap $> 3\%$ over 100 units).
       - Weight Out-of-Spec (consecutive weight points beyond UCL/LCL).
       - Vibration RMS or Temperature overheating.
  2. **Alarm Storm Deduplication & Suppression Window:**
     - Prevents alerting fatigue during major line trips.
     - Cooldown period prevents repeating identical alerts within $N$ minutes.
  3. **Auto-Resolve Watchdog:**
     - Automatically resolves active alerts when machine telemetry returns to normal parameters (`RUNNING`).
  4. **Alert Lifecycle:**
     - State flow: `ACTIVE` $\to$ `ACKNOWLEDGED` (by technician/supervisor) $\to$ `RESOLVED`.
     - Direct button to spawn a formal `MaintenanceTicket` from an alert.
  5. **Notification Drawer:** Real-time slide-out drawer accessible from any page with unread badge counter.

---

### 7.6 Module 6: Industrial AI Copilot (Dual-Engine)
- **Route:** `/copilot/`
- **Architecture:** Hybrid Cloud + Edge Dual Engine:
  1. **Cloud Engine (Google Gemini Flash):** Connected via Google AI Studio API. Uses Function Calling tools to query live database metrics (OEE, current speeds, active downtime events, top pareto causes, giveaway losses).
  2. **Deterministic Offline Engine (Edge Fallback):** 100% Python offline engine requiring zero internet. Executes mathematical queries and pre-built operational heuristics locally.
- **Features:**
  1. **Bilingual Querying (English & Arabic):** Full natural language understanding in both languages.
  2. **Context-Aware Factory Queries:**
     - *"Why is OEE low on Line 1 today?"* $\to$ Analyzes breakdown vs speed loss vs scrap.
     - *"ما هي الماكينة التي تمثل عنق الزجاجة الآن؟"* $\to$ Identifies active constraint machine.
     - *"Draft shift handover notes for the incoming supervisor."* $\to$ Generates 4-bullet executive synthesis.
     - *"How much did overfill giveaway cost us this morning?"* $\to$ Pulls exact financial sum.
  3. **Interactive Action Chips:** AI responses include clickable shortcuts (e.g., `[View Filler HMI]`, `[Review Pareto Chart]`, `[Check SPC]`).

---

### 7.7 Module 7: Shift Handover & Production Reporting
- **Route:** `/reports/`
- **Features:**
  1. **Official Shift Handover Document:**
     - Standardized operational report ready for end-of-shift handover meetings.
     - Contains: 4-bullet executive summary, Line OEE breakdown (A/P/Q), Production count vs. target, Top 5 downtime events, Scrap defect breakdown, Operator attendance.
  2. **Export to PDF:** High-resolution formatted PDF ready for print or email.
  3. **Export to Excel (.xlsx):** Multi-tab structured workbook with raw hourly metrics, downtime logs, and defect logs for pivot tables and data science.
  4. **Automated Report Subscriptions:**
     - Configure automated report generation (Frequency: Daily, End-of-Shift, Weekly).
     - Recipient email distribution lists.

---

### 7.8 Module 8: Master Data Management & Onboarding Wizard
- **Route:** `/masterdata/` and `/masterdata/wizard/`
- **Features:**
  1. **60-Second Onboarding Wizard:**
     - Deploy a complete packaging line from scratch using 1-Click Industry Presets:
       - **Bottled Water (High Speed):** 6 Machines, 120 CPM Bottleneck (Blow Molder $\to$ Filler $\to$ Capper $\to$ Labeler $\to$ Case Packer $\to$ Palletizer).
       - **Carbonated Soft Drinks (CSD):** Rinser $\to$ Isobaric Filler $\to$ Crown Capper $\to$ Tunnel Pasteurizer $\to$ Labeler.
       - **Edible Oil & Condiments:** Piston Filler $\to$ Nitrogen Doser $\to$ Induction Sealer $\to$ Wrap Labeler.
  2. **Interactive Factory Topology Hub (`/masterdata/topology/`):**
     - Visual SVG node graph representing physical machine sequence on the line.
     - Real-time animated bottle flow dots and machine status color codes.
     - Tap any machine node to open a slide-out telemetry drawer showing vibration RMS, motor temperatures, and current speeds.
  3. **IoT Gateway QR Code Onboarding:**
     - System generates unique claim QR codes for hardware gateways (Raspberry Pi, ESP32, Moxa).
     - Field technician scans QR code with mobile camera to bind gateway directly to a machine.
  4. **Production Planning & Work Orders:**
     - Create and schedule production plans, assign target quantities, and track completion progress. Printable production work orders.
  5. **Built-in Industrial KPI Glossary & User Guide:**
     - Comprehensive definitions of OEE, MTBF, MTTR, SMED, $C_p$, $C_{pk}$, Six Big Losses.

---

### 7.9 Module 9: Signal Simulator & Demo Controller
- **Route:** `/controller/`
- **Target Users:** Sales demonstrators, training instructors, QA test engineers.
- **Features:**
  1. **Synthetic Telemetry Generator:**
     - Generates realistic pulses, speeds, and micro-stops when real factory PLCs are not connected.
  2. **Clock Speed Multiplier:** Run simulation in real-time ($1.0\times$), accelerated ($2.0\times$, $5.0\times$, $10.0\times$), or paused.
  3. **Scenario Injector Library:**
     - *Scenario 1: Cap Chute Jam* $\to$ Faults Capper, creates bottle backup to Filler.
     - *Scenario 2: Overfill Giveaway Drift* $\to$ Causes Filler scale weights to drift upwards by $+1.2\text{ g}$.
     - *Scenario 3: Mechanical Breakdown* $\to$ Stops Blow Molder, starves downstream line.
     - *Scenario 4: Defect Burst* $\to$ Injects spike of 25 label scrap defects.
     - *Scenario 5: Golden Run* $\to$ Restores all machines to perfect rated speed (95% OEE).
  4. **Manual Machine Override:** Force any machine's state, speed, vibration, and temperature with sliders.
  5. **Shift Transition & Reset Trigger:** Manually trigger shift end, test handover report generation, and reset counters.
  6. **"DEMO MODE ACTIVE" Persistent Badge:** Clear visual ribbon ensuring operators never confuse simulated data with real plant telemetry.

---

## 8. Comprehensive REST & Streaming API Directory

| Method | Endpoint Route | Request Payload / Params | Response Summary | Purpose |
|---|---|---|---|---|
| **POST** | `/api/v1/telemetry/ingest/` | `{"machine_code", "pulse_count", "instant_cpm", "state_code", "vibration", "temperature"}` | `{"status": "ok", "machine_state"}` | Ingest edge gateway sensor pulses |
| **GET** | `/api/v1/telemetry/live/<line_code>/` | None | JSON summary of line machines & metrics | Polling fallback for live status |
| **GET** | `/api/v1/telemetry/stream/<line_code>/` | None | `text/event-stream` (SSE) | Real-time 1Hz live telemetry stream |
| **GET** | `/api/v1/calculation/line/<line_code>/kpi/` | `?shift_id=&product_id=` | `{"oee", "availability", "performance", "quality", "bottleneck"}` | Live OEE and bottleneck calculation |
| **GET** | `/api/v1/calculation/line/<line_code>/hourly/` | `?date=` | Array of hourly production & OEE records | Hourly run chart trend data |
| **GET** | `/api/v1/calculation/line/<line_code>/waterfall/`| None | Breakdown of minutes lost across 6 Big Losses | Six Big Losses waterfall chart data |
| **POST** | `/operator/stoppage/<id>/classify/` | `{"category_id", "reason_id", "notes"}` | `{"status": "classified"}` | Classify downtime from touch console |
| **POST** | `/operator/stoppage/<id>/split/` | `{"splits": [{"duration_minutes", "reason_id"}]}` | `{"status": "split"}` | Split single downtime event into multiple |
| **POST** | `/operator/defect/<machine_code>/` | `{"reason_id", "scrap_count", "disposition"}` | `{"status": "logged", "total_scrap"}` | Log scrap rejects via HMI numpad |
| **POST** | `/operator/weight/<machine_code>/` | `{"weight_grams", "sku_id"}` | `{"status": "logged", "is_in_spec"}` | Log checkweigher manual scale sample |
| **POST** | `/operator/maintenance/<code>/request/`| `{"priority", "description"}` | `{"ticket_id", "status"}` | Request urgent maintenance dispatch |
| **POST** | `/operator/maintenance/<code>/cancel/` | None | `{"status": "cancelled"}` | Cancel maintenance call |
| **GET** | `/api/v1/stoppages/pareto/` | `?line_code=&metric=duration|frequency` | Array of reasons sorted with cumulative % | Juran 80/20 downtime Pareto curve |
| **GET** | `/api/v1/stoppages/reliability/` | `?line_code=` | `{"mtbf_min", "mttr_min", "mttf_min", "avail_pct"}` | MTBF & MTTR reliability statistics |
| **POST** | `/api/v1/stoppages/<id>/reclassify/` | `{"new_reason_id", "supervisor_notes"}` | `{"status": "updated"}` | Supervisor audit reclassification |
| **POST** | `/api/v1/smed/start/` | `{"line_code", "from_sku", "to_sku"}` | `{"changeover_id", "phase": 1}` | Start SMED changeover event |
| **POST** | `/api/v1/smed/<id>/advance/` | None | `{"changeover_id", "new_phase"}` | Advance SMED stopwatch to next phase |
| **POST** | `/api/v1/smed/<id>/rampup/` | `{"bottles_produced", "scrap_bottles"}` | `{"status": "rampup_recorded"}` | Log test run bottles during SMED ramp-up |
| **GET** | `/quality/api/<sku_code>/` | `?limit=50` | `{"mean", "std_dev", "cp", "cpk", "samples", "giveaway_cost"}` | SPC control chart data and capability |
| **POST** | `/api/v1/quality/weight-sample/` | `{"sku_code", "weight_value", "machine_code"}`| `{"sample_id", "deviation"}` | Programmatic quality weight ingestion |
| **GET** | `/quality/giveaway/export/` | `?sku_code=` | CSV File Download | Raw weight samples export |
| **GET** | `/alerts/api/live/` | `?line_code=` | Array of active unresolved alert events | Real-time active alerts badge & drawer |
| **POST** | `/alerts/event/<id>/acknowledge/` | None | `{"status": "acknowledged"}` | Acknowledge alarm event |
| **POST** | `/alerts/event/<id>/resolve/` | `{"resolution_notes"}` | `{"status": "resolved"}` | Manually resolve alarm |
| **POST** | `/copilot/api/chat/` | `{"query", "language", "history"}` | `{"answer", "action_chips", "engine_used"}` | AI Copilot bilingual conversation |
| **GET** | `/copilot/api/quick-summary/` | `?line_code=` | `{"summary_text", "status_level"}` | 1-Sentence AI executive status check |
| **GET** | `/reports/export/pdf/` | `?shift_id=&line_code=` | PDF File Download | End-of-shift handover PDF document |
| **GET** | `/reports/export/excel/` | `?shift_id=&line_code=` | XLSX File Download | Shift audit metrics Excel workbook |
| **POST** | `/api/v1/controller/scenario/apply/` | `{"scenario_key": "cap_jam|overfill|..."}` | `{"status": "applied"}` | Inject test scenario in simulator |
| **POST** | `/api/v1/controller/machine/override/` | `{"machine_code", "state", "speed", "temp"}` | `{"status": "overridden"}` | Manual telemetry override |
| **POST** | `/api/v1/controller/multiplier/` | `{"multiplier": 1.0|2.0|5.0|10.0}` | `{"active_multiplier"}` | Adjust simulation clock speed |
| **POST** | `/api/v1/controller/shift/transition/` | None | `{"new_shift_name", "status"}` | Trigger shift rotation in simulator |

---

## 9. Data Models & Schema Reference

### 9.1 Core Entities & Fields
- **`Factory`**: `id` (UUID), `code`, `name`, `name_ar`, `location`, `industry`, `timezone`, `currency`, `working_days_mask`, `is_active`.
- **`Line`**: `id` (UUID), `factory` (FK), `code`, `name`, `name_ar`, `sequence`, `target_oee`, `bottleneck_machine` (FK), `current_product` (FK).
- **`Machine`**: `id` (UUID), `line` (FK), `code`, `name`, `name_ar`, `category`, `sequence_order`, `criticality_rank` (A/B/C), `ideal_run_rate_cpm`, `is_bottleneck`, `sensor_protocol`.
- **`Product` (SKU)**: `id` (UUID), `factory` (FK), `code`, `name`, `barcode`, `category`, `unit_of_measure`, `nominal_weight`, `usl_weight`, `lsl_weight`, `unit_cost`, `scrap_cost`.
- **`MachineProductRate`**: `machine` (FK), `product` (FK), `rated_speed_cpm`, `ideal_cycle_time_sec`.
- **`Shift`**: `id` (UUID), `factory` (FK), `code`, `name`, `name_ar`, `start_time`, `end_time`, `unpaid_break_minutes`, `sequence`.
- **`MachineCurrentState`**: `machine` (1-to-1), `state_code`, `current_speed_cpm`, `active_product` (FK), `vibration_rms`, `temperature_c`, `shift_pulse_count`, `shift_scrap_count`, `last_state_change`.
- **`StoppageEvent`**: `id` (UUID), `machine` (FK), `line` (FK), `shift` (FK), `start_time`, `end_time`, `duration_seconds`, `status` (`ACTIVE`, `CLASSIFIED`, `SPLIT`), `category` (FK), `reason` (FK), `tpm_loss_type`, `department`, `is_planned`, `classified_by` (FK), `notes`.
- **`ChangeoverEvent` (SMED)**: `id` (UUID), `line` (FK), `from_product` (FK), `to_product` (FK), `current_phase` (1-4), `status` (`IN_PROGRESS`, `COMPLETED`), `phase1_duration`, `phase2_duration`, `phase3_duration`, `phase4_duration`, `total_duration_sec`, `rampup_bottles`, `rampup_scrap`.
- **`DefectLog`**: `id` (UUID), `machine` (FK), `line` (FK), `shift` (FK), `product` (FK), `reason` (FK), `quantity`, `disposition` (`SCRAP`, `REWORK`), `timestamp`.
- **`WeightSample`**: `id` (UUID), `machine` (FK), `product` (FK), `shift` (FK), `measured_weight_grams`, `nominal_target_grams`, `deviation_grams`, `is_within_spec`, `timestamp`.
- **`AlertRule`**: `id` (UUID), `scope` (`GLOBAL`, `LINE`, `MACHINE`), `rule_type`, `threshold_value`, `duration_seconds`, `cooldown_minutes`, `severity` (`INFO`, `WARNING`, `CRITICAL`), `is_active`.
- **`AlertEvent`**: `id` (UUID), `rule` (FK), `machine` (FK), `line` (FK), `severity`, `title`, `message`, `status` (`ACTIVE`, `ACKNOWLEDGED`, `RESOLVED`), `triggered_at`, `resolved_at`, `auto_resolved`.
- **`MaintenanceTicket`**: `id` (UUID), `machine` (FK), `priority` (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), `status` (`OPEN`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`), `description`, `reported_by`, `assigned_to`, `created_at`.
- **`ReportSubscription`**: `report_type` (`SHIFT_HANDOVER`, `DAILY_OEE`, `QUALITY_SPC`), `format` (`PDF`, `EXCEL`), `frequency`, `recipient_emails`.

---

## 10. Key Frontend & UX Guidelines for the New UI

When designing and implementing the new UI for this platform:

1. **Touch Ergonomics for HMI Screens (`/operator`):**
   - Design for 10"–15" rugged industrial tablets.
   - All interactive touch targets must be at least **48px $\times$ 48px** (preferably 56px+).
   - Use high-contrast color badges (`#34A853` Green for Running, `#EA4335` Red for Faulted, `#FBBC04` Amber for Blocked/Starved).
   - Incorporate an on-screen custom numeric keypad for scrap and weight inputs (avoid relying on OS virtual keyboards).

2. **Tabular Typography for Telemetry:**
   - Always render speeds, OEE percentages, and bottle counters using monospace tabular numbers (`font-variant-numeric: tabular-nums` or fonts like `Roboto Mono`, `JetBrains Mono`). This prevents jittering during real-time 1 Hz updates.

3. **Responsive Multi-Form Factor Layout:**
   - **Control Room Video Walls (1080p / 4K):** Dense multi-line overview with live conveyor status and alerts ticker.
   - **Supervisor Desktop / Laptop:** In-depth Pareto analytics, SPC distribution curves, and PDF/Excel generation.
   - **Floor Operator Tablet:** Simplified, distraction-free machine console.
   - **Manager Mobile View:** High-level OEE gauge cards and shift pacing summaries.

4. **Bi-Directional Support (English & Arabic):**
   - Provide clean LTR (English) and RTL (Arabic) stylesheets.
   - In RTL mode, conveyor flow directions and sequence numbering reverse naturally to maintain intuitive physical alignment.

5. **Real-time Live Feel:**
   - Connect frontend telemetry components via Server-Sent Events (SSE) or WebSockets.
   - Provide subtle micro-animations (e.g. subtle green pulse dot on running machines, glowing red border on unclassified stops) to make the plant floor feel alive.


---

# Appendix B — Complete UI and role source

The following source is preserved verbatim. Its historical diagnoses and approval status are not verified findings for the new app. Sections 1–12 control conflicts.

# Factory MES & OEE Platform (Siri / FactorySense)
# UI/UX Architecture, Information Structure & Role Organization Specification

---

## 1. Executive Summary & Problem Diagnosis

### 1.1 System Identity & Scope
The platform is an industrial **Manufacturing Execution System (MES)** and **Overall Equipment Effectiveness (OEE)** tracking system designed for factory floor operations. It unifies machine monitoring, production tracking, operator logging, scrap/defect counting, maintenance ticketing, document approvals (drawings & SOPs), supply chain work orders, and master setup data.

### 1.2 Current Architecture Flaws & Pain Points
An audit of the codebase reveals critical UI and organizational issues that hinder factory adoption:

1. **Fragmented UI & App Silos:**
   - Every Django app (`operatorsystem`, `shiftleader`, `maintenance`, `approvals`, `setuppage`, `supplychain`) has its own independent `base.html` template.
   - There is no unified navigation bar, no consistent header, no shared color palette, and no cohesive design system.
   - Switching between views feels like navigating separate disconnected applications.

2. **Rigid & Brittle Role Redirection:**
   - In `accounts/views.py` and `system/urls.py`, role routing is handled via a cascade of `if user.groups.filter(...).exists(): elif ...` branches.
   - If a user belongs to multiple groups (e.g., a **Shift Leader** who is also a **Maintenance Technician**, or a **Plant Manager** requiring visibility across all modules), the system blindly redirects to the first matching branch, locking them out of other areas.
   - Operators are tightly coupled to a single machine identifier (`mac_address`) which fails gracelessly if headers or parameters are lost.

3. **Poor Ergonomics for Factory Floor (Operator Dashboard):**
   - The operator interface runs on factory tablets and touch kiosks. The existing design uses standard desktop web layouts, tiny form controls, and intrusive alert popups rather than high-contrast, glove-friendly touch ergonomics.
   - High-stress actions (reporting sudden breakdown, logging scrap, changing processes) require too many clicks and lack instant visual confirmation.

4. **Cluttered Information Architecture (IA):**
   - In `setuppage`, settings for machines, shifts, stoppage reasons, products, processes, alert emails, and CSV exports are laid out in a flat navbar with no logical groupings.
   - Work orders are split inconsistently between `setuppage/work-orders/` and `supplychain/workorders/`.
   - Real-time plant floor status is scattered across multiple pages instead of being anchored by a centralized **Executive Live Command Center**.

---

## 2. Unified Design System & UI Foundations

### 2.1 Industrial Design Tokens & Ergonomics
The UI must support two contrasting physical environments:
- **Shop Floor Kiosks / Tablets:** Ruggedized, high-contrast, touch-optimized (minimum touch target 48x48px, primary buttons 64px+ height), readable from 2 meters away under ambient factory lighting.
- **Office / Management Desktops:** Dense, data-rich analytical views with sortable tables, multi-metric KPI cards, interactive charts, and quick search filters.

#### Semantic Status Color Palette (ISO 22400 / Industrial Standards)
| Status | Meaning | Hex Token | Tailwind Equivalent | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Running / Normal** | Machine running, target speed met | `#10B981` | `emerald-500` | Machine card border, live badge, running timer |
| **Unplanned Downtime** | Breakdown, emergency stop, fault | `#EF4444` | `rose-500` | Breakdown alert, blocking takeover modal |
| **Planned Stoppage** | Setup, changeover, scheduled break | `#F59E0B` | `amber-500` | Setup badge, planned downtime progress |
| **Maintenance Active** | Technician clocked-in, under repair | `#8B5CF6` | `purple-600` | Maintenance ticket in-progress, technician badge |
| **Waiting Spare Parts** | Blocked awaiting components | `#EC4899` | `pink-500` | Ticket paused indicator |
| **Idle / Standby** | Machine powered on but not cycling | `#6B7280` | `slate-500` | Machine idle badge |
| **Quality Alert** | Scrap rate exceeding tolerance | `#F97316` | `orange-500` | Defect counter warning, quality hold |

#### Typography & Localization (Arabic & English)
- **Primary Fonts:** `Inter`, `Cairo`, or `IBM Plex Sans Arabic` for crisp readability in both Latin and Arabic scripts.
- **Directional Support:** Native bidirectional support (`dir="ltr"` and `dir="rtl"`). All sidebars, tables, and badge alignments adapt seamlessly based on the active language (`en` or `ar`).
- **Data Display Numbers:** High-visibility monospaced tabular numerals (`font-mono`) for cycle times, piece counters, and countdown clocks to eliminate visual jitter.

---

## 3. Global Information Architecture & Master Shell

### 3.1 Unified App Shell Layout
Instead of separate base templates, the entire system must render within a single, cohesive **Master Application Shell**:

```
+----------------------------------------------------------------------------------------------------+
| TOPBAR: [Logo: Siri MES] | Factory: Plant 1 | Live Shift: Shift A (06:00-14:00) | [Search / CMD]   |
| [Global Alerts: 2 Down] [Language: EN/AR] [Role Switcher: Shift Leader v] [User Profile / Logout] |
+------------------------------------+---------------------------------------------------------------+
| SIDEBAR (Collapsible / Role-aware) | MAIN CONTENT AREA                                             |
|                                    |                                                               |
| [x] Live Floor Monitor             | [Breadcrumbs: Home > Floor Overview > Line 1]                 |
| [ ] Operator Kiosk Mode            |                                                               |
| [ ] Shift Management               | +-----------------------------------------------------------+ |
| [ ] Maintenance Hub (3 Open)       | | KPI Summary Cards (Availability | Performance | Quality)  | |
| [ ] Work Orders & Supply Chain     | +-----------------------------------------------------------+ |
| [ ] Engineering & Approvals (1)    | |                                                           | |
| [ ] Reports & Analytics            | | [Active View / Tab Content / Interactive Grid / Form]      | |
| [ ] Master Settings (Admin)        | |                                                           | |
|                                    | +-----------------------------------------------------------+ |
+------------------------------------+---------------------------------------------------------------+
| FOOTER: System Status: Healthy | Redis/Celery: Active | Sentry: Connected | v2.4.0                 |
+----------------------------------------------------------------------------------------------------+
```

### 3.2 Top Bar Global Utilities
1. **Plant & Shift Context Indicator:** Displays current active shift, elapsed time, and plant area.
2. **Global Plant Alarm Ribbon:** Pulses red when any critical machine is experiencing unplanned stoppage or a force-logout breakdown.
3. **Role Switcher Dropdown:** Enables users with multiple role assignments (e.g., Shift Leader + Maintenance) to toggle view personas without logging out.
4. **Bilingual Toggle (EN / AR):** Instant language switch without resetting form state or session filters.
5. **Universal Quick Action Button (+):** Allows authorized users to immediately "Log Breakdown Ticket", "Add Shift Scrap", or "Issue Work Order" from anywhere.

---

## 4. Module-by-Module UI Wireframes & Structural Specifications

### 4.1 Module 1: Operator Kiosk Dashboard (`operatorsystem`)
*Target Device: 10"–15" Industrial Touchscreen mounted directly on each machine.*

#### Key Structural Elements:
1. **Header Banner (Touch-friendly 70px):**
   - Machine Name (`Machine #04 - Injection Mold A`) + Operator Badge Name (`Ahmed Hassan`).
   - Current Product & Active Work Order (`WO-2026-0891 - Flange 40mm`).
   - Active Process Badge (`Process: Molding Step 2`).
   - Giant Shift Timer (Runtime vs Downtime).

2. **Main KPI & Production Counters (Center 50% of viewport):**
   - **Good Pieces Produced:** Massive green digital counter with rapid `+1`, `+5`, `+10` quick-tap buttons.
   - **Defect / Scrap Counter:** Prominent orange counter with single-tap trigger opening a quick-defect categorization modal (Burr, Crack, Dimension, Color).
   - **Real-Time OEE Radial Gauge:** Visual dial displaying current shift efficiency.

3. **Action Bar & Machine State Controls (Bottom 25% of viewport):**
   - `[Report Breakdown / Stop]` (Red, high-priority): Immediately pauses runtime, starts downtime timer, and creates a maintenance ticket.
   - `[Changeover / Setup]` (Yellow): Switches state to "Planned Setup" with stopwatch.
   - `[Switch Process / Work Order]` (Blue): Prompts quick selector for authorized next routing steps.
   - `[View SOP & Drawing]` (Slate): Slides out a full-screen drawer displaying the latest approved PDF drawing/SOP with pinch-to-zoom.

4. **Blocking Modal Overlays (Controlled Intervention):**
   - **Maintenance Forced Lockout:** If a ticket is flagged `force_logout=True`, the entire screen locks with a high-visibility warning: *"Machine Stopped by Maintenance Ticket #142 (Motor Overheat). Operator locked until technician clears issue."*
   - **Setup In-Progress:** Soft-blocks piece input until the operator or shift leader taps "Complete Setup & Begin Production".

---

### 4.2 Module 2: Shift Leader Live Floor Hub (`shiftleader`)
*Target Device: Shop Floor Supervisor Tablet or Office Dual-Monitor Setup.*

#### Key Structural Elements:
1. **Floor Matrix / Grid View:**
   - Visual grid of all factory machines (e.g., 20 machines organized by line or cell).
   - Each machine card provides an instant glanceable state:
     - Border color: Emerald (Running), Rose (Breakdown), Amber (Setup), Violet (In Maintenance).
     - Running operator photo/name.
     - Active Work Order & progress bar (`740 / 1000 pcs (74%)`).
     - Current runtime vs downtime breakdown bar.
2. **Active Shift Summary Strip:**
   - Total factory output for current shift vs planned quota.
   - Aggregate factory OEE (Availability, Performance, Quality).
   - Count of open maintenance tickets and total downtime minutes.
3. **Shift Handoff & End-of-Shift Wizard:**
   - Guided 3-step checklist to review unclosed tickets, verify total piece counts against physical bins, log handoff remarks, and sign off shift closure.

---

### 4.3 Module 3: Maintenance Operations Center (`maintenance`)
*Target Device: Maintenance Lead Desktop & Mobile Phone for On-Call Technicians.*

#### Key Structural Elements:
1. **Kanban Incident Board:**
   - Columns: **Open / Unassigned** -> **In Progress / Technician Dispatched** -> **Waiting for Spare Parts** -> **Testing & Verification** -> **Resolved / Closed**.
   - Cards display Machine ID, reason category (Mechanical, Electrical, Pneumatic, Tooling), elapsed downtime timer (ticking red if >30 minutes), and assigned technician.
2. **Technician Action Sheet (Mobile-optimized):**
   - Direct button to `[Clock In / Start Repair]` (records `maintenance_start` timestamp).
   - `[Request Spare Part]` button (pauses SLA timer and marks ticket as "Waiting Spare").
   - `[Record Solution & Root Cause]` form (mandatory before ticket closure to prevent recurring downtime).
   - `[Release Machine to Production]` button (notifies operator kiosk and unlocks machine).

---

### 4.4 Module 4: Engineering & Quality Document Approvals (`approvals`)
*Target Device: Engineering Workstation & Tablet for Quality Sign-off.*

#### Key Structural Elements:
1. **Document Lifecycle Pipeline:**
   - Tabs: `Draft Designs` -> `Pending Review` -> `Approved for Production` -> `Archived / Deprecated`.
2. **Version Control & Revision Diff Viewer:**
   - Side-by-side or overlay comparison of technical drawings (Rev A vs Rev B).
   - Change log summary (e.g., "Wall thickness increased from 2.5mm to 3.0mm per QC inspection").
3. **Sequential Multi-Group Approval Flow:**
   - Visual step tracker showing who has approved (e.g., Step 1: Design Lead [Approved] -> Step 2: Quality Manager [Pending] -> Step 3: Production Head [Waiting]).
   - One-click "Approve with Digital Signature" or "Reject with Required Modification Feedback".

---

### 4.5 Module 5: Planning, Supply Chain & Work Orders (`supplychain` & `setuppage`)
*Target Device: Desktop Browser for ERP Planners & Supply Chain Specialists.*

#### Key Structural Elements:
1. **Work Order Central Dispatch:**
   - Consolidates work orders from Odoo / ERP sync into a single view.
   - Status tracking: Scheduled, In Production, Completed, Short-Closed.
   - Machine assignment matrix: Visual calendar showing which work orders are assigned to which machines across Shift 1, Shift 2, and Shift 3.
2. **Process Routing & Bill of Operations:**
   - Displays multi-step processes for each product (e.g., Cutting -> Bending -> Welding -> Powder Coating -> Assembly).
   - Progress bar showing piece completion at each sequential process stage.

---

### 4.6 Module 6: Master Setup & System Administration (`setuppage`)
*Target Device: System Administrator Desktop.*

#### Restructured Information Architecture (Grouped into logical tabs):
1. **Plant & Asset Master:**
   - Machines setup (Identifier, MAC Address, Line, IP, Tablet pairing).
   - Maintenance reasons taxonomy (Hierarchical breakdown: Electrical, Mechanical, Setup, Quality).
2. **Production Master:**
   - Products & SKUs.
   - Process catalog & Ideal Cycle Times (standard performance benchmarks).
3. **Shift Schedules & Calendars:**
   - Shift definitions (Start time, end time, grace periods, planned breaks).
   - One-click "Copy shifts configuration to all machines".
4. **Alerts & Automation Center:**
   - Email alert trigger rules (e.g., if downtime > 20 mins -> email Production Head; if scrap > 5% -> email Quality Lead).
   - Telegram Bot configuration & recipient channels.
   - Scheduled report distributions (Daily Shift Summary PDF / Excel).
5. **Historical Data & Analytics Center:**
   - Filterable data explorer (by date range, machine, operator, work order).
   - One-click export to CSV / Excel for Production, Maintenance, and Scrap records.

---

## 5. Comprehensive User & Role-Based Access Control (RBAC)

### 5.1 System Personas & Responsibilities

| Role / Persona | Group Name | Primary Objective | Physical Environment |
| :--- | :--- | :--- | :--- |
| **Machine Operator** | `operators` | High-speed production entry, scrap logging, stopping machine during issues | Machine Kiosk (Touchscreen) |
| **Shift Leader / Supervisor** | `shift-leaders` | Floor supervision, machine status oversight, ticket escalation, shift handover | Mobile Tablet / Floor Pod |
| **Maintenance Technician** | `maintenance` | Immediate troubleshooting, spare parts requisition, repair logging | Mobile Phone / Workshop PC |
| **Design / Quality Engineer** | `designers` | Creating/updating technical drawings, SOPs, inspecting scrap, document review | Office Workstation / CAD PC |
| **Production Planner** | `planners` | Master data config, shift definition, SKU setup, cycle times | Office Desktop |
| **Supply Chain Officer** | `supply_chain` | Work order scheduling, ERP/Odoo sync, material delivery tracking | Office Desktop |
| **Plant Director / Executive** | `management` | High-level OEE trends, MTTR/MTBF analysis, plant downtime costs | Executive Dashboard / Tablet |
| **System Administrator** | `admin` | User provisioning, role assignments, system logs, backups, Sentry errors | Desktop Browser |

---

### 5.2 Granular Permissions Matrix

| Module / Action | Operator | Shift Leader | Maintenance | Designer / QC | Planner | Supply Chain | Plant Manager | Admin |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Operator Kiosk Dashboard** | Full | View Only | View Only | No | No | No | View Only | Full |
| **Log Pieces & Defects** | Yes | Yes (Override) | No | No | No | No | No | Yes |
| **Trigger Breakdown / Stoppage** | Yes | Yes | Yes | No | No | No | No | Yes |
| **Floor Monitor (All Machines)** | No | Full | View | View | View | View | Full | Full |
| **Open Machine Ticket** | Yes | Yes | Yes | Yes | No | No | No | Yes |
| **Close Maintenance Ticket** | No | Approve | Execute/Close | No | No | No | No | Yes |
| **Mark Waiting for Spare Parts** | No | No | Yes | No | No | No | No | Yes |
| **Create / Revise Drawing/SOP** | No | No | No | Full | No | No | No | Full |
| **Approve Document Version** | No | Consult | No | Yes (Quality) | No | No | Full | Full |
| **Manage Work Orders** | View Active | View | No | No | Edit | Full | View | Full |
| **Setup Products & Cycle Times** | No | No | No | No | Full | No | View | Full |
| **Setup Shifts & Calendars** | No | View | No | No | Full | No | View | Full |
| **Manage Stoppage Reasons** | No | No | Propose | No | Full | No | View | Full |
| **Configure Email / Alerts** | No | No | No | No | Full | No | View | Full |
| **Export Historical Data (CSV)** | No | Shift Only | Maintenance | QC Only | Full | Full | Full | Full |
| **System Audit Logs & Settings** | No | No | No | No | No | No | View | Full |

---

### 5.3 Multi-Role Navigation & Session Security

#### 1. Multi-Role Switcher Architecture
In factory operations, a single individual often holds overlapping responsibilities. For example, a senior technician may act as **Maintenance Technician** and **Shift Leader**.
- Instead of relying on rigid `if-elif` redirects:
  - When a user logs in, the backend computes all groups the user belongs to.
  - If the user has more than 1 group, the top navigation renders a **Role Persona Switcher** dropdown.
  - Selecting a persona updates `request.session['active_role']`, switching navigation items, widgets, and default home screens dynamically without re-authentication.

#### 2. Operator Machine Kiosk Locking & Hardware Security
- **One-Operator-Per-Machine Guarantee:**
  - An operator profile can only hold **one active session at any time**. Logging into Machine B automatically terminates or prompts confirmation for their session on Machine A.
- **Machine Hardware Binding:**
  - Machines are identified by hardware identifier / MAC address stored in `MachineSetup`.
  - If an operator tries to access the kiosk from an unapproved device, the system prompts for Supervisor Override PIN.
- **Maintenance Override Lock:**
  - When a ticket with `reason__force_logout=True` is activated, all active operator sessions on that machine are instantly terminated.
  - The login screen for that specific machine displays a red banner: *"Machine under active repair by Technician [Name]. Login disabled."*

---

## 6. Component Architecture & Frontend Implementation Roadmap

### 6.1 Unified Master Template Structure
Refactor the fragmented Django templates into a modular, clean hierarchy:

```
templates/
├── base_app.html                 <-- Master shell (Sidebar, Topbar, RTL/LTR engine, Tailwind, Font, Toasts)
├── components/
│   ├── topbar.html               <-- Header, shift timer, plant alerts, role switcher, language select
│   ├── sidebar.html              <-- Dynamic navigation menu based on user groups and active role
│   ├── kpi_card.html             <-- Standardized KPI widget (Value, Target, Trend, Sparkline)
│   ├── status_badge.html         <-- Standardized status badge (Running, Stopped, Maintenance, Idle)
│   ├── touch_counter.html        <-- High-contrast touch keypad component for kiosk
│   ├── modal_breakdown.html      <-- Rapid stoppage reporting dialog
│   └── toast_notifications.html  <-- Floating alert notifications for Telegram/Email triggers
├── layouts/
│   ├── kiosk_layout.html         <-- Minimalist, no-sidebar full-screen layout for tablets
│   └── desktop_layout.html       <-- Standard desktop view with collapsible navigation
└── modules/
    ├── operatorsystem/           <-- Extends layouts/kiosk_layout.html
    ├── shiftleader/              <-- Extends layouts/desktop_layout.html
    ├── maintenance/              <-- Extends layouts/desktop_layout.html
    ├── approvals/                <-- Extends layouts/desktop_layout.html
    ├── supplychain/              <-- Extends layouts/desktop_layout.html
    └── setuppage/                <-- Extends layouts/desktop_layout.html
```

### 6.2 Modern Interactive Layer (No Heavy Framework Needed)
To achieve a blazing-fast, executive-grade UI without abandoning Django:
- **Tailwind CSS 3.x:** Pre-compiled unified CSS bundle with consistent spacing, industrial colors, and responsive utilities.
- **Alpine.js or HTMX:**
  - Used for real-time polling of machine status, cycle updates, and live downtime tickers without requiring full page refreshes.
  - Operator counter clicks (`+1`, `+5`) execute instant background POST requests and update badge counters via optimistic UI rendering.
- **WebSockets / Server-Sent Events (or 5s Celery Heartbeat):**
  - Instant floor alerts: when Machine #2 breaks down, Shift Leader's dashboard card flashes red immediately without manual refresh.

---

## 7. Migration & Rollout Plan

### Phase 1: Foundation & Shared Shell (Week 1)
- Create `templates/base_app.html` with unified topbar, sidebar, language selector, and design tokens.
- Implement the `RoleMiddleware` and dynamic role-based navigation helper in `accounts`.
- Eliminate hardcoded `elif` routing in `accounts/views.py` and `system/urls.py` in favor of dynamic landing page resolution based on `active_role`.

### Phase 2: Operator Kiosk Redesign (Week 2)
- Rebuild `operatorsystem/machine_dashboard.html` using the touch-first Kiosk layout.
- Implement high-visibility numerical counters, giant stop button, and quick-action modals for defects and stoppage reasons.
- Test touch responsiveness on factory floor tablets (10"–15").

### Phase 3: Shift Leader & Maintenance Unification (Week 3)
- Modernize the Shift Leader Floor Overview into an interactive 20-machine visual matrix.
- Convert maintenance tickets into an interactive Kanban workflow board.
- Integrate automated Telegram and Email alert feeds directly into the topbar notification bell.

### Phase 4: Master Setup & Work Order Consolidation (Week 4)
- Consolidate `setuppage` into clean, tabbed categories (Assets, Production Routing, Shift Calendars, Alert Automation).
- Merge duplicate work order endpoints into a streamlined Supply Chain & Work Order console.
- Conduct factory floor user acceptance testing (UAT) with operators and shift supervisors.

---
*Document Version: 1.0.0*  
*Target System: Siri MES / FactorySense*  
*Status: Approved Architecture Specification*
