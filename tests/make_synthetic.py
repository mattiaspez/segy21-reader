"""
Generate a minimal synthetic SEG-Y 2.1 file for testing.

Produces:
  tests/synthetic_segy21.segy   -- IEEE float (format code 5), 10 traces, 100 samples
  tests/synthetic_segy21_ibm.segy -- IBM float (format code 1), 10 traces, 100 samples
"""

import struct
import numpy as np
from pathlib import Path

OUT_DIR_REV1  = Path(__file__).parent / "rev1"
OUT_DIR_REV20 = Path(__file__).parent / "rev20"
OUT_DIR       = Path(__file__).parent / "rev21"


def make_textual_header(text: str = "") -> bytes:
    """Build a 3200-byte ASCII textual header (40 lines × 80 chars)."""
    content_lines = [
        "C 1 SEG-Y 2.1 SYNTHETIC TEST FILE",
        "C 2 Created by make_synthetic.py",
        "C 3 Format: IEEE 32-bit float, 10 traces, 100 samples @ 2ms",
    ]
    lines = [line.ljust(80)[:80] for line in content_lines]
    while len(lines) < 40:
        lines.append(("C" + str(len(lines) + 1)).ljust(80)[:80])
    raw = "".join(lines)
    assert len(raw) == 3200, f"Expected 3200, got {len(raw)}"
    return raw.encode("ascii")


def make_binary_header(
    data_fmt: int,
    samples: int,
    sample_interval_us: int,
    n_traces: int = 0,
    revision: tuple = (2, 1),
) -> bytes:
    """
    Build a 400-byte SEG-Y binary file header.

    revision : (major, minor) tuple
        (1, 0) → SEG-Y Rev 1.0
        (2, 0) → SEG-Y Rev 2.0
        (2, 1) → SEG-Y Rev 2.1 (default)
    """
    buf = bytearray(400)

    def put_i16(off, val): struct.pack_into(">h", buf, off, val)
    def put_i32(off, val): struct.pack_into(">i", buf, off, val)
    def put_i64(off, val): struct.pack_into(">q", buf, off, val)
    def put_u8(off, val):  struct.pack_into(">B", buf, off, val)

    put_i32(0,  1)       # job_id
    put_i32(4,  1)       # line_number
    put_i32(8,  1)       # reel_number
    put_i16(12, 1)       # traces_per_ensemble
    put_i16(16, sample_interval_us)
    put_i16(18, sample_interval_us)
    put_i16(20, samples)
    put_i16(22, samples)
    put_i16(24, data_fmt)
    put_i16(26, 1)       # ensemble_fold
    put_i16(54, 1)       # measurement_system = meters

    major, minor = revision
    put_u8(300, major)
    put_u8(301, minor)
    put_i16(302, 1)      # fixed-length traces
    put_i16(304, 0)      # no extended textual headers
    put_i16(306, 0)      # no additional trace headers

    if major >= 2:
        # Rev 2.0+ extended binary header fields
        put_i64(310, n_traces)   # num_traces_in_file
        # byte_offset_first_trace = 0 → reader uses fh.tell()

    return bytes(buf)


def make_trace_header(
    trace_idx: int,
    samples: int,
    sample_interval_us: int,
) -> bytes:
    buf = bytearray(240)

    def put_i16(off, val): struct.pack_into(">h", buf, off, val)
    def put_i32(off, val): struct.pack_into(">i", buf, off, val)

    put_i32(0,  trace_idx + 1)   # trace_seq_line
    put_i32(4,  trace_idx + 1)   # trace_seq_file
    put_i32(8,  trace_idx + 1)   # field_record_no
    put_i32(12, 1)               # trace_no_in_record
    put_i32(20, trace_idx + 1)   # ensemble_no
    put_i32(24, 1)               # trace_no_in_ensemble
    put_i16(28, 1)               # trace_id_code = seismic
    put_i16(114, samples)        # num_samples
    put_i16(116, sample_interval_us)
    # CDP coords
    put_i32(180, 100 + trace_idx * 25)   # cdp_x
    put_i32(184, 200)                    # cdp_y
    put_i32(188, 1)                      # inline
    put_i32(192, trace_idx + 1)          # crossline
    # Date/time (fake)
    put_i16(156, 2024)   # year
    put_i16(158, 1)      # day
    put_i16(160, 0)      # hour
    put_i16(162, 0)      # minute
    put_i16(164, 0)      # second
    return bytes(buf)


def ieee_float_trace(trace_idx: int, n_samples: int) -> bytes:
    t = np.arange(n_samples, dtype=np.float32) * 0.002  # 2ms
    data = (
        np.sin(2 * np.pi * 30 * t) * np.exp(-t * 2)   # 30 Hz Ricker-ish
        + 0.1 * np.random.randn(n_samples).astype(np.float32) * float(trace_idx + 1)
    ).astype(np.float32)
    return data.astype(">f4").tobytes()


def ieee_to_ibm(ieee_array: np.ndarray) -> bytes:
    """Convert float32 numpy array to IBM 360 float bytes."""
    result = bytearray(len(ieee_array) * 4)
    for i, v in enumerate(ieee_array):
        f = float(v)
        if f == 0.0:
            ibm = 0
        else:
            sign = 1 if f < 0 else 0
            f = abs(f)
            exp = 0
            while f < 0.0625:
                f *= 16.0
                exp -= 1
            while f >= 1.0:
                f /= 16.0
                exp += 1
            exp += 64
            mantissa = int(f * (1 << 24))
            ibm = (sign << 31) | (exp << 24) | (mantissa & 0x00FFFFFF)
        struct.pack_into(">I", result, i * 4, ibm)
    return bytes(result)


def write_segy(path: Path, data_fmt: int, n_traces: int = 10, n_samples: int = 100,
               sample_interval_us: int = 2000, revision: tuple = (2, 1)) -> None:
    np.random.seed(42)
    with open(path, "wb") as f:
        f.write(make_textual_header())
        f.write(make_binary_header(data_fmt, n_samples, sample_interval_us, n_traces,
                                   revision=revision))
        for i in range(n_traces):
            f.write(make_trace_header(i, n_samples, sample_interval_us))
            t = np.arange(n_samples, dtype=np.float32) * (sample_interval_us / 1e6)
            data = (
                np.sin(2 * np.pi * 30 * t) * np.exp(-t * 4)
                + 0.05 * (i + 1) * np.random.randn(n_samples).astype(np.float32)
            ).astype(np.float32)
            if data_fmt == 5:
                f.write(data.astype(">f4").tobytes())
            elif data_fmt == 1:
                f.write(ieee_to_ibm(data))
            elif data_fmt == 2:
                f.write(data.astype(">i4").tobytes())
            elif data_fmt == 3:
                f.write((data * 32767).clip(-32768, 32767).astype(">i2").tobytes())
    print(f"Written: {path}")


if __name__ == "__main__":
    for out_dir, rev, tag in [
        (OUT_DIR_REV1,  (1, 0), "rev1"),
        (OUT_DIR_REV20, (2, 0), "rev20"),
        (OUT_DIR,       (2, 1), "rev21"),
    ]:
        out_dir.mkdir(exist_ok=True)
        write_segy(out_dir / f"synthetic_{tag}.segy",     data_fmt=5, revision=rev)
        write_segy(out_dir / f"synthetic_{tag}_ibm.segy", data_fmt=1, revision=rev)
        write_segy(out_dir / f"synthetic_{tag}_int32.segy", data_fmt=2, revision=rev)
        write_segy(out_dir / f"synthetic_{tag}_int16.segy", data_fmt=3, revision=rev)
        print(f"Written Rev {rev[0]}.{rev[1]} files to {out_dir}/")
    print("All synthetic files created.")
