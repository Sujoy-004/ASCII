# DESIGN.md — Studio UI Design Tokens & Layout Specification

**Phase:** 02 — Studio UI/UX Redesign & Client Shader Pipeline
**Plan:** 02-01 (Stitch MCP prototypes + token spec)
**Source prototypes:** Stitch project `13429898272245688948` — "RGB ASCII & Retro FX Studio" (DESKTOP)
**Design system:** "Cathode Retro FX Studio" (`assets/df6f50a9fc4440308f061263195e879a`)
**Mockups:** `prototypes/02-01-studio-standby.png` (blank slate) · `prototypes/02-01-studio-active-media.png` (Sunset.png loaded)

---

## 1. Layout: Three-Column Studio Shell (D-03)

The Studio is a fixed three-column workspace. No page scroll — only the Center Stage content area scrolls/zooms internally.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Titlebar (28px): app mark · file name · project mode pill           │
├───────────────┬──────────────────────────────────┬───────────────────┤
│               │                                  │                   │
│  Left Rail    │           Center Stage           │    Right Rail     │
│  (240px)      │   (flex-1, media viewport)       │    (280px)        │
│               │                                  │                   │
│  Media        │   Canvas with checkerboard       │  Inspector        │
│  library      │   backing + live RGB ASCII       │  (stacked panel   │
│  Import       │   preview render                 │   groups)         │
│  Presets      │                                  │                   │
│               │   [Dropzone overlay when empty]  │                   │
├───────────────┴──────────────────────────────────┴───────────────────┤
│  Statusbar (24px): FPS · resolution · active FX chain · export state │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.1 Left Rail — Media Library (240px fixed)

- **Role:** source of truth for assets. Sections: `Library`, `Import`, `Presets`.
- Library rows: 32px thumbnail, filename (mono, 12px), size/format chip.
- Import row is a persistent "+ Import" affordance AND the whole rail accepts drag-drop (D-04).
- Presets list: saved FX chains, one-line summaries, star toggle.
- Collapse affordance: rail collapses to 48px icon column on narrow viewports (container query, §4).

### 1.2 Center Stage — Media Viewport (flex)

- **Role:** the canvas. Contains the live RGB ASCII preview render (phased into Task/Plan 02-02).
- **Blank-slate state (standby mockup):** centered dropzone card — dashed 1px border, phosphor-green on hover, copy "Drop image or video / or browse", subtle CRT scanline texture in the empty state only.
- **Active state:** checkerboard backing behind the media, render fills stage with 8px padding, zoom % indicator bottom-right.
- Drag-drop overlay: full-stage tint `--overlay-drag: rgba(51,255,102,0.06)` + border highlight while dragging over (D-04).

### 1.3 Right Rail — Inspector (280px fixed)

- **Role:** parameter controls for the active FX chain (per STUDIO-01: inspector with live parameter controls).
- Panel groups (accordions, one open at a time): `Source`, `ASCII`, `Color`, `Effects`, `Export`.
- Control set: sliders (with mono numeric readouts), segmented toggles, color swatches, dropdowns.
- Every control label 11px uppercase; value column right-aligned, tabular numbers.
- Reset-per-group icon; "Randomize" global button in the panel header (fits the fun/dev-toy tone).

### 1.4 Chrome

- **Titlebar (28px):** left — logo mark + "RGB ASCII Studio"; center — active file name; right — mode pill (`Text` / `Image` / `Video`) and command-palette hint (⌘K).
- **Statusbar (24px):** FPS readout, source resolution, grid size, active FX chain summary, export/encode state. Mono 11px, dim text.

---

## 2. Design Tokens

The full token sheet below is the contract the client implementation consumes. Tokens are CSS custom properties; do not hardcode raw values in components.

### 2.1 Color

| Token | Value | Use |
|---|---|---|
| `--bg-base` | `#0d0f12` | App background, rails, chrome |
| `--bg-panel` | `#12151a` | Raised panels, inspector cards |
| `--bg-input` | `#0a0c0f` | Inputs, sliders, code-ish fields |
| `--border-1` | `#26292e` | 1px hairlines, panel separators |
| `--border-2` | `#34383e` | Hover borders, focused control edges |
| `--text-primary` | `#e8eaed` | Headings, filenames, values |
| `--text-secondary` | `#9aa0a8` | Labels, secondary copy |
| `--text-dim` | `#5c6167` | Placeholder, disabled, statusbar |
| `--accent-phosphor` | `#33ff66` | Primary accent — active states, dropzone, focus rings, R channel |
| `--accent-amber` | `#ffb000` | Secondary accent — G channel highlight, warnings, record state |
| `--accent-cyan` | `#4dd0e1` | B channel highlight, info chips |
| `--accent-danger` | `#ff5252` | Destructive, error states |
| `--overlay-drag` | `rgba(51,255,102,0.06)` | Drag-over stage tint (D-04) |
| `--overlay-scrim` | `rgba(0,0,0,0.55)` | Modal/scrim |

Channel semantics: phosphor green / amber / cyan map to the RGB channels of the ASCII renderer — use them consistently when visualizing channel splits.

### 2.2 Typography

| Token | Value |
|---|---|
| `--font-mono` | `"JetBrains Mono", ui-monospace, "Cascadia Code", Consolas, monospace` |
| `--font-ui` | `"Inter", system-ui, sans-serif` (labels only; everything else mono) |
| `--text-title` | 15px / 600 / mono |
| `--text-body` | 13px / 400 / mono |
| `--text-label` | 11px / 500 / uppercase / letter-spacing 0.06em |
| `--text-micro` | 10px / 400 / statusbar & badges |

### 2.3 Spacing & Radius

| Token | Value | Use |
|---|---|---|
| `--space-1` | 4px | Tight control internals |
| `--space-2` | 8px | Control gaps, list padding |
| `--space-3` | 12px | Panel padding, group gaps |
| `--space-4` | 16px | Rail padding, section spacing |
| `--space-6` | 24px | Stage padding, empty-state spacing |
| `--radius-sm` | 2px | Chips, inputs |
| `--radius-md` | 4px | Buttons, thumbnails |
| `--radius-lg` | 8px | Dropzone card, modals |

### 2.4 Borders, Elevation, Effects

- **Hairline rule:** ALL separation is 1px `--border-1`. No drop shadows between panels — depth comes from background contrast (`--bg-panel` vs `--bg-base`), not shadow.
- `--shadow-raised: 0 4px 16px rgba(0,0,0,0.5)` — modals only.
- `--scanline: repeating-linear-gradient(0deg, rgba(255,255,255,0.02) 0 1px, transparent 1px 3px)` — decorative CRT texture, empty states & preview frame only, `pointer-events: none`.
- `--focus-ring: 0 0 0 1px var(--accent-phosphor)` — replaces browser outlines on all interactive elements (keep `:focus-visible` semantics).

### 2.5 Motion

| Token | Value | Use |
|---|---|---|
| `--dur-fast` | 120ms | Hover/focus, control state |
| `--dur-med` | 200ms | Panel expand, rail collapse |
| `--ease` | `cubic-bezier(0.2, 0, 0, 1)` | All transitions |

---

## 3. Component Guidelines (Inspector controls per STUDIO-01)

- **Slider:** 2px track `--bg-input` with `--border-1`, filled portion phosphor green, 12px square thumb (mono aesthetic), value readout right-aligned in tabular mono. Double-click value → inline edit.
- **Segmented toggle:** equal-width cells, 1px separators, active cell `--bg-input` + phosphor text.
- **Dropdown:** mono list, keyboard navigable, active row phosphor text.
- **Swatch row (channel colors):** square swatches with 1px border; selected swatch gets `--focus-ring`.
- **Accordion group:** header row (label + chevron), 1px divider, 12px group padding; only one open at a time.
- **Dropzone card (D-04):** 8px-radius card, dashed 1px `--border-2`, phosphor border + tint on hover/drag-over, centered mono copy, entire Center Stage is also a drop target.
- **Library row:** 32px thumb (checkerboard backing for transparent assets), name truncated, format chip in `--text-dim`.

---

## 4. Responsive / Container Queries

- Studio shell uses container queries, not viewport media queries, so the app behaves the same embedded or full-window:
  - `@container (max-width: 1100px)` → Left Rail collapses to 48px icon rail; inspector remains.
  - `@container (max-width: 800px)` → Right Rail becomes a bottom sheet-style overlay, toggled from the statusbar.
- Center Stage canvas scales with `aspect-ratio` preserved; letterboxed by `--bg-base`.

---

## 5. Prototype Cross-Reference

| State | Screen ID | Screenshot | Notes |
|---|---|---|---|
| Standby (blank slate) | `bd8d6a99afa84db6a886f4582c52053b` | `prototypes/02-01-studio-standby.png` | Dropzone, empty library, default inspector |
| Active media (Sunset.png) | `1ecf3101e2a940a19f3a1cd0a30a2d18` | `prototypes/02-01-studio-active-media.png` | Canvas render, populated inspector + library |

Machine-readable identifiers: `stitch-prototypes.json` (same directory).
