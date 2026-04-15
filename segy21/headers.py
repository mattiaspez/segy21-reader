"""SEG-Y 2.1 header definitions and parsers."""

import struct
from dataclasses import dataclass, field
from typing import Optional
from .constants import (
    TEXTUAL_HEADER_SIZE, BINARY_HEADER_SIZE, TRACE_HEADER_SIZE,
    ENCODING_EBCDIC, ENCODING_ASCII, EBCDIC_CODEC, DATA_FORMATS,
    SEGY_REV_2_1,
)


@dataclass
class TextualHeader:
    raw: bytes
    encoding: str
    text: str

    @classmethod
    def from_bytes(cls, raw: bytes) -> "TextualHeader":
        assert len(raw) == TEXTUAL_HEADER_SIZE

        # Detect encoding: EBCDIC starts with 0xC3 ('C' in EBCDIC)
        if raw[0] == 0xC3:
            encoding = ENCODING_EBCDIC
            text = raw.decode(EBCDIC_CODEC, errors="replace")
        else:
            try:
                text = raw.decode("utf-8", errors="strict")
                encoding = "utf-8"
            except UnicodeDecodeError:
                text = raw.decode("ascii", errors="replace")
                encoding = ENCODING_ASCII

        return cls(raw=raw, encoding=encoding, text=text)

    def lines(self) -> list[str]:
        """Return the 40 lines of 80 characters each."""
        return [self.text[i * 80:(i + 1) * 80] for i in range(40)]

    def __str__(self) -> str:
        return "\n".join(f"C{i+1:02d} {line}" for i, line in enumerate(self.lines()))


@dataclass
class BinaryFileHeader:
    """
    SEG-Y 2.1 Binary File Header (400 bytes, big-endian).
    Field names and byte positions follow the SEG-Y 2.1 standard.
    Byte positions are 1-indexed from the start of the binary header.
    """
    # Core acquisition parameters
    job_id:                      int   # bytes 1-4
    line_number:                 int   # bytes 5-8
    reel_number:                 int   # bytes 9-12
    traces_per_ensemble:         int   # bytes 13-14
    aux_traces_per_ensemble:     int   # bytes 15-16
    sample_interval_us:          int   # bytes 17-18  (microseconds)
    sample_interval_orig_us:     int   # bytes 19-20
    samples_per_trace:           int   # bytes 21-22
    samples_per_trace_orig:      int   # bytes 23-24
    data_sample_format:          int   # bytes 25-26
    ensemble_fold:               int   # bytes 27-28
    trace_sorting:               int   # bytes 29-30
    vertical_sum:                int   # bytes 31-32
    sweep_freq_start:            int   # bytes 33-34
    sweep_freq_end:              int   # bytes 35-36
    sweep_length:                int   # bytes 37-38
    sweep_type:                  int   # bytes 39-40
    sweep_channel_trace_number:  int   # bytes 41-42
    sweep_taper_at_start:        int   # bytes 43-44
    sweep_taper_at_end:          int   # bytes 45-46
    taper_type:                  int   # bytes 47-48
    correlated_traces:           int   # bytes 49-50
    binary_gain_recovered:       int   # bytes 51-52
    amplitude_recovery_method:   int   # bytes 53-54
    measurement_system:          int   # bytes 55-56  (1=meters, 2=feet)
    impulse_signal_polarity:     int   # bytes 57-58
    vibratory_polarity_code:     int   # bytes 59-60
    # Extended (SEG-Y 2.0+)
    ext_traces_per_ensemble:     int   # bytes 61-64
    ext_aux_per_ensemble:        int   # bytes 65-68
    ext_samples_per_trace:       int   # bytes 69-72 (uint32)
    ext_sample_interval:         int   # bytes 73-80 (int64, in picoseconds)
    ext_sample_interval_orig:    int   # bytes 81-88 (int64)
    ext_samples_per_trace_orig:  int   # bytes 89-92 (uint32)
    ext_ensemble_fold:           int   # bytes 93-96 (uint32)
    integer_constant:            int   # bytes 97-100
    # bytes 101-300: unassigned
    # SEG-Y revision
    segy_revision_major:         int   # byte 301
    segy_revision_minor:         int   # byte 302
    fixed_length_trace_flag:     int   # bytes 303-304
    num_extended_textual_headers:int   # bytes 305-306
    # SEG-Y 2.1 additions
    num_additional_trace_headers:int   # bytes 307-308
    time_basis_code:             int   # bytes 309-310
    num_traces_in_file:          int   # bytes 311-318  (int64)
    byte_offset_first_trace:     int   # bytes 319-326  (uint64)
    num_data_trailer_stanzas:    int   # bytes 327-330  (int32)

    raw: bytes = field(repr=False)

    _FMT = (
        ">iii"          # job_id, line, reel        (bytes 1-12)
        "hhhhhhhh"      # traces/ens .. samples/tr   (bytes 13-24)
        "hhhhhhhhhhhhhhhhhhh"  # fmt .. polarity    (bytes 25-60)  19 shorts
        "iiIqq"         # ext fields                 (bytes 61-92) -- actually need exact layout
    )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "BinaryFileHeader":
        assert len(raw) == BINARY_HEADER_SIZE, f"Expected 400 bytes, got {len(raw)}"

        def u8(off): return struct.unpack_from(">B", raw, off)[0]
        def i16(off): return struct.unpack_from(">h", raw, off)[0]
        def u16(off): return struct.unpack_from(">H", raw, off)[0]
        def i32(off): return struct.unpack_from(">i", raw, off)[0]
        def u32(off): return struct.unpack_from(">I", raw, off)[0]
        def i64(off): return struct.unpack_from(">q", raw, off)[0]
        def u64(off): return struct.unpack_from(">Q", raw, off)[0]

        return cls(
            job_id                      = i32(0),
            line_number                 = i32(4),
            reel_number                 = i32(8),
            traces_per_ensemble         = i16(12),
            aux_traces_per_ensemble     = i16(14),
            sample_interval_us          = i16(16),
            sample_interval_orig_us     = i16(18),
            samples_per_trace           = i16(20),
            samples_per_trace_orig      = i16(22),
            data_sample_format          = i16(24),
            ensemble_fold               = i16(26),
            trace_sorting               = i16(28),
            vertical_sum                = i16(30),
            sweep_freq_start            = i16(32),
            sweep_freq_end              = i16(34),
            sweep_length                = i16(36),
            sweep_type                  = i16(38),
            sweep_channel_trace_number  = i16(40),
            sweep_taper_at_start        = i16(42),
            sweep_taper_at_end          = i16(44),
            taper_type                  = i16(46),
            correlated_traces           = i16(48),
            binary_gain_recovered       = i16(50),
            amplitude_recovery_method   = i16(52),
            measurement_system          = i16(54),
            impulse_signal_polarity     = i16(56),
            vibratory_polarity_code     = i16(58),
            ext_traces_per_ensemble     = i32(60),
            ext_aux_per_ensemble        = i32(64),
            ext_samples_per_trace       = u32(68),
            ext_sample_interval         = i64(72),
            ext_sample_interval_orig    = i64(80),
            ext_samples_per_trace_orig  = u32(88),
            ext_ensemble_fold           = u32(92),
            integer_constant            = i32(96),
            segy_revision_major         = u8(300),
            segy_revision_minor         = u8(301),
            fixed_length_trace_flag     = i16(302),
            num_extended_textual_headers= i16(304),
            num_additional_trace_headers= i16(306),
            time_basis_code             = i16(308),
            num_traces_in_file          = i64(310),
            byte_offset_first_trace     = u64(318),
            num_data_trailer_stanzas    = i32(326),
            raw                         = raw,
        )

    @property
    def segy_revision(self) -> str:
        return f"{self.segy_revision_major}.{self.segy_revision_minor}"

    @property
    def effective_samples_per_trace(self) -> int:
        """Return ext field if set (non-zero), else the standard 2-byte field."""
        return self.ext_samples_per_trace if self.ext_samples_per_trace else self.samples_per_trace

    @property
    def effective_sample_interval_us(self) -> float:
        """Sample interval in microseconds. Prefers ext field (picoseconds -> µs)
        only when the value is plausible (1 µs – 1 s range)."""
        ext = self.ext_sample_interval
        if 0 < ext <= 1_000_000_000_000:   # 1 ps to 1 s expressed in ps
            return ext / 1e6
        return self.sample_interval_us

    @property
    def data_format_description(self) -> str:
        return DATA_FORMATS.get(self.data_sample_format, (None, None, "Unknown"))[2]

    def summary(self) -> str:
        lines = [
            f"SEG-Y Revision        : {self.segy_revision}",
            f"Data Sample Format    : {self.data_sample_format} ({self.data_format_description})",
            f"Samples per Trace     : {self.effective_samples_per_trace}",
            f"Sample Interval       : {self.effective_sample_interval_us:.4f} µs",
            f"Traces per Ensemble   : {self.traces_per_ensemble or self.ext_traces_per_ensemble}",
            f"Ensemble Fold         : {self.ensemble_fold or self.ext_ensemble_fold}",
            f"Measurement System    : {'Meters' if self.measurement_system == 1 else 'Feet' if self.measurement_system == 2 else 'Unknown'}",
            f"Extended Txt Headers  : {self.num_extended_textual_headers}",
            f"Fixed-Length Traces   : {'Yes' if self.fixed_length_trace_flag == 1 else 'No'}",
            f"Traces in File        : {self.num_traces_in_file if self.num_traces_in_file else 'Not specified'}",
        ]
        return "\n".join(lines)


# Trace header field definitions: (name, byte_offset_0indexed, format, description)
# All offsets are 0-indexed from the start of the 240-byte trace header.
TRACE_HEADER_FIELDS = [
    ("trace_seq_line",          0,   ">i", "Trace sequence number within line"),
    ("trace_seq_file",          4,   ">i", "Trace sequence number within SEG-Y file"),
    ("field_record_no",         8,   ">i", "Original field record number"),
    ("trace_no_in_record",      12,  ">i", "Trace sequence number within field record"),
    ("energy_source_point",     16,  ">i", "Energy source point number"),
    ("ensemble_no",             20,  ">i", "Ensemble number (CDP, CMP, etc.)"),
    ("trace_no_in_ensemble",    24,  ">i", "Trace sequence number within ensemble"),
    ("trace_id_code",           28,  ">h", "Trace identification code"),
    ("num_vert_summed",         30,  ">h", "Number of vertically summed traces"),
    ("num_horiz_stacked",       32,  ">h", "Number of horizontally stacked traces"),
    ("data_use",                34,  ">h", "Data use (1=production, 2=test)"),
    ("source_receiver_dist",    36,  ">i", "Distance from center of source to receiver"),
    ("receiver_elevation",      40,  ">i", "Receiver group elevation"),
    ("source_elevation",        44,  ">i", "Surface elevation at source"),
    ("source_depth",            48,  ">i", "Source depth below surface"),
    ("datum_elevation_receiver",52,  ">i", "Seismic datum elevation at receiver"),
    ("datum_elevation_source",  56,  ">i", "Seismic datum elevation at source"),
    ("water_depth_source",      60,  ">i", "Water depth at source"),
    ("water_depth_receiver",    64,  ">i", "Water depth at receiver group"),
    ("elevation_scalar",        68,  ">h", "Scalar for elevations and depths"),
    ("coord_scalar",            70,  ">h", "Scalar for coordinates"),
    ("source_x",                72,  ">i", "Source X coordinate"),
    ("source_y",                76,  ">i", "Source Y coordinate"),
    ("receiver_x",              80,  ">i", "Receiver X coordinate"),
    ("receiver_y",              84,  ">i", "Receiver Y coordinate"),
    ("coord_units",             88,  ">h", "Coordinate units"),
    ("weathering_velocity",     90,  ">h", "Weathering velocity"),
    ("subweathering_velocity",  92,  ">h", "Subweathering velocity"),
    ("uphole_time_source",      94,  ">h", "Uphole time at source (ms)"),
    ("uphole_time_group",       96,  ">h", "Uphole time at group (ms)"),
    ("source_static",           98,  ">h", "Source static correction (ms)"),
    ("group_static",            100, ">h", "Group static correction (ms)"),
    ("total_static",            102, ">h", "Total static applied (ms)"),
    ("lag_time_a",              104, ">h", "Lag time A (ms)"),
    ("lag_time_b",              106, ">h", "Lag time B (ms)"),
    ("delay_record_time",       108, ">h", "Delay recording time (ms)"),
    ("mute_time_start",         110, ">h", "Mute time - start (ms)"),
    ("mute_time_end",           112, ">h", "Mute time - end (ms)"),
    ("num_samples",             114, ">h", "Number of samples in this trace"),
    ("sample_interval_us",      116, ">h", "Sample interval (µs)"),
    ("gain_type",               118, ">h", "Gain type of field instruments"),
    ("instrument_gain",         120, ">h", "Instrument gain constant (dB)"),
    ("instrument_early_gain",   122, ">h", "Instrument early or initial gain (dB)"),
    ("correlated",              124, ">h", "Correlated (1=no, 2=yes)"),
    ("sweep_freq_start",        126, ">h", "Sweep frequency at start (Hz)"),
    ("sweep_freq_end",          128, ">h", "Sweep frequency at end (Hz)"),
    ("sweep_length",            130, ">h", "Sweep length (ms)"),
    ("sweep_type",              132, ">h", "Sweep type"),
    ("sweep_taper_start",       134, ">h", "Sweep trace taper length at start (ms)"),
    ("sweep_taper_end",         136, ">h", "Sweep trace taper length at end (ms)"),
    ("taper_type",              138, ">h", "Taper type"),
    ("alias_filter_freq",       140, ">h", "Alias filter frequency (Hz)"),
    ("alias_filter_slope",      142, ">h", "Alias filter slope (dB/octave)"),
    ("notch_filter_freq",       144, ">h", "Notch filter frequency (Hz)"),
    ("notch_filter_slope",      146, ">h", "Notch filter slope (dB/octave)"),
    ("low_cut_freq",            148, ">h", "Low-cut frequency (Hz)"),
    ("high_cut_freq",           150, ">h", "High-cut frequency (Hz)"),
    ("low_cut_slope",           152, ">h", "Low-cut slope (dB/octave)"),
    ("high_cut_slope",          154, ">h", "High-cut slope (dB/octave)"),
    ("year",                    156, ">h", "Year data recorded"),
    ("day_of_year",             158, ">h", "Day of year"),
    ("hour",                    160, ">h", "Hour of day"),
    ("minute",                  162, ">h", "Minute of hour"),
    ("second",                  164, ">h", "Second of minute"),
    ("time_basis_code",         166, ">h", "Time basis code"),
    ("trace_weighting_factor",  168, ">h", "Trace weighting factor"),
    ("geophone_group_roll_sw1", 170, ">h", "Geophone group number (roll switch pos 1)"),
    ("geophone_group_first",    172, ">h", "Geophone group number (first trace)"),
    ("geophone_group_last",     174, ">h", "Geophone group number (last trace)"),
    ("gap_size",                176, ">h", "Gap size"),
    ("over_travel",             178, ">h", "Over travel (1=down/behind, 2=up/ahead)"),
    # bytes 181-232: X,Y,inline,crossline etc. (SEG-Y Rev 1+)
    ("cdp_x",                   180, ">i", "X coordinate of ensemble (CDP)"),
    ("cdp_y",                   184, ">i", "Y coordinate of ensemble (CDP)"),
    ("inline_no",               188, ">i", "Inline number"),
    ("crossline_no",            192, ">i", "Crossline number"),
    ("shot_point_no",           196, ">i", "Shot point number"),
    ("shot_point_scalar",       200, ">h", "Scalar for shot point number"),
    ("trace_measure_unit",      202, ">h", "Trace value measurement unit"),
    # bytes 205-210: transduction constant (mantissa + exp)
    ("transduction_exp",        210, ">h", "Transduction constant exponent"),
    ("device_id",               212, ">h", "Device/Trace Identifier"),
    ("time_scalar",             214, ">h", "Scalar for times in trace header"),
    ("source_type",             216, ">h", "Source type/orientation"),
    # bytes 219-224: source energy direction
    ("source_measure_exp",      224, ">h", "Source measurement exponent"),
    # SEG-Y 2.0+: bytes 233-240
    ("ext_num_samples",         232, ">I", "Extended number of samples (SEG-Y 2.0+)"),
    ("ext_sample_interval_ps",  236, ">i", "Extended sample interval in picoseconds (SEG-Y 2.0+)"),
]


@dataclass
class TraceHeader:
    fields: dict
    raw: bytes = field(repr=False)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "TraceHeader":
        assert len(raw) == TRACE_HEADER_SIZE
        fields = {}
        for name, offset, fmt, _ in TRACE_HEADER_FIELDS:
            size = struct.calcsize(fmt)
            if offset + size <= TRACE_HEADER_SIZE:
                (val,) = struct.unpack_from(fmt, raw, offset)
                fields[name] = val
        return cls(fields=fields, raw=raw)

    def __getitem__(self, key: str):
        return self.fields[key]

    def get(self, key: str, default=None):
        return self.fields.get(key, default)

    @property
    def effective_num_samples(self) -> int:
        ext = self.fields.get("ext_num_samples", 0)
        return ext if ext else self.fields.get("num_samples", 0)

    @property
    def effective_sample_interval_us(self) -> float:
        ext_ps = self.fields.get("ext_sample_interval_ps", 0)
        if ext_ps:
            return ext_ps / 1e6
        return self.fields.get("sample_interval_us", 0)

    def summary(self, verbose: bool = False) -> str:
        key_fields = [
            ("trace_seq_file",    "Trace # in file"),
            ("trace_seq_line",    "Trace # in line"),
            ("field_record_no",   "Field record #"),
            ("ensemble_no",       "Ensemble #"),
            ("inline_no",         "Inline #"),
            ("crossline_no",      "Crossline #"),
            ("cdp_x",             "CDP X"),
            ("cdp_y",             "CDP Y"),
            ("source_x",          "Source X"),
            ("source_y",          "Source Y"),
            ("receiver_x",        "Receiver X"),
            ("receiver_y",        "Receiver Y"),
            ("num_samples",       "Num samples"),
            ("sample_interval_us","Sample interval (µs)"),
            ("trace_id_code",     "Trace ID code"),
            ("year",              "Year"),
        ]
        if verbose:
            return "\n".join(
                f"  {label:<28}: {self.fields.get(key, 'N/A')}"
                for key, label in key_fields
            )
        return "  " + "  ".join(
            f"{label}={self.fields.get(key, 'N/A')}"
            for key, label in key_fields[:8]
        )
