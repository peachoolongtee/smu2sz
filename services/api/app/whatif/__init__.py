"""What-if sandbox (display-only). The owner moves sliders; the real verifier evaluates a synthetic,
typed package; the result is a server-formatted view labelled hypothetical.

It never executes an operation, never writes state and never reads free text (INVARIANTS 1, 2, 13).

Public interface: `simulate()` (-> WhatIfResult), `presets()`, `WhatIfParams`, `WhatIfParamError`,
`PRESETS`, `clear_cache()`.
"""

from app.whatif.params import PRESETS, WhatIfParamError, WhatIfParams
from app.whatif.simulate import WhatIfResult, clear_cache, presets, simulate

__all__ = ["PRESETS", "WhatIfParamError", "WhatIfParams", "WhatIfResult", "clear_cache", "presets", "simulate"]
