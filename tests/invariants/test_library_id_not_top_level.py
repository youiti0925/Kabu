"""Invariant: top-level library_id is deprecated; live in slice + run_metadata.

Policy: SCHEMA.md S0 D-12 / D-13.
"""

from __future__ import annotations

import warnings

import pytest

from kabu.decision_trace import LibraryRef
from kabu.trace_io import trace_from_dict, trace_to_dict

from tests.decision_trace._fixtures import make_trace


def test_writer_does_not_emit_top_level_library_id():
    d = trace_to_dict(make_trace())
    assert "library_id" not in d


def test_reader_warns_and_drops_top_level_library_id():
    d = trace_to_dict(make_trace())
    d["library_id"] = "legacy_top_level_lib_v1"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        rt = trace_from_dict(d)
        deprecations = [item for item in w if issubclass(item.category, DeprecationWarning)]
        assert deprecations, "expected DeprecationWarning for top-level library_id"
        assert "library_id" in str(deprecations[0].message)
    # The reconstructed trace does not carry a top-level library_id.
    assert not hasattr(rt, "library_id")


def test_library_ref_dataclass_requires_all_fields():
    with pytest.raises(ValueError):
        LibraryRef(slice="", library_id="L1", library_kind="global", feature_set="v1")
    with pytest.raises(ValueError):
        LibraryRef(slice="waveform_ctx", library_id="", library_kind="global", feature_set="v1")
    with pytest.raises(ValueError):
        LibraryRef(slice="waveform_ctx", library_id="L1", library_kind="", feature_set="v1")
    with pytest.raises(ValueError):
        LibraryRef(slice="waveform_ctx", library_id="L1", library_kind="global", feature_set="")


def test_library_ref_valid():
    ref = LibraryRef(
        slice="waveform_ctx",
        library_id="wf_lib_v1",
        library_kind="global",
        feature_set="v1_5bar_logret",
    )
    assert ref.slice == "waveform_ctx"
    assert ref.library_id == "wf_lib_v1"
