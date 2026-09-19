# PVNetwork UI/UX Audit — sequential 1.0.x hardening

Status values: `PASS`, `PARTIAL`, `OPEN`, `N/A`. A page cannot be marked PASS from code inspection alone when interaction or viewport behavior needs browser verification.

## Global requirements

| Requirement | Task | Current |
|---|---:|---|
| Mobile navigation remains reachable | PVN-100 | PARTIAL |
| 44×44 touch targets | PVN-113 | OPEN |
| No page-level horizontal overflow | PVN-114 | OPEN |
| Persian RTL | PVN-115 | PARTIAL |
| English LTR | PVN-116 | PARTIAL |
| Keyboard-only operation | PVN-117 | OPEN |
| Visible focus states | PVN-118 | OPEN |
| Accessible icon controls | PVN-119 | OPEN |
| Text contrast | PVN-120 | OPEN |
| Reduced motion | PVN-121 | OPEN |
| Modal viewport containment | PVN-122 | OPEN |
| Management-table mobile strategy | PVN-123 | PARTIAL |
| Responsive search/sort/pagination | PVN-124 | PARTIAL |
| Loading/empty/error/retry states | PVN-125 | PARTIAL |
| Duplicate-submit prevention | PVN-126 | PARTIAL |

## Main pages

| Page | Desktop | Tablet | Phone | RTL/LTR | Keyboard | Task |
|---|---|---|---|---|---|---:|
| Dashboard | PARTIAL | PARTIAL | PARTIAL | PARTIAL | OPEN | PVN-109 |
| Users | PARTIAL | PARTIAL | PARTIAL | PARTIAL | OPEN | PVN-101 |
| Nodes | PARTIAL | PARTIAL | PARTIAL | PARTIAL | OPEN | PVN-102 |
| Admins / Resellers | PARTIAL | PARTIAL | PARTIAL | PARTIAL | OPEN | PVN-103 |
| Operations Center | PARTIAL | OPEN | OPEN | PARTIAL | OPEN | PVN-104 |
| Security | PARTIAL | OPEN | OPEN | PARTIAL | OPEN | PVN-105 |
| Fleet Management | PARTIAL | OPEN | OPEN | PARTIAL | OPEN | PVN-106 |
| Monitoring | PARTIAL | OPEN | OPEN | PARTIAL | OPEN | PVN-107 |
| Bandwidth Control | PARTIAL | OPEN | OPEN | PARTIAL | OPEN | PVN-108 |
| Login | PARTIAL | PARTIAL | PARTIAL | PARTIAL | OPEN | PVN-110 |
| Subscription page | PARTIAL | PARTIAL | PARTIAL | PARTIAL | OPEN | PVN-111 |

## Core dialogs/workflows

| Workflow | Task | Current issue to verify/fix |
|---|---:|---|
| User actions dropdown | PVN-112 | touch size, ARIA menu semantics, keyboard/edge positioning |
| Renew User | PVN-127 | short-screen scrolling, button reachability, RTL/LTR |
| AnyConnect User | PVN-128 | credential rows, copy controls, short-screen scrolling |
| Add/Edit User | PVN-129 | numeric input ergonomics, validation, node selection wrapping |
| Add/Edit Node | PVN-130 | long labels, automatic/manual mode on phone, deploy progress |
| Add/Edit Admin | PVN-131 | quotas/permissions on phone, deletion transfer flow |
| Backup/Restore | PVN-132 | file picker/RESTORE confirmation/progress/table on phone |
| Domain History | PVN-133 | long domains, internal scroll, close/action reachability |
| Download/profile chooser | PVN-133 | long node names and action reachability |

## Required viewport evidence

For each release-visible page/workflow, record PASS/FAIL at: `360`, `375`, `390`, `430`, `768`, `1024`, `1366`, `1440`, `1920` px. Core admin flows additionally require zoom checks at 100%, 125% and 150%.

| Viewport | Dashboard | Users | Nodes | Admins | Ops | Security | Fleet | Monitor | Bandwidth |
|---:|---|---|---|---|---|---|---|---|---|
| 360 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |
| 375 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |
| 390 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |
| 430 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |
| 768 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |
| 1024 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |
| 1366 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |
| 1440 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |
| 1920 | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN | OPEN |

## Interaction evidence

- Mouse: OPEN
- Touch: OPEN
- Keyboard only: OPEN
- Visible focus: OPEN
- Escape/close behavior: OPEN
- Focus return after modal/dropdown: OPEN
- Reduced motion: OPEN
- Light mode: PARTIAL
- Dark mode: PARTIAL
- Persian RTL: PARTIAL
- English LTR: PARTIAL

## Current code observations

The existing frontend already has a responsive breakpoint near 992 px, a mobile bottom navigation, table-container horizontal scrolling, responsive admin cards and stacked modal actions near 768 px. These are useful foundations but do not by themselves prove full phone/tablet usability or accessibility. The sequential 1.0.x UX hardening stream focuses on global primitives first, then page-specific exceptions, with one Production-visible PVN task per patch release.

## Evidence policy

Do not change `OPEN`/`PARTIAL` to `PASS` without reproducible evidence: automated test output, verified production build, browser screenshot/video from sanitized data, or a documented manual viewport/accessibility check. Production screenshots must never expose live customer or infrastructure data.
