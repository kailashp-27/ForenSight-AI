# 📋 ForenSight AI: UI/UX Master Guidelines

**Version:** 1.3 — Fully Dark-First Implementation of Investigation Hub Layout  
**Last Updated:** 2026-08-22  
**Agent Instruction:** This is the single source of truth for all UI/UX decisions. Every React component, inline style, visual token, layout decision, and interaction pattern MUST reference and comply with these guidelines. Never deviate from this document without explicit user instruction.

***

## 0. Design Inspirations

**Primary Visual Reference:** [SiteAssist](https://www.siteassist.com/) — a Control of Works platform for high-risk industries (construction, utilities, nuclear, defense).

SiteAssist demonstrates strong patterns for:
- High-stakes workflows with compliance requirements
- Clear status indicators and audit trails
- Field-ready, touch-friendly interfaces

**Additional References:**
- **Forensic Tracker** (GovTech/Legal UI) — structured evidence tracking for law enforcement 
- **Evidex** — forensics dashboard with timeline reconstruction capabilities 
- **Modern SaaS dashboards** (Linear, Stripe, Mercury) — for information density and progressive disclosure 

> ⚠️ **Important:** ForenSight AI uses a fully dark-first theme (deep navy-black canvas and slate-900 elevated cards) to reduce eye strain and look highly professional.


### SiteAssist Design Element Mappings

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

***

## 1. Design Philosophy: "Mission-Critical & Zero-Clutter"

- **Purpose over Decoration:** Every element must serve a functional purpose. No decorative gradients or animations for their own sake.
- **High Information Density, Low Cognitive Load:** Use grids, data tables, and card-based layouts. Generous padding (`p-6` or `p-8` for cards). Never crowd elements.
- **Action-Oriented:** The investigator's next steps must be the most visually prominent elements (primary blue CTA buttons, never hidden in menus).
- **Trust & Transparency:** The AI must never feel like a black box. Every AI output must have a visible, clickable source reference.
- **Dual-Theme Ready:** Build all components to work in both light (default) and dark mode. Use CSS custom properties, never hard-coded colors.
- **Progressive Disclosure:** Show the minimum information needed for the user's next decision. Reveal additional details on demand (click, hover, expand). Avoid dumping all data at once. 

***

## 2. Typography System

### Font Stack

```css
/* Primary — All UI text */
font-family: 'Geist', system-ui, -apple-system, sans-serif;

/* Monospace — IDs, timestamps, code, evidence hashes */
font-family: 'Geist Mono', 'Courier New', monospace;
```

### Import (add to `index.css` / `index.html`)

```html
<!-- Geist from Fontsource CDN (recommended) -->
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link href="https://cdn.jsdelivr.net/npm/geist@1.0.0/dist/geist.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/geist@1.0.0/dist/geist-mono.css" rel="stylesheet">

<!-- Alternative: Self-host from npm package -->
<!-- npm install geist -->
```

> ⚠️ **Note:** Geist is NOT available on Google Fonts. Use the Vercel/Fontsource CDN or self-host via npm package. [jsdelivr](https://www.jsdelivr.com/package/npm/geist-svelte)

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

***

## 3. Color Palette & CSS Tokens

### Base UI Colors (Light Theme)

```css
:root {
  /* Backgrounds */
  --color-bg-page:      #f8fafc;   /* slate-50 — page background */
  --color-bg-card:      #ffffff;   /* white — content cards */
  --color-bg-canvas:    #f1f5f9;   /* slate-100 — focus canvas background */
  --color-bg-sidebar:   #0f172a;   /* slate-900 — dark surfaces */
  --color-bg-header:    #ffffff;   /* white — top bar */

  /* Borders */
  --color-border:       #e2e8f0;   /* slate-200 */
  --color-border-dark:  #1e293b;   /* slate-800 — dark surface borders */

  /* Primary Accent — Trust & Action */
  --color-accent:       #A855F7;   /* vibrant digital violet */
  --color-accent-hover: #9333ea;   /* darker violet */
  --color-accent-light: rgba(168, 85, 247, 0.1);

  /* Secondary Accent */
  --color-teal:         #F43F5E;   /* electric rose magenta */
  --color-teal-light:   rgba(244, 63, 94, 0.1);

  /* Text */
  --color-text-primary: #0f172a;   /* slate-900 */
  --color-text-body:    #334155;   /* slate-700 */
  --color-text-muted:   #64748b;   /* slate-500 */
  --color-text-subtle:  #94a3b8;   /* slate-400 — timestamps, secondary info */
  --color-text-inverse: #ffffff;   /* white — on dark backgrounds */

  /* Shadow */
  --shadow-card: 0 1px 3px 0 rgb(0 0 0 / 0.07), 0 1px 2px -1px rgb(0 0 0 / 0.07);
  --shadow-elevated: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-canvas: inset 0 2px 4px 0 rgb(0 0 0 / 0.03);
}
```

### Semantic Status Colors (CRITICAL - never repurpose)

```css
:root {
  --color-status-queued:    #64748b;   /* slate-500 */
  --color-status-analyzing: #2563eb;   /* blue-600 */
  --color-status-review:    #d97706;   /* amber-600 — AI flagged, needs human */
  --color-status-cleared:   #059669;   /* emerald-600 — processed, no flags */
  --color-status-failed:    #dc2626;   /* red-600 — error */
  --color-status-pending:   #7c3aed;   /* violet-600 — queued for processing */
}
```

### Data Visualization Palette (Distinct from status colors)

```css
:root {
  --color-entity-person:    #3b82f6;   /* blue-500 */
  --color-entity-device:    #10b981;   /* emerald-500 */
  --color-entity-account:   #f59e0b;   /* amber-500 */
  --color-entity-location:  #8b5cf6;   /* violet-500 */
  --color-entity-network:   #ec4899;   /* pink-500 */
  --color-entity-event:     #64748b;   /* slate-500 */
}
```

### Dark Theme Tokens

```css
[data-theme="dark"] {
  --color-bg-page:     #0A0712;   /* very dark ink violet */
  --color-bg-card:     #150F24;   /* deep purple-gray */
  --color-bg-canvas:   #0A0712;   /* very dark ink violet */
  --color-bg-sidebar:  #0A0712;   /* very dark ink violet */
  --color-bg-header:   #150F24;   /* deep purple-gray */
  
  --color-border:      #334155;   /* slate-700 */
  --color-border-dark: #475569;   /* slate-600 */
  
  --color-text-primary:#F1EEF7;   /* lavender mist white */
  --color-text-body:   #cbd5e1;   /* slate-300 */
  --color-text-muted:  #94a3b8;   /* slate-400 */
  --color-text-subtle: #64748b;   /* slate-500 */
  --color-text-inverse:#0f172a;   /* slate-900 — on light backgrounds */
  
  /* Keep accent and status colors the same */
}
```

### Tailwind Shorthand Reference

| Purpose | Tailwind Class(es) |
|---|---|
| Page bg | `bg-slate-50` (light) / `dark:bg-slate-950` (dark) |
| Card bg | `bg-white border border-slate-200 shadow-sm` |
| Canvas bg | `bg-slate-100` (light) / `dark:bg-slate-900` (dark) |
| Primary button | `bg-blue-600 hover:bg-blue-700 text-white` |
| Secondary button | `bg-white border border-slate-300 text-slate-700 hover:bg-slate-50` |
| Destructive button | `bg-red-600 hover:bg-red-700 text-white` |
| Input field | `border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-blue-500` |

***

## 4. Layout Architecture: Investigation Hub

### Primary Layout Structure

The default dashboard is **NOT** a sidebar + cards layout. It is a three-zone **Investigation Hub** optimized for forensic workflows.

```
┌─────────────────────────────────────────────────────────────┐
│  GLOBAL CONTEXT BAR (56–64px)                               │
│  [Logo] [Global Search...]              [Workspace] [User]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    FOCUS CANVAS                             │
│   (Timeline + Entity Graph hybrid view)                     │
│                                                             │
│                                                             │
│                                                             │
│  (Floating Action Orb - bottom-left)                        │
│       o                                                     │
├─────────────────────────────────────────────────────────────┤
│ INTELLIGENCE STRIP (25–30% height, collapsible)             │
│ [Leads] [Hypotheses] [Gaps] [Recent Activity]               │
│ [Lead cards grid...]                                        │
└─────────────────────────────────────────────────────────────┘
```

### Zone Descriptions

#### 4.1. Global Context Bar (Top)

- **Height:** 56–64px
- **Background:** `var(--color-bg-header)`
- **Border-bottom:** `border-b border-slate-200`
- **Content:**
  - Left: Logo + "ForenSight AI" wordmark
  - Center: Global search input (prominent, `w-96` on desktop)
  - Right: Workspace selector, time window, user profile, notifications

#### 4.2. Focus Canvas (Center)

- **Purpose:** Primary workspace for investigating a case
- **Background:** `var(--color-bg-canvas)`
- **Content:** Timeline + Entity Graph hybrid view (see §5.11)
- **Behavior:**
  - Horizontal scroll for time navigation
  - Click events → opens Context Panel (§5.12)
  - Drag to select time range → filters Intelligence Strip
  - Toggle view modes: Timeline | Graph | Map

#### 4.3. Intelligence Strip (Bottom)

- **Height:** 25–30% of viewport (collapsible)
- **Background:** `var(--color-bg-card)`
- **Border-top:** `border-t border-slate-200`
- **Content:** AI-driven insights organized into tabs (see §5.13)

#### 4.4. Floating Action Orb (Navigation)

- **Position:** Bottom-left of Focus Canvas
- **Default state:** Small dot (`w-3 h-3 rounded-full bg-slate-400`)
- **Active state:** Expands to radial menu on click/hover
- **Menu items:** New Case, New Query, Board View, Reports, Settings, Help

### Responsive Breakpoints

- **Mobile (`< 768px`):**
  - Global Context Bar: Search collapses to icon
  - Focus Canvas: Vertical timeline instead of horizontal
  - Intelligence Strip: Full-screen modal when opened
  - Floating Orb: Larger touch target (`w-12 h-12`)

- **Tablet (`768px–1024px`):**
  - Global Context Bar: Abbreviated search placeholder
  - Focus Canvas: Standard horizontal timeline
  - Intelligence Strip: 40% height

- **Desktop (`>= 1024px`):**
  - Full layout as described above

### Max Content Width

- **Container:** `max-w-[1440px] mx-auto` (matches SiteAssist reference)
- **Full-bleed sections:** Focus Canvas has no max-width constraint
- **Fluid scaling:** Use `clamp()` for responsive typography and spacing

***

## 5. Core Components Reference

### 5.1. KPI Stat Cards

```tsx
// Used in Intelligence Strip tabs or summary views
// Each card shows: icon, metric number, label, optional delta trend
<KpiCard
  icon={<FolderIcon />}
  value="124"
  label="Total Evidence"
  trend="+12 this week"    // optional
  variant="default"        // default | warning | success | danger
/>
```

- **Card:** `bg-white border border-slate-200 rounded-xl p-6 shadow-sm`
- **Number:** `text-3xl font-bold text-slate-900`
- **Label:** `text-sm text-slate-500 mt-1`
- **Trend:** `text-xs text-emerald-600 font-medium`

### 5.2. Status Badges (Pill Shape)

```tsx
<Badge variant="analyzing" />   // Renders "ANALYZING" in blue pill
<Badge variant="review" />      // "REVIEW REQUIRED" in amber pill
<Badge variant="cleared" />     // "CLEARED" in green pill
<Badge variant="queued" />      // "QUEUED" in slate pill
<Badge variant="failed" />      // "FAILED" in red pill
```

- **Shape:** `rounded-full px-2.5 py-0.5 text-xs font-semibold`
- **Include:** A colored dot (`●`) before the text
- **Animation:** `ANALYZING` uses pulsing dot (`animate-pulse`)

### 5.3. Live Processing Toast (Socket.io)

```tsx
// Appears top-right (to avoid Intelligence Strip overlap), non-blocking, stacks for multiple jobs
// Shows: [pulsing blue dot] "Processing CCTV_footage.mp4 — 67%"
// Includes a thin progress bar at the bottom of the toast
// Auto-dismisses on COMPLETED, stays open on FAILED
```

- **Container:** `fixed top-4 right-4 z-50 flex flex-col gap-2`
- **Toast:** `bg-white border border-slate-200 rounded-xl shadow-elevated p-4 w-80`
- **Progress bar:** `h-1 bg-blue-600 rounded-full transition-all duration-300`

### 5.4. Data Tables

- **Header:** `bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 font-bold`
- **Row:** `border-b border-slate-100 hover:bg-slate-50 transition-colors`
- **Row height:** `h-14` minimum (field-ready touch targets)
- **Clickable rows:** `cursor-pointer` with hover highlight
- **Sortable columns:** Show sort arrow icon on hover/active

### 5.5. Evidence Upload Wizard (Hold Points)

**Step-by-step modal:**

1. **Step 1: Select File** — Drag & drop zone (dashed border, file icon, "or Browse")
2. **Step 2: Assign to Case** — Dropdown selector for case + evidence type selector
3. **Step 3: Disclaimer Hold Point** — Checkbox: "I confirm that uploading this evidence complies with chain-of-custody protocols and I accept responsibility for its accuracy." **Next button disabled until checked.**
4. **Step 4: Upload** — Progress bar with Socket.io live updates

**Dropzone styling:**

```css
border: 2px dashed var(--color-border);
border-radius: 12px;
background: var(--color-accent-light);
/* On drag-over: border-blue-600 bg-blue-50 */
```

### 5.6. Blinking Live Indicator (SiteAssist Pattern)

```tsx
// Used to indicate active processing or live Socket.io connection
<div className="relative flex h-2.5 w-2.5">
  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-600" />
</div>
```

### 5.7. Vertical Audit Timeline (Stepper)

```
  ●  [2026-08-19 14:32]  Evidence uploaded by kailashp-27
  │
  ●  [2026-08-19 14:33]  YOLOv8 processing started
  │
  ●  [2026-08-19 14:35]  2 detections found: [weapon][vehicle]  ← clickable citations
  │
  ◌  [Pending]           RAG Summary generation
```

- **Timeline line:** `border-l-2 border-slate-200 ml-3`
- **Dot:** `w-3 h-3 rounded-full bg-blue-600 -ml-1.5`
- **Citation badge:** `text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-mono cursor-pointer hover:bg-amber-200`

### 5.8. Grad-CAM Overlay Toggle

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

### 5.10. Global Context Bar Navigation

```tsx
// Replaces traditional sidebar navigation
// Global search, workspace selector, user profile
// Height: h-14 (56px) or h-16 (64px)
// Background: var(--color-bg-header)
// Border-bottom: border-b border-slate-200
```

**Search input:**
- `w-96` on desktop, `w-48` on tablet, icon-only on mobile
- Placeholder: "Search cases, entities, events, evidence…"
- Focus ring: `focus:ring-2 focus:ring-blue-500`

**Workspace selector:**
- Dropdown with current workspace name
- Icon: `Briefcase` or `FolderOpen`

**User profile:**
- Avatar + name dropdown
- Items: Profile, Settings, Sign out

### 5.11. Focus Canvas (Timeline + Graph Hybrid)

**Purpose:** Primary workspace for investigating a case. Shows events over time with associated entities.

**Structure:**
- Horizontal timeline across center
- Event markers (pills/diamonds) along timeline
- Entity nodes (circles/rounded squares) above/below timeline
- Connection lines between events and entities

**Interactions:**
- Scroll horizontally to navigate time
- Click event → opens Context Panel (§5.12)
- Drag to select time range → filters Intelligence Strip
- Toggle view modes: Timeline | Graph | Map

**Styling:**
- **Background:** `var(--color-bg-canvas)`
- **Timeline line:** `h-0.5 bg-slate-300`
- **Event markers:** `rounded-full px-2 py-1 text-xs font-medium`
- **Entity nodes:** `w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center`
- **Connection lines:** `stroke-1 stroke-slate-400`

**Responsive:**
- On mobile: vertical timeline instead of horizontal
- Touch-friendly event markers (`min-w-12 min-h-12`)

### 5.12. Context Panel (Right-Side Detail View)

**Trigger:** Clicking an event, entity, or lead in Focus Canvas or Intelligence Strip.

**Structure:**
- Slides in from right (320–400px width)
- Header: title + close button
- Sections:
  - Details (raw data, metadata)
  - AI Reasoning (why flagged, confidence, sources)
  - Related Items (linked events, entities)
  - Actions (tag, annotate, escalate, export)

**Behavior:**
- Overlay on mobile (full screen)
- Pushes content on desktop (no overlay)
- Dismissible via close button, Escape key, or clicking outside

**Styling:**
- **Background:** `var(--color-bg-card)`
- **Border-left:** `border-l border-slate-200`
- **Header:** `h-14 flex items-center justify-between px-4 border-b border-slate-200`
- **Sections:** `p-4 border-b border-slate-100`

### 5.13. Intelligence Strip

**Purpose:** Surface AI-driven insights, hypotheses, and gaps at the bottom of the dashboard.

**Structure:**
- Fixed-height strip (25–30% of viewport height)
- Tabbed navigation: Leads | Hypotheses | Gaps | Recent Activity
- Grid of compact cards within each tab

**Card Content (Leads):**
- Title (e.g., "Unusual login pattern for User X")
- Confidence score (badge)
- One-line summary
- "Open" button → loads Context Panel

**Behavior:**
- Collapsible (drag handle or toggle button)
- Scrollable internally (independent of Focus Canvas)
- Filters sync with Focus Canvas time selection

**Styling:**
- **Background:** `var(--color-bg-card)`
- **Top border:** `border-t border-slate-200`
- **Tabs:** `text-sm font-medium text-slate-500 hover:text-slate-700`
- **Active tab:** `text-blue-600 border-b-2 border-blue-600`
- **Card grid:** `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4`

### 5.14. Floating Action Orb

**Purpose:** Primary navigation control without permanent sidebar.

**Structure:**
- Default state: Small dot (`w-3 h-3 rounded-full bg-slate-400`)
- Active state: Radial menu with 6–8 items
- Position: Fixed, bottom-left of Focus Canvas (`bottom-8 left-8`)

**Menu Items:**
- New Case (`Plus` icon)
- New Query (`Search` icon)
- Board View (`Grid` icon)
- Reports (`FileText` icon)
- Settings (`Settings` icon)
- Help (`HelpCircle` icon)

**Styling:**
- **Orb:** `w-12 h-12 rounded-full bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center shadow-elevated`
- **Menu items:** `absolute w-10 h-10 rounded-full bg-white border border-slate-200 shadow-md flex items-center justify-center hover:bg-slate-50`
- **Animation:** Radial expansion with `transition-all duration-200`

### 5.15. Evidence Card

```tsx
// Used in Intelligence Strip or case views
// Shows: thumbnail, title, type badge, status badge, timestamp
<EvidenceCard
  thumbnail="/path/to/thumb.jpg"
  title="CCTV_lobby_2026-08-19.mp4"
  type="video"
  status="analyzing"
  timestamp="2026-08-19 14:32"
/>
```

- **Card:** `bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow`
- **Thumbnail:** `w-full h-32 object-cover`
- **Content:** `p-4`
- **Title:** `text-sm font-semibold text-slate-900 truncate`
- **Badges:** Flex row with `gap-2 mt-2`

***

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
| Context panel slide-in | `translate-x-full → translate-x-0` from right, 300ms ease-out |
| Context panel slide-out | `translate-x-0 → translate-x-full` 200ms ease-in |
| Dropzone drag-over | `border-blue-500 bg-blue-50 scale-[1.01] transition-all` |
| Modal open | `opacity-0 scale-95 → opacity-100 scale-100` 200ms ease-out |
| Orb menu expand | Radial animation with `transition-all duration-200` |
| Intelligence strip collapse | `height: 30% → height: 0` with `transition-height duration-300` |

***

## 7. Form Design Principles

- **Label above input always** — Never use placeholder-only labels (accessibility)
- **Helper text below inputs** — `text-xs text-slate-500 mt-1`
- **Error state:** `border-red-500` + red helper text + red icon
- **Required fields:** Asterisk `*` in `text-red-500` after label
- **Field height:** Minimum `h-11` for touch-friendliness (field-ready)
- **Disabled state:** `opacity-50 cursor-not-allowed`
- **Focus ring:** `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1`

***

## 8. Icon Library

Use **Lucide React** exclusively:

```bash
npm install lucide-react
```

**Standard sizes:**
- Navigation icons: `w-5 h-5`
- Inline/badge icons: `w-4 h-4`
- KPI card icons: `w-6 h-6`
- Empty state illustrations: `w-12 h-12 text-slate-300`

**Mandatory icon → use case mapping:**

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
| `Loader2` | Spinning loader (`animate-spin`) |
| `Eye` | View / inspect |
| `Upload` | Upload CTA |
| `Activity` | Live/real-time indicator |
| `Search` | Search inputs |
| `Filter` | Filter controls |
| `ChevronRight` | Breadcrumb separator / row arrow |
| `Plus` | New case / add action |
| `Grid` | Board view |
| `Settings` | Settings |
| `HelpCircle` | Help |
| `Briefcase` | Workspace selector |

***

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

***

## 10. Ethical Guardrail UI Rules (NON-NEGOTIABLE)

1. **REVIEW REQUIRED badge** (amber) must be shown for ANY evidence that was flagged by YOLOv8 or the texture classifier. It must never auto-clear without human confirmation.
3. **Hold Point steps** in the upload wizard must use `disabled={!accepted}` on the Next button. Never bypass with JavaScript trickery.
4. **Confidence scores** must always be displayed alongside detections (e.g., "Firearm — 84% confidence"). Never show a label without its confidence.
5. **Grad-CAM overlay** must default to OFF (`showHeatmap = false`) and require explicit toggle by the investigator.
6. **LLM citations** must be hyperlinks, not plain text. Clicking a citation must scroll/highlight the source evidence.
7. **No autonomous conclusions:** Any LLM-generated text that contains words like "guilty", "confirmed", "conclusive" must be caught and replaced with a warning banner.

***

## 11. Accessibility Standards

- All interactive elements must have `aria-label` or visible text labels
- Color alone must never convey status — always pair with icon or text
- Focus rings must be visible (never `outline-none` without a replacement)
- Minimum touch target: `44×44px` (h-11 minimum)
- Keyboard navigation must work for all modals, dropdowns, and forms
- `role="alert"` on all toast notifications
- **WCAG 2.1 AA compliance** for all color contrasts

***

## 12. Data Visualization Guidelines

### Color Usage

- **Do NOT reuse semantic status colors** for chart series.
- Use the **Data Visualization Palette** (§3) for entity types:
  - Person: `#3b82f6` (blue)
  - Device: `#10b981` (emerald)
  - Account: `#f59e0b` (amber)
  - Location: `#8b5cf6` (violet)
  - IP/Network: `#ec4899` (pink)

### Chart Styles

- Minimal grid lines (`stroke-slate-200`)
- No 3D effects or shadows
- Tooltips on hover with detailed info
- Consistent padding and font sizes
- Use `Geist` for all labels and values

### Network Graph

- **Nodes:** Circles with icon or initial (`w-10 h-10`)
- **Edges:** Thin lines (`stroke-1`), color-coded by relationship type
- **Zoom/pan controls:** Bottom-right corner
- **Legend:** Top-right, collapsible
- **Entity type colors:** Use Data Visualization Palette

### Timeline Visualization

- **Horizontal line:** `h-0.5 bg-slate-300`
- **Event markers:** Pill-shaped or diamond
- **Time labels:** Below timeline, `font-mono text-xs text-slate-500`
- **Selection range:** Highlighted background (`bg-blue-50`)

***

## 13. Component File Structure Convention

```
frontend/src/
├── components/
│   ├── layout/
│   │   ├── AppLayout.tsx          ← Root shell (Investigation Hub)
│   │   ├── GlobalContextBar.tsx   ← Top bar with search + workspace
│   │   ├── FocusCanvas.tsx        ← Timeline + graph hybrid
│   │   ├── IntelligenceStrip.tsx  ← Bottom AI insights panel
│   │   └── FloatingActionOrb.tsx  ← Radial navigation menu
│   ├── ui/
│   │   ├── Badge.tsx              ← Status pill badges
│   │   ├── Button.tsx             ← Primary, secondary, destructive variants
│   │   ├── Card.tsx               ← Base card container
│   │   ├── KpiCard.tsx            ← Stats card with icon + trend
│   │   ├── Modal.tsx              ← Accessible modal/dialog
│   │   ├── StatusToast.tsx        ← Socket.io processing toasts
│   │   ├── Toggle.tsx             ← On/off toggle (Grad-CAM etc.)
│   │   ├── Spinner.tsx            ← Loading indicator
│   │   └── EvidenceCard.tsx       ← Evidence preview card
│   ├── evidence/
│   │   ├── EvidenceUploadWizard.tsx
│   │   ├── EvidenceCard.tsx
│   │   └── EvidenceTable.tsx
│   ├── ai/
│   │   ├── DetectionBadge.tsx       ← YOLOv8 detection pill
│   │   ├── GradCamToggle.tsx
│   │   └── AuditTimeline.tsx
│   └── visualization/
│       ├── TimelineView.tsx         ← Horizontal timeline component
│       ├── GraphView.tsx            ← Network graph component
│       ├── EntityNode.tsx           ← Graph node component
│       └── EventMarker.tsx          ← Timeline event marker
├── pages/
│   ├── Dashboard.tsx                ← Investigation Hub layout
│   ├── Cases.tsx
│   ├── CaseDetail.tsx
│   └── EvidenceViewer.tsx           ← Split-pane workspace
├── store/
│   ├── caseStore.ts
│   ├── evidenceStore.ts
│   └── socketStore.ts
└── services/
    ├── api.ts
    └── socket.ts
```

***

## 14. Do's and Don'ts

### ✅ DO

- Use `Geist` for all text, `Geist Mono` for IDs and data
- Use semantic status colors strictly as defined in §3
- Always show confidence % alongside AI detections
- Keep buttons large (h-11 minimum)
- Add `transition-*` classes to all interactive elements
- Use `rounded-xl` for cards, `rounded-lg` for inputs, `rounded-full` for badges
- Use the Investigation Hub layout as the default (not sidebar + cards)
- Use progressive disclosure to reduce cognitive load
- Test all components in both light and dark themes

### ❌ DON'T

- Don't use Tailwind arbitrary values like `text-[13px]` — stick to the scale
- Don't use red for anything other than critical errors or destructive actions
- Don't use green for anything other than successfully completed processing
- Don't add decorative gradients to functional UI elements
- Don't auto-confirm Hold Point steps programmatically
- Don't use `outline-none` without a focus ring replacement
- Don't commit `node_modules/`, `.venv/`, or `backend/storage/*` to git
- Don't use Google Fonts for Geist (use Fontsource CDN or self-host)
- Don't revert to sidebar + cards layout without explicit instruction

***

## 15. Version History

| Version | Date       | Changes                          | Author |
|---------|------------|----------------------------------|--------|
| 1.0     | 2026-08-XX | Initial draft                    |        |
| 1.1     | 2026-08-22 | Added SiteAssist references      |        |
| 1.2     | 2026-08-22 | Complete rewrite: Investigation Hub layout, Focus Canvas, Intelligence Strip, Floating Action Orb, dark theme tokens, data visualization palette, Geist font CDN fix |        |

***

## 16. Implementation Notes

### Font Loading Strategy

```html
<!-- In index.html <head> -->
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link href="https://cdn.jsdelivr.net/npm/geist@1.0.0/dist/geist.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/geist@1.0.0/dist/geist-mono.css" rel="stylesheet>

<!-- Or via npm (recommended for production) -->
<!-- npm install geist -->
<!-- Then import in index.css: -->
<!-- @import 'geist/dist/geist.css'; -->
<!-- @import 'geist/dist/geist-mono.css'; -->
```

### Theme Switching

```tsx
// In root component
useEffect(() => {
  const theme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', theme);
}, []);

// Toggle function
const toggleTheme = () => {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
};
```

### Responsive Container

```css
.container-investigation {
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 clamp(1rem, 5vw, 2rem);
}
```

***

**End of Document**

This is the complete, updated UI/UX Master Guidelines for ForenSight AI. All future design and development work must comply with this specification.