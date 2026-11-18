# DESIGN.md — Studio UI Design Tokens & Layout Specification (Grainrad Mono, r2)

**Phase:** 02 — Studio UI/UX Redesign & Client Shader Pipeline
**Plan:** 02-01 (Stitch MCP prototypes + token spec)
**Round:** 2 — monochrome "Grainrad" redesign (round 1 phosphor system `assets/df6f50a9fc4440308f061263195e879a` retired; left untouched in Stitch)
**Source prototypes:** Stitch project `13429898272245688948` — "RGB ASCII & Retro FX Studio" (DESKTOP)
**Design system:** "Grainrad Mono Studio" (`assets/15749583180289410834`)
**Mockups:** `prototypes/02-01-studio-standby.png` (blank slate) · `prototypes/02-01-studio-active-media.png` (media loaded, RGB ASCII canvas output)
**Design authority:** measured from grainrad.com. The UI is a quiet greyscale instrument; all color lives in the canvas artwork only.

---

## 1. Layout: Three-Column Studio Shell (D-03 — kept)

The Studio is a fixed three-column workspace. No page scroll — only the Center Stage content area scrolls/zooms internally. The three-column shell, drag-drop interaction, and effect tile grid are carried over from round 1 unchanged.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Titlebar (24px): route mark · app name · project status pill        │
├───────────────┬──────────────────────────────────┬───────────────────┤
│               │                                  │                   │
│  Left Rail    │           Center Stage           │    Right Rail     │
│  (240px)      │   (flex-1, media viewport)       │    (280px)        │
│               │                                  │                   │
│  Source input │   Canvas (black; artwork only    │  Inspector        │
│  Pipeline     │   source of color)               │  (stacked groups: │
│  mode tiles   │                                  │  pre-tone, ascii  │
│  Macro        │   [Dropzone overlay when empty]  │  params, emission,│
│  presets      │                                  │  export)          │
│               │                                  │                   │
├───────────────┴──────────────────────────────────┴───────────────────┤
│  Statusbar (24px): mem · vram · zoom · channel keys · profile        │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.1 Left Rail — Source & Pipeline (240px fixed)

- **Role:** source input + pipeline mode selection. Sections: `source input` (drop card, file/url/cam buttons), `pipeline mode` (16 effect tiles in 2 columns), `macro presets` (bank row: `terminal p01`, `pure matrix p02`, `gameboy 2b p03`, `aperture p04`).
- Section headers: `− section name` (dash glyph) left, count/state right-aligned.
- Effect tiles: full-width cells, 24px-minimum height, glyph-state prefix (`● ascii` active, `○ dither` idle), 12px mono text, no borders — active tile distinguished by raised background `--bg-active` only.
- The whole rail and Center Stage accept drag-drop (D-04, kept).

### 1.2 Center Stage — Media Viewport (flex)

- **Role:** the canvas. Contains the live RGB ASCII preview render (render pipeline itself lands in Plan 02-02).
- **Blank-slate state (standby mockup):** centered empty-state — dashed 1px hairline frame, `+` affordance, copy "drop image or video / or browse" in `--text-default`, secondary hint line in `--text-dim`. **CRT scanline texture is allowed in this empty standby state only.**
- **Active state:** media/canvas fills the stage; artwork (including the RGB ASCII output) is the ONLY place color may appear. Zoom control row pinned bottom-center (`− 100% + reset 16:9 r g b snap`), `r`/`g`/`b` are channel key buttons.
- Drag-drop overlay: full-stage dim tint `--overlay-drag: rgba(10,10,10,0.6)` + hairline highlight while dragging over (D-04). No colored tint.

### 1.3 Right Rail — Inspector (280px fixed)

- **Role:** parameter controls for the active FX chain (STUDIO-01, kept).
- Panel groups (top to bottom, multiple stacked groups with 1px hairline separators): `pre-tone` (brightness/contrast/saturation/gamma sliders + reset), `ascii params` (cell size, aspect ratio, glyph ramp dropdown, invert luminance toggle), `emission model` (segmented: `mono 01 / mono 02 / mono 03`), `export / dispatch` (export png frame row + jpeg/svg/txt/gif grid + record stream row).
- Group headers: `− group name` left, state/reset right.
- Every control row: label left (12px mono, lowercase), value right-aligned (tabular numbers, `--text-highlight`). Slider row beneath: 1px hairline track, small square thumb, no fill color.
- Tabs at rail top: `− inspector` (active, raised bg) / `export` (idle).

### 1.4 Chrome

- **Titlebar (24px):** left — route mark (`rgb://fx / grainrad v1.4.2 [gpu]`); center — project name + status pill (`untitled studio | ● synced`); right — fps readout, backend tag (`webgpu`), window glyphs, user tag. All 12px mono, dim; the synced dot is the only bright accent in chrome (a filled ● in `--text-highlight`).
- **Statusbar (24px):** left — `mem 482mb`, `vram 1.2gb`; right — `profile  rec.709 linear`. Mono 12px, dim text. No icons, no color.

---

## 2. Design Tokens

The full token sheet below is the contract the client implementation consumes. Tokens are CSS custom properties; do not hardcode raw values in components. All values measured from grainrad.com.

### 2.1 Color — pure greyscale

| Token | Value | Use |
|---|---|---|
| `--bg-base` | `#0a0a0a` | App background, canvas, statusbar |
| `--bg-active` | `#0f0f0f` | Active tile, active tab, focused row |
| `--bg-raised` | `#151515` | Panels, buttons at rest, controls |
| `--border-hairline` | `#222222` | 1px hairlines, separators, dashed dropzone frame |
| `--text-dim` | `#555555` | Placeholder, disabled, secondary hints |
| `--text-default` | `#888888` | Labels, body text, chrome |
| `--text-highlight` | `#cccccc` | Values, active labels, primary copy |
| `--text-max` | `#ffffff` | Sparing only (e.g. active value digits) |
| `--overlay-drag` | `rgba(10,10,10,0.6)` | Drag-over stage dim tint (D-04) |
| `--overlay-scrim` | `rgba(0,0,0,0.55)` | Modal/scrim |

**Prohibited in UI chrome:** phosphor green, amber, magenta, cyan, any hue. No glow, no colored borders, no colored focus rings, no channel-colored accents in chrome. Depth and state are expressed by background contrast and glyph states only.

**Exception — canvas content:** the artwork rendered on Center Stage (source media, RGB ASCII output) MAY contain color. This is content, not chrome.

### 2.2 Typography — IBM Plex Mono only

| Token | Value |
|---|---|
| `--font-mono` | `"IBM Plex Mono", ui-monospace, Consolas, monospace` |
| `--text-base` | 16px / 400 / mono — the one base size |
| `--text-control` | 12px / 400 / mono — labels, buttons, tiles, chrome |
| `--text-value` | 12px / 400 / mono / `font-variant-numeric: tabular-nums` — right-aligned values |

**Rules:** no bold for hierarchy (400 everywhere; weight never encodes importance), no italic, no text-transform (everything lowercase), no letter-spacing adjustments, no non-mono typeface anywhere. Hierarchy comes from size (16 vs 12) and color step (`--text-default` vs `--text-highlight`).

### 2.3 Spacing & Radius — 4px grid, square corners

| Token | Value | Use |
|---|---|---|
| `--space-1` | 4px | Tight control internals |
| `--space-2` | 8px | Horizontal control padding, group gaps |
| `--space-3` | 12px | Vertical padding, list row spacing |
| `--space-4` | 16px | Rail/panel padding |
| `--radius` | **0** | Everything. No rounded corners anywhere in chrome. |

### 2.4 Borders, Elevation, Effects

- **No visible control borders.** Controls (buttons, tiles, rows) are distinguished purely by background steps: `--bg-base` → `--bg-raised` (rest) → `--bg-active` (active/hover/focus). Hairlines (`--border-hairline`, 1px) exist only as section separators and the dashed empty-state frame.
- **No shadows.** Depth via background contrast only.
- **No glow.** `text-shadow`, `box-shadow` glow, phosphor bloom — none in chrome.
- `--scanline: repeating-linear-gradient(0deg, rgba(255,255,255,0.02) 0 1px, transparent 1px 3px)` — CRT texture, **empty standby state only**, `pointer-events: none`. Never on panels, controls, or populated canvas.
- `:focus-visible` → background step to `--bg-active` (no outline ring, no color).

### 2.5 Motion

| Token | Value | Use |
|---|---|---|
| `--dur-fast` | 100ms | Hover/focus background step |
| `--dur-med` | 160ms | Panel expand, state flips |
| `--ease` | `cubic-bezier(0.2, 0, 0, 1)` | All transitions |

---

## 3. Component Guidelines (Inspector controls per STUDIO-01)

- **Control geometry (all interactive chrome):** 24px height, `6px 8px` padding, 12px mono text, radius 0, no visible border. Rest = `--bg-raised`; hover/focus/active = `--bg-active`.
- **Slider:** 1px hairline track, small (8px) square thumb, no color fill. Label left, value right in tabular mono; double-click value → inline edit.
- **Segmented toggle / mode tiles:** equal-width cells, glyph-state prefix — `●` active, `○` idle — followed by lowercase label. Active cell gets `--bg-active` + `--text-highlight`; no color, no border change.
- **Dropdown:** mono list, keyboard navigable, chevron at row end; selected row `--bg-active`.
- **Toggle (`invert luminance`):** compact right-aligned pill, `● on` / `○ off` glyph state.
- **Accordion/stacked groups:** header row (`− group` + state right), 1px hairline separator between groups; groups stay visible (no accordion collapse needed in v1).
- **Dropzone card (D-04):** dashed 1px `--border-hairline` frame, `+` glyph, centered mono copy in `--text-default`/`--text-dim`. On drag-over: stage dims via `--overlay-drag`, frame steps to solid hairline. No green.
- **Macro preset row:** label + bank tag (`terminal p01`), rest = `--bg-raised`.
- **Export grid:** 2-column button grid (`jpeg 95%` / `vector svg` / `raw txt` / `anim gif`), full-width primary row (`export png frame` with right-aligned `1920x1080`).

---

## 4. Responsive / Container Queries

- Studio shell uses container queries, not viewport media queries, so the app behaves the same embedded or full-window:
  - `@container (max-width: 1100px)` → Left Rail collapses to 48px icon/glyph column; inspector remains.
  - `@container (max-width: 800px)` → Right Rail becomes a bottom sheet-style overlay, toggled from the statusbar.
- Center Stage canvas scales with `aspect-ratio` preserved; letterboxed by `--bg-base`.

---

## 5. Prototype Cross-Reference (r2)

| State | Screen ID | Screenshot | Notes |
|---|---|---|---|
| Standby (blank slate) | `1413dc7c5bce4a51b610710f5b31ee09` | `prototypes/02-01-studio-standby.png` | Dropzone, 16 mode tiles, macro presets, inspector defaults; scanlines in empty stage only |
| Active media (RGB ASCII output) | `3a0e2c0aff1b44fcacb6e4d44c925c26` | `prototypes/02-01-studio-active-media.png` | Populated library + inspector; color ONLY in canvas artwork |

Machine-readable identifiers: `stitch-prototypes.json` (same directory).
