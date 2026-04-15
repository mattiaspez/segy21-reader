"""SEG-Y 2.1 constants and format definitions."""

TEXTUAL_HEADER_SIZE = 3200
BINARY_HEADER_SIZE = 400
TRACE_HEADER_SIZE = 240

# Data sample format codes -> (struct_fmt, bytes_per_sample, description)
DATA_FORMATS = {
    1:  (None,   4, "4-byte IBM floating-point"),
    2:  (">i4",  4, "4-byte two's complement integer"),
    3:  (">i2",  2, "2-byte two's complement integer"),
    5:  (">f4",  4, "4-byte IEEE floating-point"),
    6:  (">f8",  8, "8-byte IEEE floating-point (double)"),
    7:  (None,   3, "3-byte two's complement integer"),
    8:  (">i1",  1, "1-byte two's complement integer"),
    9:  (">i8",  8, "8-byte two's complement integer"),
    10: (">u4",  4, "4-byte unsigned integer"),
    11: (">u2",  2, "2-byte unsigned integer"),
    12: (">u1",  1, "1-byte unsigned integer"),
    15: (None,   3, "3-byte unsigned integer"),
    16: (None,   4, "4-byte IBM floating-point (alt)"),
}

# Textual header encodings
ENCODING_EBCDIC = "ebcdic"
ENCODING_ASCII  = "ascii"
ENCODING_UTF8   = "utf-8"

# SEG-Y revision bytes (bytes 3501-3502 in file, i.e. binary header bytes 277-278)
SEGY_REV_1_0 = 0x0100
SEGY_REV_2_0 = 0x0200
SEGY_REV_2_1 = 0x0201

# EBCDIC code page
EBCDIC_CODEC = "cp500"
