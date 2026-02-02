#!/usr/bin/env python3
"""split ambiguous CSV into batch files for LLM workers."""
import csv
import math
import json
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True, help="ambiguous.csv from categorize.py")
    parser.add_argument("--output-dir", required=True, help="directory for batch CSV files")
    parser.add_argument("--max-workers", type=int, default=10)
    args = parser.parse_args()

    rows = []
    with open(args.input_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print(json.dumps({"total": 0, "batches": 0, "batch_size": 0}))
        return

    total = len(rows)
    batch_size = math.ceil(total / min(args.max_workers, max(1, total // 10 or 1)))
    if batch_size < 10:
        batch_size = 10
    num_batches = math.ceil(total / batch_size)
    if num_batches > args.max_workers:
        batch_size = math.ceil(total / args.max_workers)
        num_batches = math.ceil(total / batch_size)

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    for b in range(num_batches):
        start = b * batch_size
        end = min(start + batch_size, total)
        batch_rows = rows[start:end]

        batch_path = Path(args.output_dir) / f"batch-{b+1}.csv"
        with open(batch_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["global_row", "project", "file", "line", "ref", "snippet"])
            for row in batch_rows:
                writer.writerow([
                    row["row"], row["project"], row["file"],
                    row["line"], row["ref"], row["snippet"],
                ])

    print(json.dumps({
        "total": total,
        "batches": num_batches,
        "batch_size": batch_size,
        "last_batch_size": end - (num_batches - 1) * batch_size,
        "files": [f"batch-{i+1}.csv" for i in range(num_batches)],
    }))


if __name__ == "__main__":
    main()
