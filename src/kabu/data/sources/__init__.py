"""Vendor-specific Source implementations.

Each module in this package adapts a single vendor SDK / API into the
``kabu.data.Source`` Protocol. The vendor SDK MUST NOT be imported
anywhere in ``src/kabu/`` outside this directory; ``test_vendor_layer_isolation``
checks that invariant.

P4.7 ships only the ``yfinance`` adapter.

Vendor adapters use a *lazy* import strategy: the SDK is imported inside
the default factory function, so unit tests can inject a fake
``history_fn`` and never touch the real package. This keeps CI free of
external network dependencies and lets the project be installed without
any vendor extra.
"""

from kabu.data.sources.yfinance_source import (
    YFinanceSource,
    yfinance_row_to_ohlcbar,
)

__all__ = ["YFinanceSource", "yfinance_row_to_ohlcbar"]
