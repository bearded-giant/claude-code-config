#!/usr/bin/env python3
"""merge regex categorization with LLM worker results.

reads the regex output CSV, then overlays LLM classifications for
rows that were below the confidence threshold.
"""
import csv
import json
import sys
import argparse
from collections import Counter, defaultdict
from pathlib import Path


def load_worker_files(workers_dir):
    """load all batch-*.json worker outputs, return {global_row: classification}."""
    categorizations = {}
    failed_batches = []

    for f in sorted(Path(workers_dir).glob("batch-*.json")):
        batch_idx = int(f.stem.split("-")[1])
        try:
            data = json.loads(f.read_text())
            for item in data:
                global_row = item.get("global_row", item.get("row"))
                if global_row:
                    categorizations[int(global_row)] = item
        except (json.JSONDecodeError, KeyError) as e:
            failed_batches.append({"batch": batch_idx, "error": str(e)})

    return categorizations, failed_batches


def main():
    parser = argparse.ArgumentParser(description="merge regex + LLM categorizations")
    parser.add_argument("--regex-csv", required=True, help="output from categorize.py")
    parser.add_argument("--workers-dir", required=True, help="dir with batch-*.json from LLM workers")
    parser.add_argument("--output-csv", required=True, help="final merged output")
    args = parser.parse_args()

    llm_cats, failed_batches = load_worker_files(args.workers_dir)

    rows = []
    with open(args.regex_csv) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            if i in llm_cats:
                llm = llm_cats[i]
                row["type"] = llm.get("type", row["type"])
                row["method"] = llm.get("method", row["method"])
                row["confidence"] = llm.get("confidence", row["confidence"])
            rows.append(row)

    with open(args.output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["project", "file", "line", "ref", "type", "method", "confidence", "snippet"])
        for r in rows:
            writer.writerow([
                r["project"], r["file"], r["line"], r["ref"],
                r["type"], r["method"], r["confidence"], r["snippet"],
            ])

    type_counts = Counter(r["type"] for r in rows)
    method_counts = defaultdict(lambda: Counter())
    confidences = []
    for r in rows:
        c = float(r["confidence"])
        confidences.append(c)
        if r["method"]:
            method_counts[r["method"]][r["type"]] += 1

    low_conf = sum(1 for c in confidences if c < 0.7)
    total = len(rows)

    top_methods = sorted(method_counts.items(), key=lambda x: sum(x[1].values()), reverse=True)[:10]
    top_methods_out = []
    for method, tcounts in top_methods:
        t = sum(tcounts.values())
        breakdown = ", ".join(f"{cnt} {tp}" for tp, cnt in tcounts.most_common())
        top_methods_out.append({"method": method, "total": t, "breakdown": breakdown})

    summary = {
        "total_rows": total,
        "regex_kept": total - len(llm_cats),
        "llm_classified": len(llm_cats),
        "llm_failed_batches": failed_batches,
        "types": [{"type": t, "count": c, "pct": round(c / total * 100, 1)}
                  for t, c in type_counts.most_common()],
        "low_confidence_count": low_conf,
        "low_confidence_pct": round(low_conf / total * 100, 1) if total else 0,
        "unique_methods": len(method_counts),
        "top_methods": top_methods_out,
        "output_csv": args.output_csv,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
