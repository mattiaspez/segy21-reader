# segy21-reader

A pure-Python SEG-Y reader for revisions 1.0, 2.0, and 2.1, with a CLI inspector and an interactive Streamlit viewer for post-stack seismic data. Includes open-source SEG-Y test datasets.

## Features

- Reads SEG-Y revisions 1.0, 2.0, and 2.1
- Supports all standard data sample formats (IBM float, IEEE float/double, int8/16/32/64, unsigned ints)
- Auto-detects EBCDIC / ASCII / UTF-8 textual headers
- Extended trace header fields (Rev 2.0+) preferred over standard fields when non-zero
- Random-access and iterator-based trace reading
- Interactive Streamlit viewer with section, trace, map, and header tabs
- CLI inspector for quick file inspection from the terminal

## Installation

```bash
pip install numpy>=1.24          # core library only
pip install numpy plotly streamlit pandas  # + web viewer
```

Clone the repo and import directly — there is no package distribution yet:

```bash
git clone https://github.com/mattiaspez/segy21-reader.git
cd segy21-reader
```

## Quick start

```python
from segy21 import SegyReader

with SegyReader("survey.segy") as r:
    print(r.textual_header)              # 40-line text header
    print(r.binary_header.summary())     # key binary header fields
    print(r.num_traces())                # total trace count

    # Iterate all traces
    for hdr, data in r.traces():
        print(hdr["inline_no"], data.mean())

    # Slice a range
    for hdr, data in r.traces(start=10, stop=20):
        pass

    # Random access by index
    hdr, data = r.read_trace(42)
    print(hdr["cdp_x"], hdr["cdp_y"])
```

### Key classes

**`BinaryFileHeader`**  
Parsed 400-byte binary file header. Key properties: `segy_revision`, `effective_samples_per_trace`, `effective_sample_interval_us`, `data_sample_format`, `num_traces_in_file`.

**`TraceHeader`**  
Parsed 240-byte trace header. Access fields via `hdr["inline_no"]` or `hdr.get("cdp_x", 0)`.  
Key fields: `trace_seq_file`, `inline_no`, `crossline_no`, `cdp_x`, `cdp_y`, `num_samples`, `sample_interval_us`, `ext_num_samples`, `ext_sample_interval_ps`.

**`TextualHeader`**  
3200-byte text header. `str(hdr)` returns the 40-line formatted text; encoding is auto-detected.

### Supported data sample formats

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
| 10–12 | Unsigned ints (4, 2, 8-byte) |
| 15 | 3-byte unsigned int |

## CLI inspector

```bash
python main.py survey.segy                    # headers + first 3 trace stats
python main.py survey.segy --traces 0 10      # headers for traces 0–9
python main.py survey.segy --trace 42         # detailed single-trace inspect
python main.py survey.segy --trace 42 --samples 20  # include first 20 sample values
python main.py survey.segy --no-textual       # skip textual header
```

## Streamlit viewer

```bash
streamlit run app.py
```

Four tabs:

| Tab | Description |
|-----|-------------|
| **Section** | Seismic section as a Plotly heatmap. Slice by inline, crossline, or all traces. Colour scale and clip-percentile controls. Wiggle display mode. |
| **Trace** | Single-trace waveform with amplitude statistics. |
| **Map** | Scatter plot of CDP X/Y positions (falls back to inline/crossline grid when coordinates are zero). |
| **Headers** | Textual, binary, and extended headers. Binary header shown as a full field table. |

## Project structure

```
segy21-reader/
├── segy21/               # Core library
│   ├── __init__.py
│   ├── reader.py         # SegyReader — main entry point
│   ├── headers.py        # TextualHeader, BinaryFileHeader, TraceHeader
│   ├── constants.py      # Sizes, format codes, encodings
│   └── ibm_float.py      # IBM 360 float → IEEE converter
├── app.py                # Streamlit viewer
├── main.py               # CLI inspector
├── requirements.txt
└── tests/
    ├── test_reader.py    # 35 pytest unit tests
    ├── make_synthetic.py # Generates synthetic SEG-Y files at test time
    └── rev21/            # Open-source SEG-Y test files (Equinor samples)
```

## Testing

Synthetic SEG-Y files are generated at test time by `tests/make_synthetic.py` (formats: IEEE float, IBM float, int32, int16; revisions 1.0, 2.0, 2.1). Two real open-source files from Equinor are included in `tests/rev21/`.

```bash
python -m pytest tests/ -v
```

All 35 tests pass.

## License

[MIT](LICENSE)
