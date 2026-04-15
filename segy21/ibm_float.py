"""IBM 360 floating-point <-> IEEE 754 conversion."""

import struct
import numpy as np


def ibm_to_ieee(raw_bytes: bytes) -> np.ndarray:
    """Convert a bytes buffer of 4-byte IBM floats to a numpy float32 array."""
    n = len(raw_bytes) // 4
    ibm = np.frombuffer(raw_bytes, dtype=">u4", count=n)

    sign     = (ibm >> 31) & 0x01
    exponent = (ibm >> 24) & 0x7F   # biased exponent (excess-64, base 16)
    mantissa = (ibm & 0x00FFFFFF).astype(np.float64) / (1 << 24)

    # IBM float: value = (-1)^sign * 16^(exp-64) * mantissa
    value = mantissa * np.power(16.0, exponent.astype(np.float64) - 64.0)
    value[sign == 1] *= -1.0

    return value.astype(np.float32)
