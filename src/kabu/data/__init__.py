"""Data access layer for Kabu.

Exposes the `Source` Protocol (DATA_SOURCES.md S0 D-3..D-5) and the
`OHLCBar` value type. Concrete vendor implementations live behind the
Protocol; callers must not import vendor modules directly.

P1 scope: Protocol + a single in-memory reference implementation.
No external data fetching. No vendor SDK is wired in.
"""

from kabu.data.source import OHLCBar, Source
from kabu.data.inmemory import InMemorySource

__all__ = ["OHLCBar", "Source", "InMemorySource"]
