# SEG-Y 2.1 Reader — Project Guide

## Python runtime

There is **no system Python**. Use Miniconda:

```
/c/Users/MSpeziali/AppData/Local/miniconda3/python.exe
```

All required packages are installed there: `numpy`, `pandas`, `plotly`, `streamlit`, `pytest`.

## Common commands

```bash
# Run tests
/c/Users/MSpeziali/AppData/Local/miniconda3/python.exe -m pytest tests/test_reader.py -v

# Launch the Streamlit viewer
/c/Users/MSpeziali/AppData/Local/miniconda3/python.exe -m streamlit run app.py

# CLI inspector
/c/Users/MSpeziali/AppData/Local/miniconda3/python.exe main.py <file.segy>
/c/Users/MSpeziali/AppData/Local/miniconda3/python.exe main.py <file.segy> --trace 5 --samples 20
/c/Users/MSpeziali/AppData/Local/miniconda3/python.exe main.py <file.segy> --traces 0 10
```

## Project structure

```
segy21_reader/
├── segy21/               # Core library (importable package)
│   ├── __init__.py       # Exports: SegyReader
│   ├── reader.py         # SegyReader class — main entry point
│   ├── headers.py        # TextualHeader, BinaryFileHeader, TraceHeader
│   ├── constants.py      # Sizes, format codes, encodings
│   └── ibm_float.py      # IBM 360 float → IEEE converter
├── app.py                # Streamlit web viewer (4 tabs)
├── main.py               # CLI inspector
├── requirements.txt      # numpy>=1.24 (minimum; streamlit/plotly needed for app.py)
└── tests/
    ├── test_reader.py    # 35 pytest unit tests (all passing)
    ├── make_synthetic.py # Writes synthetic SEG-Y files for testing
    ├── rev21/            # Real SEG-Y 2.1 test files
    │   ├── BO_3D-Inglewood_rev21_v7.sgy
    │   ├── equinor_segyio_prestack_small-ps.segy
    │   ├── equinor_segyio_small.segy
    │   └── open-source-geoscience_Stratton-3D_SouthTexas_poststack_32bit.segy
    ├── rev1/             # (generated at test time)
    └── rev20/            # (generated at test time)
```

## Library API

```python
from segy21 import SegyReader

with SegyReader("survey.segy") as r:
    print(r.textual_header)              # TextualHeader
    print(r.binary_header.summary())     # BinaryFileHeader
    print(r.extended_textual_headers)    # list[str]
    print(r.num_traces())                # int

    for hdr, data in r.traces():        # iterate all traces
        pass

    for hdr, data in r.traces(start=10, stop=20):  # slice
        pass

    hdr, data = r.read_trace(42)        # random access by index
```

### Key classes

**`BinaryFileHeader`** — parsed 400-byte binary file header.  
Important properties: `segy_revision`, `effective_samples_per_trace`, `effective_sample_interval_us`, `data_sample_format`, `num_traces_in_file`.

**`TraceHeader`** — parsed 240-byte trace header.  
Access fields via `hdr["inline_no"]` or `hdr.get("cdp_x", 0)`.  
Important fields: `trace_seq_file`, `inline_no`, `crossline_no`, `cdp_x`, `cdp_y`, `num_samples`, `sample_interval_us`, `ext_num_samples`, `ext_sample_interval_ps`.

**`TextualHeader`** — 3200-byte text header.  
`str(hdr)` returns the 40-line formatted text. Encoding auto-detected (EBCDIC/ASCII/UTF-8).

### Supported data format codes

| Code | Format |
|------|--------|
| 1, 16 | 4-byte IBM float |
| 2 | 4-byte int32 |
| 3 | 2-byte int16 |
| 5 | 4-byte IEEE float |
| 6 | 8-byte IEEE double |
| 7 | 3-byte signed int |
| 8 | 1-byte int8 |
| 9 | 8-byte int64 |
| 10–12 | unsigned ints |
| 15 | 3-byte unsigned int |

## Streamlit viewer (app.py)

Four tabs:
- **Section** — seismic section as a Plotly heatmap. Slice by inline, crossline, or all traces. Colour scale and clip percentile controls.
- **Trace** — single trace waveform with amplitude stats.
- **Map** — scatter plot of CDP X/Y positions (falls back to inline/crossline grid if coordinates are zero).
- **Headers** — textual, binary, and extended headers; binary header shown as a full table.

Default directory: `tests/`. Recursively scans for `.segy`, `.sgy`, `.seg` files.

## SEG-Y revision handling

- **Rev 1.0** — standard 240-byte trace header, 2-byte samples/trace field, no `num_traces_in_file` (estimated from file size).
- **Rev 2.0** — adds 4-byte extended fields in binary header, `num_traces_in_file`, additional trace header blocks.
- **Rev 2.1** — adds `byte_offset_first_trace`, `num_data_trailer_stanzas`, extended sample count/interval in trace header.

The reader selects `ext_*` fields over standard fields when they are non-zero (Rev 2.0+).

## Testing

Synthetic files are generated at test time by `tests/make_synthetic.py` for formats: `ieee`, `ibm`, `int32`, `int16`. Tests cover Rev 1.0, 2.0, and 2.1. All 35 tests pass.

```bash
/c/Users/MSpeziali/AppData/Local/miniconda3/python.exe -m pytest tests/ -v
```
