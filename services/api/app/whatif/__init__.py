"""What-if sandbox (display-only). The owner moves sliders; the real verifier evaluates a synthetic,
typed package; the result is a server-formatted view labelled hypothetical.

It never executes an operation, never writes state and never reads free text (INVARIANTS 1, 2, 13).

Public interface: `simulate()` (-> WhatIfResult), `presets()`, `WhatIfParams`, `WhatIfParamError`,
`PRESETS`, `clear_cache()`.
"""

from app.whatif.params import PRESETS, WhatIfParamError, WhatIfParams, WhatIfRequest
from app.whatif.simulate import WhatIfResult, clear_cache, presets, resolve, simulate

__all__ = ["PRESETS", "WhatIfParamError", "WhatIfParams", "WhatIfRequest", "WhatIfResult", "clear_cache", "presets", "resolve", "simulate"]
