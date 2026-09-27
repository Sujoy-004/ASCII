"""Milestone 7: optional temporal smoothing across displayed frames.

M6 decides *which* video frame to display next; M7 decides how the transition
toward that displayed frame is rendered, with the goal of reducing flicker,
color instability, and harsh jumps between consecutive DISPLAYED frames.

This is VISUAL SMOOTHING only -- it is explicitly NOT motion interpolation,
optical flow, motion estimation, or frame generation. No new frame that never
existed is invented; the smoothed value is a single blend of the previous
*discarded-then-displayed* state and the newly selected source frame.

Representation
--------------
Smoothing is performed on the compact RGB24 numeric representation (one
byte per channel), i.e. the raw frame bytes. This is preferred over:

 - smoothing the final ANSI string (never blend escape codes as text), and
 - smoothing only luminance/ASCII.

Because the renderer derives luminance from RGB (Rec. 601) and selects the
ASCII character from that luminance, smoothing RGB also smooths the luminance
used for character selection, addressing both color flicker and ASCII
character flicker with a single numeric representation.

Consistency with dropped frames
-------------------------------
The smoother only ever sees frames that were actually SELECTED for display
(i.e. passed through from FrameSelector). Decoded-but-dropped frames never
reach it, so they can never contaminate the smoothing history. The retained
state is always the previous *displayed* frame.

Alpha semantics (new-frame contribution)
----------------------------------------
    smoothed = previous * (1 - alpha) + current * alpha

 - alpha == 1.0 -> current frame immediately (no smoothing)
 - alpha == 0.0 -> previous frame forever (after initialization)
 - 0 < alpha < 1 -> exponential blend toward the current frame

Config default is 0.0 => smoothing disabled (pass-through), so the pre-M7
renderer output is preserved exactly. Smoothing is opt-in.
"""

from __future__ import annotations

from src.config import Config


class TemporalSmoother:
    """Blends consecutive displayed frames toward the current one.

    Retains at most one previous-displayed numeric frame state (bounded -- no
    growing history). ``smooth()`` returns the frame bytes to render.

    Two independent axes (the config's ``smoothing`` is both, unless overridden
    in tests):

    - enabled: smoothing is on/off. Disabled => pass-through of the input.
      By default this is ``config.smoothing > 0`` (so the default 0.0 disables
      smoothing and preserves the pre-M7 renderer exactly).
    - alpha: the new-frame contribution used by the blend, = config.smoothing.
    """

    def __init__(self, config: Config, enabled: bool | None = None) -> None:
        self.config = config
        # New-frame contribution; blend is prev*(1-a) + cur*a. Clamped to [0,1]
        # so out-of-range CLI values can never produce out-of-range bytes.
        self.alpha: float = min(1.0, max(0.0, config.smoothing))
        self.enabled: bool = (
            config.smoothing > 0.0 if enabled is None else enabled
        )
        self._prev: bytearray | None = None
        self.smoothed_frames: int = 0
        # Precomputed 256x256 blend table: entry [prev*256 + cur] ==
        # round(prev*(1-a) + cur*a), so the per-byte hot loop is a single
        # table lookup instead of per-pixel float math. This is byte-identical
        # to the naive formula. Built only when enabled.
        self._blend_table: bytes | None = None
        # The same table sliced into 256 rows, so the hot loop indexes it as
        # ``rows[prev_byte][cur_byte]`` instead of computing ``prev << 8 | cur``
        # itself. The rows are slices (copies) taken from the single table at
        # construction, so they cannot disagree with it, and the row lookup
        # replaces a shift, an OR and a bounds-checked flat index with two
        # plain sequence indexes inside a list comprehension.
        self._blend_rows: tuple[bytes, ...] = ()
        if self.enabled:
            table = bytearray(256 * 256)
            one_minus = 1.0 - self.alpha
            a = self.alpha
            for p in range(256):
                base = p * 256
                for c in range(256):
                    table[base + c] = int(p * one_minus + c * a + 0.5)
            self._blend_table = bytes(table)
            self._blend_rows = tuple(
                self._blend_table[p * 256:(p + 1) * 256] for p in range(256)
            )

    def smooth(self, frame: bytes) -> bytes:
        """Return the frame to display, blended toward the previous display.

        - Disabled: pass-through, identical to the pre-M7 renderer input.
        - First displayed frame: initialize the retained state directly with
          no blend against black (avoids a fade-in artifact).
        - Otherwise: ``prev*(1-alpha) + current*alpha`` per channel byte.
        """
        if not self.enabled:
            # Disabled means no retained history: drop it, so a later re-enable
            # (the adaptive quality controller shedding load and then
            # recovering) blends against the frame actually being displayed
            # instead of a stale pre-downgrade ghost, and so the next
            # initialization is a direct copy rather than a blend.
            self._prev = None
            return frame
        if self._prev is None:
            self._prev = bytearray(frame)
            return frame
        return self._blend(self._prev, frame)

    def _blend(self, prev: bytearray, frame: bytes) -> bytes:
        rows = self._blend_rows
        # One bounded pass over the RGB channel bytes; each output byte is a
        # single row-then-column lookup into the precomputed 256x256 blend
        # table (no NumPy, no float math). ``zip`` drives the walk and
        # ``bytes(bytearray(...))`` materialises it in one C-level pass.
        out = bytes(bytearray([rows[p][c] for p, c in zip(prev, frame)]))
        self._prev = bytearray(out)
        self.smoothed_frames += 1
        return out
