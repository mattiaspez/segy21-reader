"""Unit tests for the SEG-Y reader (Rev 1.0, 2.0, 2.1)."""

import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from segy21 import SegyReader
from tests.make_synthetic import write_segy


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

def _make_files(tmp_path_factory, revision: tuple, tag: str) -> dict:
    base = tmp_path_factory.mktemp(f"segy_{tag}")
    files = {}
    for fmt_code, suffix in [(5, "ieee"), (1, "ibm"), (2, "int32"), (3, "int16")]:
        p = base / f"synth_{suffix}.segy"
        write_segy(p, data_fmt=fmt_code, n_traces=10, n_samples=100, revision=revision)
        files[suffix] = p
    return files


@pytest.fixture(scope="session", autouse=True)
def synthetic_files(tmp_path_factory):
    """Generate Rev 2.1 synthetic SEG-Y files (default fixture used by most tests)."""
    files = _make_files(tmp_path_factory, revision=(2, 1), tag="rev21")
    synthetic_files.paths = files
    return files


@pytest.fixture(scope="session")
def rev1_files(tmp_path_factory):
    files = _make_files(tmp_path_factory, revision=(1, 0), tag="rev1")
    rev1_files.paths = files
    return files


@pytest.fixture(scope="session")
def rev20_files(tmp_path_factory):
    files = _make_files(tmp_path_factory, revision=(2, 0), tag="rev20")
    rev20_files.paths = files
    return files


def get_path(suffix: str) -> Path:
    return synthetic_files.paths[suffix]


# ------------------------------------------------------------------ #
# Textual header
# ------------------------------------------------------------------ #

class TestTextualHeader:
    def test_encoding_detected(self):
        with SegyReader(get_path("ieee")) as r:
            assert r.textual_header.encoding in ("ascii", "utf-8", "ebcdic")

    def test_40_lines(self):
        with SegyReader(get_path("ieee")) as r:
            lines = r.textual_header.lines()
            assert len(lines) == 40

    def test_line_length(self):
        with SegyReader(get_path("ieee")) as r:
            for line in r.textual_header.lines():
                assert len(line) == 80

    def test_content(self):
        with SegyReader(get_path("ieee")) as r:
            text = r.textual_header.text
            assert "SEG-Y 2.1" in text


# ------------------------------------------------------------------ #
# Binary file header
# ------------------------------------------------------------------ #

class TestBinaryHeader:
    def test_revision(self):
        with SegyReader(get_path("ieee")) as r:
            bh = r.binary_header
            assert bh.segy_revision_major == 2
            assert bh.segy_revision_minor == 1
            assert bh.segy_revision == "2.1"

    def test_samples_per_trace(self):
        with SegyReader(get_path("ieee")) as r:
            assert r.binary_header.effective_samples_per_trace == 100

    def test_sample_interval(self):
        with SegyReader(get_path("ieee")) as r:
            assert r.binary_header.effective_sample_interval_us == 2000.0

    def test_data_format_ieee(self):
        with SegyReader(get_path("ieee")) as r:
            assert r.binary_header.data_sample_format == 5

    def test_data_format_ibm(self):
        with SegyReader(get_path("ibm")) as r:
            assert r.binary_header.data_sample_format == 1

    def test_fixed_length_flag(self):
        with SegyReader(get_path("ieee")) as r:
            assert r.binary_header.fixed_length_trace_flag == 1

    def test_num_traces(self):
        with SegyReader(get_path("ieee")) as r:
            assert r.binary_header.num_traces_in_file == 10


# ------------------------------------------------------------------ #
# Trace iteration
# ------------------------------------------------------------------ #

class TestTraceReading:
    def _read_all(self, path) -> list:
        with SegyReader(path) as r:
            return [(h, d) for h, d in r.traces()]

    def test_trace_count_ieee(self):
        traces = self._read_all(get_path("ieee"))
        assert len(traces) == 10

    def test_trace_count_ibm(self):
        traces = self._read_all(get_path("ibm"))
        assert len(traces) == 10

    def test_trace_count_int32(self):
        traces = self._read_all(get_path("int32"))
        assert len(traces) == 10

    def test_trace_count_int16(self):
        traces = self._read_all(get_path("int16"))
        assert len(traces) == 10

    def test_sample_array_length(self):
        for suffix in ("ieee", "ibm", "int32", "int16"):
            traces = self._read_all(get_path(suffix))
            for _, data in traces:
                assert len(data) == 100, f"Failed for format {suffix}"

    def test_header_fields(self):
        with SegyReader(get_path("ieee")) as r:
            for i, (hdr, _) in enumerate(r.traces()):
                assert hdr["trace_seq_file"] == i + 1
                assert hdr["inline_no"] == 1
                assert hdr["crossline_no"] == i + 1

    def test_data_not_all_zero(self):
        for suffix in ("ieee", "ibm"):
            traces = self._read_all(get_path(suffix))
            for _, data in traces:
                assert np.any(data != 0), f"All-zero trace in format {suffix}"

    def test_slice_start_stop(self):
        with SegyReader(get_path("ieee")) as r:
            traces = list(r.traces(start=2, stop=5))
        assert len(traces) == 3

    def test_read_single_trace(self):
        with SegyReader(get_path("ieee")) as r:
            hdr, data = r.read_trace(7)
        assert hdr["trace_seq_file"] == 8
        assert len(data) == 100

    def test_ieee_ibm_close(self):
        """IEEE and IBM versions of the same data should be numerically close."""
        with SegyReader(get_path("ieee")) as r:
            ieee_traces = [d for _, d in r.traces()]
        with SegyReader(get_path("ibm")) as r:
            ibm_traces = [d for _, d in r.traces()]
        for ieee, ibm in zip(ieee_traces, ibm_traces):
            np.testing.assert_allclose(ieee, ibm, rtol=1e-5, atol=1e-6)


# ------------------------------------------------------------------ #
# num_traces helper
# ------------------------------------------------------------------ #

class TestNumTraces:
    def test_num_traces_from_header(self):
        with SegyReader(get_path("ieee")) as r:
            assert r.num_traces() == 10


# ------------------------------------------------------------------ #
# Context manager
# ------------------------------------------------------------------ #

class TestContextManager:
    def test_closed_raises(self):
        r = SegyReader(get_path("ieee"))
        r.open()
        r.close()
        with pytest.raises(RuntimeError):
            _ = r.textual_header

    def test_with_block(self):
        with SegyReader(get_path("ieee")) as r:
            bh = r.binary_header
        assert bh is not None


# ------------------------------------------------------------------ #
# SEG-Y Rev 1.0
# ------------------------------------------------------------------ #

class TestRev1:
    def test_revision(self, rev1_files):
        with SegyReader(rev1_files["ieee"]) as r:
            bh = r.binary_header
            assert bh.segy_revision_major == 1
            assert bh.segy_revision_minor == 0
            assert bh.segy_revision == "1.0"

    def test_samples_per_trace(self, rev1_files):
        """Rev 1 has no ext_samples field — must fall back to the 2-byte standard field."""
        with SegyReader(rev1_files["ieee"]) as r:
            assert r.binary_header.effective_samples_per_trace == 100

    def test_num_traces_estimated(self, rev1_files):
        """Rev 1 has no num_traces_in_file field — reader estimates from file size."""
        with SegyReader(rev1_files["ieee"]) as r:
            assert r.num_traces() == 10

    def test_trace_count(self, rev1_files):
        for fmt in ("ieee", "ibm", "int32", "int16"):
            with SegyReader(rev1_files[fmt]) as r:
                assert sum(1 for _ in r.traces()) == 10

    def test_data_decodes(self, rev1_files):
        for fmt in ("ieee", "ibm"):
            with SegyReader(rev1_files[fmt]) as r:
                for _, data in r.traces():
                    assert len(data) == 100
                    assert np.any(data != 0)


# ------------------------------------------------------------------ #
# SEG-Y Rev 2.0
# ------------------------------------------------------------------ #

class TestRev20:
    def test_revision(self, rev20_files):
        with SegyReader(rev20_files["ieee"]) as r:
            bh = r.binary_header
            assert bh.segy_revision_major == 2
            assert bh.segy_revision_minor == 0
            assert bh.segy_revision == "2.0"

    def test_samples_per_trace(self, rev20_files):
        with SegyReader(rev20_files["ieee"]) as r:
            assert r.binary_header.effective_samples_per_trace == 100

    def test_num_traces_from_header(self, rev20_files):
        """Rev 2.0 populates num_traces_in_file in the binary header."""
        with SegyReader(rev20_files["ieee"]) as r:
            assert r.num_traces() == 10

    def test_trace_count(self, rev20_files):
        for fmt in ("ieee", "ibm", "int32", "int16"):
            with SegyReader(rev20_files[fmt]) as r:
                assert sum(1 for _ in r.traces()) == 10

    def test_data_decodes(self, rev20_files):
        for fmt in ("ieee", "ibm"):
            with SegyReader(rev20_files[fmt]) as r:
                for _, data in r.traces():
                    assert len(data) == 100
                    assert np.any(data != 0)

    def test_rev20_and_rev21_data_match(self, rev20_files):
        """Same seed: Rev 2.0 and 2.1 IEEE files should produce identical samples."""
        with SegyReader(rev20_files["ieee"]) as r:
            rev20_data = [d for _, d in r.traces()]
        with SegyReader(get_path("ieee")) as r:
            rev21_data = [d for _, d in r.traces()]
        for d20, d21 in zip(rev20_data, rev21_data):
            np.testing.assert_array_equal(d20, d21)
