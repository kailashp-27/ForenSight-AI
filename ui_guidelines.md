# 📋 ForenSight AI: UI/UX Master Guidelines
**Version:** 1.1 — Expanded with SiteAssist Design System Reference
**Agent Instruction:** This is the single source of truth for all UI/UX decisions. Every React component, Tailwind class, layout decision, and interaction pattern MUST reference and comply with these guidelines. Never deviate from this document without explicit user instruction.

---

## 0. Reference Inspiration

**Primary Reference:** [SiteAssist](https://www.siteassist.com/) — a Control of Works platform for high-risk industries (construction, utilities, nuclear, defense). Their design philosophy maps perfectly to ForenSight AI's needs:

| SiteAssist Design Element | ForenSight AI Equivalent |
|---|---|
| Digital Permits with Hold Points | Evidence Upload Wizard with Disclaimer Hold Points |
| Real-Time Hazards Detection badges | YOLOv8 Detection Alert Badges |
| Compliance checklists | Ethical Guardrail Acknowledgment Steps |
| Audit Trails | AuditLog Timeline Viewer |
| Field-ready mobile UX | Touch-friendly investigator dashboard |
| Task status boards | Evidence Processing Status Boards |

**Key SiteAssist Technical Observations:**
- Font: `Geist` (weight: 300, 400, 500, 600, 700) + `Geist Mono` (for IDs, timestamps, data values)
- Dark hero sections with `var(--primary--black)` background
- Light content sections with white cards and `bg-slate-50` page background
- Smooth GSAP-powered scroll animations (parallax, split-text reveals)
- `lenis` smooth scroll library for premium feel
- Blinking dot indicators for live/active status
- Divider lines between sections for clean structure
- Max container width `1440px` with fluid scaling via `clamp()`
- Data-theme attribute switching (`data-theme-status="light"` / `"dark"`)
- Pill-shaped badges (rounded-full) for status and tags
- Logo marquee for partner/evidence type display

---

## 1. Design Philosophy: "Mission-Critical & Zero-Clutter"

- **Purpose over Decoration:** Every element must serve a functional purpose. No decorative gradients or animations for their own sake.
- **High Information Density, Low Cognitive Load:** Use grids, data tables, and card-based layouts. Generous padding (`p-6` or `p-8` for cards). Never crowd elements.
- **Action-Oriented:** The investigator's next steps must be the most visually prominent elements (primary blue CTA buttons, never hidden in menus).
- **Trust & Transparency:** The AI must never feel like a black box. Every AI output must have a visible, clickable source reference.
- **Dual-Theme Ready:** Build all components to work in both light (default) and dark mode. Use CSS custom properties, never hard-coded colors.

---

## 2. Typography System

### Font Stack
```css
/* Primary — All UI text */
font-family: 'Geist', system-ui, -apple-system, sans-serif;

/* Monospace — IDs, timestamps, code, evidence hashes */
font-family: 'Geist Mono', 'Courier New', monospace;
```

### Import (add to index.css / index.html)
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Type Scale
| Use Case | Class | Weight |
|---|---|---|
| Page titles / Hero H1 | `text-3xl` | `font-bold` (700) |
| Section headers H2 | `text-xl` | `font-semibold` (600) |
| Card headers H3 | `text-base` | `font-semibold` (600) |
| Table headers | `text-xs uppercase tracking-wider` | `font-bold` (700) |
| Body text | `text-sm` | `font-normal` (400) |
| Muted / secondary | `text-sm text-slate-500` | `font-normal` (400) |
| Data values / IDs | `font-mono text-sm` | `font-medium` (500) |
| Timestamps | `font-mono text-xs text-slate-400` | `font-normal` (400) |

---

## 3. Color Palette & CSS Tokens

### CSS Custom Properties (define in `:root`)
```css
:root {
  /* Backgrounds */
  --color-bg-page:      #f8fafc;   /* slate-50 — page background */
  --color-bg-card:      #ffffff;   /* white — content cards */
  --color-bg-sidebar:   #0f172a;   /* slate-900 — left sidebar */
  --color-bg-header:    #ffffff;   /* white — top bar */

  /* Borders */
  --color-border:       #e2e8f0;   /* slate-200 */
  --color-border-dark:  #1e293b;   /* slate-800 — dark sidebar borders */

  /* Primary Accent — Trust & Action */
  --color-accent:       #2563eb;   /* blue-600 */
  --color-accent-hover: #1d4ed8;   /* blue-700 */
  --color-accent-light: #eff6ff;   /* blue-50 — selected rows, active states */

  /* Text */
  --color-text-primary: #0f172a;   /* slate-900 */
  --color-text-body:    #334155;   /* slate-700 */
  --color-text-muted:   #64748b;   /* slate-500 */
  --color-text-subtle:  #94a3b8;   /* slate-400 — timestamps, secondary info */
  --color-text-inverse: #ffffff;   /* white — on dark sidebar */

  /* Semantic — AI Guardrail Colors (CRITICAL - never repurpose) */
  --color-status-queued:    #64748b;   /* slate-500 */
  --color-status-analyzing: #2563eb;   /* blue-600 */
  --color-status-review:    #d97706;   /* amber-600 — AI flagged, needs human */
  --color-status-cleared:   #059669;   /* emerald-600 — processed, no flags */
  --color-status-failed:    #dc2626;   /* red-600 — error */
  --color-status-pending:   #7c3aed;   /* violet-600 — queued for processing */

  /* Shadow */
  --shadow-card: 0 1px 3px 0 rgb(0 0 0 / 0.07), 0 1px 2px -1px rgb(0 0 0 / 0.07);
  --shadow-elevated: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
}
```

### Tailwind Shorthand Reference
| Purpose | Tailwind Class(es) |
|---|---|
| Page bg | `bg-slate-50` |
| Card bg | `bg-white border border-slate-200 shadow-sm` |
| Sidebar bg | `bg-slate-900` |
| Primary button | `bg-blue-600 hover:bg-blue-700 text-white` |
| Secondary button | `bg-white border border-slate-300 text-slate-700 hover:bg-slate-50` |
| Destructive button | `bg-red-600 hover:bg-red-700 text-white` |
| Input field | `border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-blue-500` |

---

## 4. Layout Architecture

### App Shell (Fixed)
```
┌─────────────────────────────────────────────────────────────┐
│  SIDEBAR (240px fixed)  │  MAIN CONTENT AREA (flex-1)       │
│  bg-slate-900           │  bg-slate-50                       │
│                         │  ┌─────────────────────────────┐  │
│  [Logo]                 │  │ TOP BAR (56px) bg-white      │  │
│  ─────────              │  │ Page Title | Breadcrumb | CTA│  │
│  Navigation             │  └─────────────────────────────┘  │
│  - Dashboard            │                                    │
│  - Cases                │  ┌─────────────────────────────┐  │
│  - Evidence             │  │  KPI ROW (4 stat cards)     │  │
│  - Settings             │  └─────────────────────────────┘  │
│                         │                                    │
│  ─────────              │  ┌─────────────────────────────┐  │
│  [User info]            │  │  PRIMARY CONTENT             │  │
│                         │  │  (table / grid / split pane) │  │
└─────────────────────────────────────────────────────────────┘
```

### Responsive Breakpoints
- Mobile (`< 768px`): Sidebar collapses to icon-only or hamburger drawer
- Tablet (`768px–1024px`): Sidebar shows icons + abbreviated labels
- Desktop (`>= 1024px`): Full sidebar with labels

### Split-Pane Evidence Workspace
- **Trigger:** When opening an evidence file for review
- Left pane (55%): Media viewer (image/video with bounding box + Grad-CAM overlay toggle)
- Right pane (45%): AI chat / timeline assistant
- Both panes independently scrollable

### Max Content Width
- Container: `max-w-screen-xl mx-auto` (1280px)
- Full-bleed sections: No max-width constraint

---

## 5. Core Components Reference

### 5.1 KPI Stat Cards
```tsx
// 4-column grid at the top of Dashboard and Case Detail
// Each card shows: icon, metric number, label, optional delta trend
<KpiCard
  icon={<FolderIcon />}
  value="124"
  label="Total Evidence"
  trend="+12 this week"    // optional
  variant="default"        // default | warning | success | danger
/>
```
- Card: `bg-white border border-slate-200 rounded-xl p-6 shadow-sm`
- Number: `text-3xl font-bold text-slate-900`
- Label: `text-sm text-slate-500 mt-1`
- Trend: `text-xs text-emerald-600 font-medium`

### 5.2 Status Badges (Pill Shape)
```tsx
<Badge variant="analyzing" />   // Renders "ANALYZING" in blue pill
<Badge variant="review" />      // "REVIEW REQUIRED" in amber pill
<Badge variant="cleared" />     // "CLEARED" in green pill
<Badge variant="queued" />      // "QUEUED" in slate pill
<Badge variant="failed" />      // "FAILED" in red pill
```
- Shape: `rounded-full px-2.5 py-0.5 text-xs font-semibold`
- Include a colored dot (`●`) before the text
- `ANALYZING`: Pulsing dot animation (`animate-pulse`)

### 5.3 Live Processing Toast (Socket.io)
```tsx
// Appears bottom-right, non-blocking, stacks for multiple jobs
// Shows: [pulsing blue dot] "Processing CCTV_footage.mp4 — 67%"
// Includes a thin progress bar at the bottom of the toast
// Auto-dismisses on COMPLETED, stays open on FAILED
```
- Container: `fixed bottom-4 right-4 z-50 flex flex-col gap-2`
- Toast: `bg-white border border-slate-200 rounded-xl shadow-elevated p-4 w-80`
- Progress bar: `h-1 bg-blue-600 rounded-full transition-all duration-300`

### 5.4 Data Tables
- Header: `bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 font-bold`
- Row: `border-b border-slate-100 hover:bg-slate-50 transition-colors`
- Row height: `h-14` minimum (field-ready touch targets)
- Clickable rows: cursor-pointer with hover highlight
- Sortable columns: show sort arrow icon on hover/active

### 5.5 Evidence Upload Wizard (Hold Points)
Step-by-step modal:
1. **Step 1: Select File** — Drag & drop zone (dashed border, file icon, "or Browse")
2. **Step 2: Assign to Case** — Dropdown selector for case + evidence type selector
3. **Step 3: Disclaimer Hold Point** — Checkbox: "I confirm that uploading this evidence complies with chain-of-custody protocols and I accept responsibility for its accuracy." **Next button disabled until checked.**
4. **Step 4: Upload** — Progress bar with Socket.io live updates

Dropzone styling:
```css
border: 2px dashed var(--color-border);
border-radius: 12px;
background: var(--color-accent-light);
/* On drag-over: border-blue-600 bg-blue-50 */
```

### 5.6 Blinking Live Indicator (SiteAssist Pattern)
```tsx
// Used to indicate active processing or live Socket.io connection
<div className="relative flex h-2.5 w-2.5">
  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-600" />
</div>
```

### 5.7 Vertical Audit Timeline (Stepper)
```
  ●  [2026-08-19 14:32]  Evidence uploaded by kailashp-27
  │
  ●  [2026-08-19 14:33]  YOLOv8 processing started
  │
  ●  [2026-08-19 14:35]  2 detections found: [weapon][vehicle]  ← clickable citations
  │
  ◌  [Pending]           RAG Summary generation
```
- Timeline line: `border-l-2 border-slate-200 ml-3`
- Dot: `w-3 h-3 rounded-full bg-blue-600 -ml-1.5`
- Citation badge: `text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-mono cursor-pointer hover:bg-amber-200`

### 5.8 Grad-CAM Overlay Toggle
```tsx
// Positioned above the evidence image/video viewer
<div className="flex items-center gap-2 mb-2">
  <span className="text-xs text-slate-500">AI Heatmap</span>
  <Toggle checked={showHeatmap} onChange={setShowHeatmap} />
  <span className="text-xs font-medium text-blue-600">
    {showHeatmap ? 'Showing Grad-CAM Overlay' : 'Hidden'}
  </span>
</div>
```

### 5.9 AI Disclaimer Banner (Permanent)
```tsx
// Pinned to top of every AI/LLM output section, NEVER removable
<div className="flex items-center gap-2 px-4 py-2 bg-amber-50 border-b border-amber-200">
  <AlertTriangleIcon className="w-4 h-4 text-amber-600 flex-shrink-0" />
  <p className="text-xs text-amber-700">
    AI-generated summaries are for assistive purposes only.
    Do not use for definitive legal conclusions.
  </p>
</div>
```

### 5.10 Sidebar Navigation Item
```tsx
// Active: bg-blue-600 text-white rounded-lg
// Inactive: text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg
// Each item: icon (20px) + label text, h-10, px-3
```

---

## 6. Micro-Animations & Interactions

| Interaction | Implementation |
|---|---|
| Page transition | `opacity-0 → opacity-100` fade, 150ms |
| Card hover | `hover:shadow-md transition-shadow duration-200` |
| Button press | `active:scale-95 transition-transform duration-100` |
| Processing badge pulse | `animate-pulse` on the colored dot |
| Toast slide-in | `translate-x-full → translate-x-0` from right, 300ms ease-out |
| Toast slide-out | `translate-x-0 → translate-x-full` 200ms ease-in |
| Table row hover | `bg-slate-50 transition-colors duration-100` |
| Sidebar nav hover | `bg-slate-800 transition-colors duration-150` |
| Dropzone drag-over | `border-blue-500 bg-blue-50 scale-[1.01] transition-all` |
| Modal open | `opacity-0 scale-95 → opacity-100 scale-100` 200ms ease-out |

---

## 7. Form Design Principles

- **Label above input always** — Never use placeholder-only labels (accessibility)
- **Helper text below inputs** — `text-xs text-slate-500 mt-1`
- **Error state:** `border-red-500` + red helper text + red icon
- **Required fields:** Asterisk `*` in `text-red-500` after label
- **Field height:** Minimum `h-11` for touch-friendliness (field-ready)
- **Disabled state:** `opacity-50 cursor-not-allowed`
- **Focus ring:** `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1`

---

## 8. Icon Library

Use **Lucide React** exclusively:
```bash
npm install lucide-react
```
Standard sizes:
- Navigation icons: `w-5 h-5`
- Inline/badge icons: `w-4 h-4`
- KPI card icons: `w-6 h-6`
- Empty state illustrations: `w-12 h-12 text-slate-300`

Mandatory icon → use case mapping:
| Icon | Use |
|---|---|
| `FolderOpen` | Cases |
| `FileVideo` | Video evidence |
| `FileImage` | Image evidence |
| `FileAudio` | Audio evidence |
| `FileText` | Document/PDF evidence |
| `Shield` | ForenSight brand / ethical guardrails |
| `AlertTriangle` | AI disclaimer banner |
| `CheckCircle` | Cleared status |
| `Clock` | Queued / pending |
| `Loader2` | Spinning loader (animate-spin) |
| `Eye` | View / inspect |
| `Upload` | Upload CTA |
| `Activity` | Live/real-time indicator |
| `Search` | Search inputs |
| `Filter` | Filter controls |
| `ChevronRight` | Breadcrumb separator / row arrow |

---

## 9. Empty States

When a list/table has no data:
```tsx
<div className="flex flex-col items-center justify-center py-16 text-center">
  <FolderOpenIcon className="w-12 h-12 text-slate-300 mb-4" />
  <h3 className="text-base font-semibold text-slate-700">No cases yet</h3>
  <p className="text-sm text-slate-500 mt-1 mb-4">
    Create your first investigation case to get started.
  </p>
  <Button variant="primary">Create Case</Button>
</div>
```

---

## 10. Ethical Guardrail UI Rules (NON-NEGOTIABLE)

1. **The AI disclaimer banner** (`§5.9`) must appear on EVERY page that shows AI-generated content. It cannot be dismissed, minimized, or hidden by CSS.
2. **REVIEW REQUIRED badge** (amber) must be shown for ANY evidence that was flagged by YOLOv8 or the texture classifier. It must never auto-clear without human confirmation.
3. **Hold Point steps** in the upload wizard must use `disabled={!accepted}` on the Next button. Never bypass with JavaScript trickery.
4. **Confidence scores** must always be displayed alongside detections (e.g., "Firearm — 84% confidence"). Never show a label without its confidence.
5. **Grad-CAM overlay** must default to OFF (`showHeatmap = false`) and require explicit toggle by the investigator.
6. **LLM citations** must be hyperlinks, not plain text. Clicking a citation must scroll/highlight the source evidence.
7. **No autonomous conclusions:** Any LLM-generated text that contains words like "guilty", "confirmed", "conclusive" must be caught and replaced with a warning banner.

---

## 11. Accessibility Standards

- All interactive elements must have `aria-label` or visible text labels
- Color alone must never convey status — always pair with icon or text
- Focus rings must be visible (never `outline-none` without a replacement)
- Minimum touch target: `44×44px` (h-11 minimum)
- Keyboard navigation must work for all modals, dropdowns, and forms
- `role="alert"` on all toast notifications

---

## 12. Component File Structure Convention

```
frontend/src/
├── components/
│   ├── layout/
│   │   ├── AppLayout.tsx      ← Root shell (sidebar + content)
│   │   ├── Sidebar.tsx        ← Left navigation
│   │   └── TopBar.tsx         ← Page header + breadcrumb
│   ├── ui/
│   │   ├── Badge.tsx          ← Status pill badges
│   │   ├── Button.tsx         ← Primary, secondary, destructive variants
│   │   ├── Card.tsx           ← Base card container
│   │   ├── KpiCard.tsx        ← Stats card with icon + trend
│   │   ├── Modal.tsx          ← Accessible modal/dialog
│   │   ├── StatusToast.tsx    ← Socket.io processing toasts
│   │   ├── Toggle.tsx         ← On/off toggle (Grad-CAM etc.)
│   │   └── Spinner.tsx        ← Loading indicator
│   ├── evidence/
│   │   ├── EvidenceUploadWizard.tsx
│   │   ├── EvidenceCard.tsx
│   │   └── EvidenceTable.tsx
│   └── ai/
│       ├── AiDisclaimerBanner.tsx   ← ALWAYS include in AI sections
│       ├── DetectionBadge.tsx       ← YOLOv8 detection pill
│       ├── GradCamToggle.tsx
│       └── AuditTimeline.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── Cases.tsx
│   ├── CaseDetail.tsx
│   └── EvidenceViewer.tsx     ← Split-pane workspace
├── store/
│   ├── caseStore.ts
│   ├── evidenceStore.ts
│   └── socketStore.ts
└── services/
    ├── api.ts
    └── socket.ts
```

---

## 13. Do's and Don'ts

### ✅ DO
- Use `Geist` for all text, `Geist Mono` for IDs and data
- Use semantic status colors strictly as defined in §3
- Always show confidence % alongside AI detections
- Always include the AI disclaimer banner in AI sections
- Keep buttons large (h-11 minimum)
- Add `transition-*` classes to all interactive elements
- Use `rounded-xl` for cards, `rounded-lg` for inputs, `rounded-full` for badges

### ❌ DON'T
- Don't use Tailwind arbitrary values like `text-[13px]` — stick to the scale
- Don't use red for anything other than critical errors or destructive actions
- Don't use green for anything other than successfully completed processing
- Don't add decorative gradients to functional UI elements
- Don't remove or hide the AI disclaimer banner
- Don't auto-confirm Hold Point steps programmatically
- Don't use `outline-none` without a focus ring replacement
- Don't commit `node_modules/`, `.venv/`, or `backend/storage/*` to git