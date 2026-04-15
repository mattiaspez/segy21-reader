"""SEG-Y 2.1 file reader."""

import os
import struct
from pathlib import Path
from typing import Iterator, Optional
import numpy as np

from .constants import (
    TEXTUAL_HEADER_SIZE, BINARY_HEADER_SIZE, TRACE_HEADER_SIZE,
    DATA_FORMATS,
)
from .headers import TextualHeader, BinaryFileHeader, TraceHeader
from .ibm_float import ibm_to_ieee


class SegyReader:
    """
    Read SEG-Y 2.1 files.

    Usage
    -----
    with SegyReader("survey.segy") as r:
        print(r.textual_header)
        print(r.binary_header.summary())
        for hdr, data in r.traces():
            print(hdr.summary())
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._fh = None
        self._textual_header: Optional[TextualHeader] = None
        self._binary_header:  Optional[BinaryFileHeader] = None
        self._extended_textual_headers: list[str] = []
        self._data_start_offset: Optional[int] = None

    # ------------------------------------------------------------------ #
    # Context manager
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "SegyReader":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def open(self) -> None:
        self._fh = open(self.path, "rb")
        self._read_file_headers()

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    # ------------------------------------------------------------------ #
    # Public properties
    # ------------------------------------------------------------------ #

    @property
    def textual_header(self) -> TextualHeader:
        self._ensure_open()
        return self._textual_header

    @property
    def binary_header(self) -> BinaryFileHeader:
        self._ensure_open()
        return self._binary_header

    @property
    def extended_textual_headers(self) -> list[str]:
        self._ensure_open()
        return self._extended_textual_headers

    # ------------------------------------------------------------------ #
    # Trace iteration
    # ------------------------------------------------------------------ #

    def traces(
        self,
        start: int = 0,
        stop: Optional[int] = None,
    ) -> Iterator[tuple[TraceHeader, np.ndarray]]:
        """
        Iterate over traces.

        Parameters
        ----------
        start : int
            0-indexed first trace to yield.
        stop : int, optional
            0-indexed exclusive upper bound (like range). None = all traces.

        Yields
        ------
        (TraceHeader, np.ndarray)  -- header and sample array (float32 or int)
        """
        self._ensure_open()
        self._fh.seek(self._data_start_offset)

        bh = self._binary_header
        fmt_code = bh.data_sample_format
        fixed_samples = bh.effective_samples_per_trace
        fixed_length = bh.fixed_length_trace_flag == 1
        n_extra_headers = max(0, bh.num_additional_trace_headers)

        if fmt_code not in DATA_FORMATS:
            raise ValueError(f"Unknown data sample format code: {fmt_code}")

        numpy_fmt, bytes_per_sample, _ = DATA_FORMATS[fmt_code]

        idx = 0
        while True:
            hdr_bytes = self._fh.read(TRACE_HEADER_SIZE)
            if not hdr_bytes or len(hdr_bytes) < TRACE_HEADER_SIZE:
                break

            hdr = TraceHeader.from_bytes(hdr_bytes)

            # Rev 2.0+: skip any additional 240-byte trace header blocks
            if n_extra_headers:
                self._fh.seek(n_extra_headers * TRACE_HEADER_SIZE, 1)

            # Determine number of samples for this trace
            if fixed_length and fixed_samples:
                n_samples = fixed_samples
            else:
                n_samples = hdr.effective_num_samples or fixed_samples
                if not n_samples:
                    raise ValueError(
                        f"Trace {idx}: cannot determine number of samples. "
                        "Set fixed-length flag or populate trace header."
                    )

            data_bytes = self._fh.read(n_samples * bytes_per_sample)
            if len(data_bytes) < n_samples * bytes_per_sample:
                # Truncated trace at end of file
                break

            if idx < start:
                idx += 1
                continue

            if stop is not None and idx >= stop:
                break

            data = self._decode_samples(data_bytes, fmt_code, numpy_fmt, n_samples)
            yield hdr, data
            idx += 1

    def read_trace(self, index: int) -> tuple[TraceHeader, np.ndarray]:
        """Read a single trace by 0-indexed position. O(n) scan — use for spot checks."""
        for hdr, data in self.traces(start=index, stop=index + 1):
            return hdr, data
        raise IndexError(f"Trace index {index} out of range")

    def num_traces(self) -> int:
        """
        Return the number of traces.
        Uses the binary header field if populated, otherwise counts by scanning.
        """
        self._ensure_open()
        bh = self._binary_header
        if bh.num_traces_in_file > 0:
            return bh.num_traces_in_file
        # Fallback: estimate from file size
        fmt_code = bh.data_sample_format
        n_samples = bh.effective_samples_per_trace
        if fmt_code in DATA_FORMATS and n_samples:
            _, bps, _ = DATA_FORMATS[fmt_code]
            file_size = self.path.stat().st_size
            data_size = file_size - self._data_start_offset
            trace_size = TRACE_HEADER_SIZE + n_samples * bps
            return data_size // trace_size
        return -1  # unknown

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _ensure_open(self) -> None:
        if self._fh is None:
            raise RuntimeError("SegyReader is not open. Use open() or a context manager.")

    def _read_file_headers(self) -> None:
        fh = self._fh
        fh.seek(0)

        # 1. Textual header
        raw_txt = fh.read(TEXTUAL_HEADER_SIZE)
        self._textual_header = TextualHeader.from_bytes(raw_txt)

        # 2. Binary file header
        raw_bin = fh.read(BINARY_HEADER_SIZE)
        self._binary_header = BinaryFileHeader.from_bytes(raw_bin)

        bh = self._binary_header
        n_ext = bh.num_extended_textual_headers

        # 3. Extended textual headers (-1 means variable, scan for SEG: EndText stanza)
        self._extended_textual_headers = []
        if n_ext == -1:
            # Scan until the End-Of-Extended-Headers stanza is found.
            # Per SEG-Y 2.1 the stanza begins with "((SEG: EndText))" but some files
            # use "((SEG:EndText))" (no space) so we check both.
            while True:
                raw_ext = fh.read(TEXTUAL_HEADER_SIZE)
                if len(raw_ext) < TEXTUAL_HEADER_SIZE:
                    break
                text = self._decode_text_block(raw_ext)
                self._extended_textual_headers.append(text)
                if "SEG:EndText" in text or "SEG: EndText" in text:
                    break
        elif n_ext > 0:
            for _ in range(n_ext):
                raw_ext = fh.read(TEXTUAL_HEADER_SIZE)
                self._extended_textual_headers.append(self._decode_text_block(raw_ext))

        # If byte_offset_first_trace is set, use it; else use current position
        if bh.byte_offset_first_trace:
            self._data_start_offset = bh.byte_offset_first_trace
        else:
            self._data_start_offset = fh.tell()

    def _decode_text_block(self, raw: bytes) -> str:
        if raw[0] == 0xC3:
            return raw.decode("cp500", errors="replace")
        try:
            return raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return raw.decode("ascii", errors="replace")

    def _decode_samples(
        self,
        data_bytes: bytes,
        fmt_code: int,
        numpy_fmt: Optional[str],
        n_samples: int,
    ) -> np.ndarray:
        if fmt_code in (1, 16):
            return ibm_to_ieee(data_bytes)
        if fmt_code == 7:
            # 3-byte signed int — manual decode
            result = np.empty(n_samples, dtype=np.int32)
            for i in range(n_samples):
                b = data_bytes[i * 3:(i + 1) * 3]
                val = (b[0] << 16) | (b[1] << 8) | b[2]
                if val & 0x800000:
                    val -= 0x1000000
                result[i] = val
            return result
        if fmt_code == 15:
            # 3-byte unsigned int
            result = np.empty(n_samples, dtype=np.uint32)
            for i in range(n_samples):
                b = data_bytes[i * 3:(i + 1) * 3]
                result[i] = (b[0] << 16) | (b[1] << 8) | b[2]
            return result
        if numpy_fmt:
            return np.frombuffer(data_bytes, dtype=numpy_fmt, count=n_samples).copy()
        raise ValueError(f"Unsupported format code: {fmt_code}")
