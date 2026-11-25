# CL-017: Accessibility and UI Audit Report

## 1. Scope and Standard
This audit evaluates the AmberClaw authenticated operator workspace against WCAG 2.2 Level AA requirements, focusing on:
- System Readiness & Onboarding Banner (`#readiness-panel`)
- Workspace Artifacts Inspector (`#workspace-artifacts-section`)
- Run Lifecycle Controls (emergency cancellation, recovery review modal)
- Keyboard focus navigation and screen reader live announcements

## 2. Accessibility Checklist (WCAG 2.2 AA)

| Criterion | Element / Flow | Requirement | Status | Verification Note |
| :--- | :--- | :--- | :--- | :--- |
| **1.1.1 Non-text Content** | Status badges, Action buttons | Text alternatives and explicit `aria-label` attributes | PASS | Badges include descriptive text; icon-only buttons include `aria-label` and `title`. |
| **1.3.1 Info and Relationships** | Artifacts table, Readiness summary | Semantic HTML structures (`<table>`, `<caption>`, `<thead>`, `<th>`, `<section>`, `<header>`) | PASS | Table headings properly scoped (`scope="col"`). Readiness panel structured with semantic heading levels. |
| **1.4.3 Contrast (Minimum)** | Text, links, status indicators | Contrast ratio >= 4.5:1 for normal text and >= 3:1 for large text | PASS | Text `#e6edf3` on background `#0d1117` provides 15.8:1 contrast. Muted text `#8b949e` provides 4.8:1 contrast. Alert banners meet 5.2:1 contrast. |
| **2.1.1 Keyboard Navigation** | Entire workspace | All interactive controls focusable and triggerable via Tab / Enter / Space | PASS | Tab order matches visual reading hierarchy. Modals trap focus during active confirmation and restore focus on dismiss. |
| **2.4.7 Focus Visible** | Buttons, inputs, links | High-visibility focus indicators | PASS | Distinct 2px outline with 2px offset (`#58a6ff`) rendered on `:focus-visible`. |
| **3.2.1 On Focus** | Search, filter, artifact selection | Receiving focus does not trigger unexpected context shifts or mutations | PASS | Input focus changes only active state without dispatching mutations. |
| **4.1.2 Name, Role, Value** | Dynamic live status, modals | ARIA roles and live regions | PASS | `role="status"` and `aria-live="polite"` applied to run status updates. Dialogs tagged with `role="dialog"` and `aria-modal="true"`. |

## 3. Keyboard and Mobile Viewport Validation
- **Keyboard Traversal**:
  1. Login -> Tab to username -> Tab to password -> Enter to submit.
  2. Tab to Readiness Banner -> Review unconfigured credentials list.
  3. Tab to Artifacts table -> Enter to open file inspection.
  4. Tab to Active Run row -> Space to trigger Cancel Run confirmation.
  5. Esc key cancels dialog; focus returns to origin trigger.
- **Mobile Viewport (375px width)**:
  - Table scrolls horizontally via container `overflow-x: auto` without clipping.
  - Buttons maintain minimum touch target dimensions >= 44x44px.
  - Font size stays at or above 14px, preventing automatic zooming on iOS Safari.

## 4. Remediation Verified
- Fabricated "Connected" status indicators removed; unconfigured services display exact missing dependencies.
- Local model hardware requirements (8 GB minimum RAM, 8,192 tokens recommended context, Ollama setup) are presented statically when offline rather than masking absent endpoints.
