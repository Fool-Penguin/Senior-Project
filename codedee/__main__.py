#!/usr/bin/env python3
"""CodeDEE CLI.

    python -m codedee scan <path> [--json out.json] [--csv out.csv]
    python -m codedee graphs <path> [--json out.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from codedee.scan import dump_json, scan_graphs, scan_maintainability, write_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeDEE maintainability + graph IR scanner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Function-level maintainability metrics")
    p_scan.add_argument("path")
    p_scan.add_argument("--json", dest="json_out")
    p_scan.add_argument("--csv", dest="csv_out")

    p_g = sub.add_parser("graphs", help="Task 6: AST vs CFG vs DFG vs call graph")
    p_g.add_argument("path")
    p_g.add_argument("--json", dest="json_out")

    args = parser.parse_args()
    target = Path(args.path)
    if not target.exists():
        print(f"Path not found: {target}")
        return 1

    if args.cmd == "scan":
        report = scan_maintainability(target)
        print(
            f"Scanned {report['files_scanned']} files, {report['functions']} functions, "
            f"{report['functions_with_findings']} with findings ({report['scan_seconds']}s)"
        )
        if args.json_out:
            dump_json(report, Path(args.json_out))
            print(f"Wrote {args.json_out}")
        if args.csv_out:
            write_csv(report["records"], Path(args.csv_out))
            print(f"Wrote {args.csv_out}")
        if not args.json_out and not args.csv_out:
            top = sorted(
                report["records"],
                key=lambda r: (r["cognitive"], r["cyclomatic"]),
                reverse=True,
            )[:15]
            print(json.dumps(top, indent=2))
        return 0

    report = scan_graphs(target)
    text = json.dumps(report, indent=2)
    if args.json_out:
        dump_json(report, Path(args.json_out))
        print(f"Wrote {args.json_out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
