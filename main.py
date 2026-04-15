"""
CLI for inspecting SEG-Y 2.1 files.

Usage examples
--------------
  python main.py survey.segy                     # show headers + first trace stats
  python main.py survey.segy --traces 0 5        # print headers for traces 0-4
  python main.py survey.segy --trace 12          # inspect a single trace in detail
  python main.py survey.segy --no-textual        # skip textual header
"""

import argparse
import sys
import numpy as np

# Ensure the terminal can handle Unicode (important on Windows)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from segy21 import SegyReader


def fmt_array_stats(data: np.ndarray) -> str:
    if len(data) == 0:
        return "empty"
    return (
        f"min={data.min():.6g}  max={data.max():.6g}  "
        f"mean={data.mean():.6g}  std={data.std():.6g}"
    )


def print_separator(char: str = "-", width: int = 72) -> None:
    print(char * width)


def cmd_info(reader: SegyReader, args) -> None:
    """Default command: print file headers and summary stats."""

    if not args.no_textual:
        print_separator("=")
        print("TEXTUAL FILE HEADER")
        print_separator("=")
        print(f"  Encoding: {reader.textual_header.encoding}")
        print_separator()
        print(reader.textual_header)
        print()

    for i, ext in enumerate(reader.extended_textual_headers, 1):
        print_separator("=")
        print(f"EXTENDED TEXTUAL HEADER #{i}")
        print_separator("=")
        print(ext)
        print()

    print_separator("=")
    print("BINARY FILE HEADER")
    print_separator("=")
    print(reader.binary_header.summary())
    print()

    n = reader.num_traces()
    print_separator()
    print(f"Estimated trace count : {n if n >= 0 else 'unknown'}")
    print_separator()

    # Show first few traces
    max_show = args.traces if args.traces else 3
    print(f"\nFirst {max_show} trace(s):\n")
    for i, (hdr, data) in enumerate(reader.traces(stop=max_show)):
        print(f"  [Trace {i}]")
        print(hdr.summary(verbose=True))
        print(f"  {'Samples':<28}: {len(data)}")
        print(f"  {'Data stats':<28}: {fmt_array_stats(data)}")
        print()


def cmd_trace(reader: SegyReader, args) -> None:
    """Print detailed info for a specific trace."""
    idx = args.trace
    try:
        hdr, data = reader.read_trace(idx)
    except IndexError:
        print(f"Error: trace index {idx} not found.", file=sys.stderr)
        sys.exit(1)

    print_separator("=")
    print(f"TRACE {idx} — HEADER")
    print_separator("=")
    for key, val in hdr.fields.items():
        if val != 0:  # skip zero-valued fields for readability
            print(f"  {key:<35}: {val}")

    print()
    print_separator("=")
    print(f"TRACE {idx} — DATA  ({len(data)} samples)")
    print_separator("=")
    print(f"  Stats : {fmt_array_stats(data)}")
    if args.samples:
        n = min(args.samples, len(data))
        print(f"  First {n} samples:")
        for i, v in enumerate(data[:n]):
            print(f"    [{i:6d}] {v:.8g}")


def cmd_trace_range(reader: SegyReader, args) -> None:
    """Print headers for a range of traces."""
    start, stop = args.traces
    for i, (hdr, data) in enumerate(reader.traces(start=start, stop=stop), start=start):
        print(f"[Trace {i}]")
        print(hdr.summary(verbose=False))
        print(f"  stats: {fmt_array_stats(data)}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SEG-Y 2.1 file inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", help="Path to SEG-Y file")
    parser.add_argument("--no-textual", action="store_true",
                        help="Skip printing the textual header")
    parser.add_argument("--trace", type=int, default=None, metavar="N",
                        help="Show detailed info for trace N (0-indexed)")
    parser.add_argument("--traces", type=int, nargs="+", metavar="N",
                        help="Show N traces from start (1 arg), or range START STOP (2 args)")
    parser.add_argument("--samples", type=int, default=None, metavar="N",
                        help="With --trace: print first N sample values")

    args = parser.parse_args()

    try:
        with SegyReader(args.file) as reader:
            if args.trace is not None:
                cmd_trace(reader, args)
            elif args.traces and len(args.traces) == 2:
                args.traces = (args.traces[0], args.traces[1])
                cmd_trace_range(reader, args)
            else:
                if args.traces and len(args.traces) == 1:
                    args.traces = args.traces[0]
                cmd_info(reader, args)
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
