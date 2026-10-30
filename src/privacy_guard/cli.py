import argparse
import os
from pathlib import Path

from .generator import generate_large_dataset, generate_medium_dataset, generate_sample_dataset
from .pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="PrivacyGuard privacy minimization pipeline")
    subparsers = parser.add_subparsers(dest="command")

    sample_parser = subparsers.add_parser("generate-sample", help="Generate a small synthetic customer dataset")
    sample_parser.add_argument("--output-path", default="data/raw/customers.csv")

    medium_parser = subparsers.add_parser("generate-medium", help="Generate a medium synthetic customer dataset")
    medium_parser.add_argument("--output-path", default="data/raw/customers_medium.csv")

    large_parser = subparsers.add_parser("generate-large", help="Generate a large synthetic customer dataset")
    large_parser.add_argument("--output-path", default="data/raw/customers_large.csv")

    process_parser = subparsers.add_parser("process", help="Run the privacy pipeline")
    process_parser.add_argument("--input", default="data/raw/customers.csv")
    process_parser.add_argument("--config", default="config/pipeline.yaml")

    benchmark_parser = subparsers.add_parser("benchmark", help="Run a benchmark across sample sizes")
    benchmark_parser.add_argument("--config", default="config/pipeline.yaml")

    args = parser.parse_args()

    if args.command == "generate-sample":
        generate_sample_dataset(Path(args.output_path))
        print(f"Generated sample dataset at {args.output_path}")
        return

    if args.command == "generate-medium":
        generate_medium_dataset(Path(args.output_path))
        print(f"Generated medium dataset at {args.output_path}")
        return

    if args.command == "generate-large":
        generate_large_dataset(Path(args.output_path))
        print(f"Generated large dataset at {args.output_path}")
        return

    if args.command == "process":
        result = run_pipeline(Path(args.input), Path(args.config))
        print(f"Run complete: {result['run_id']}")
        print(f"Valid rows: {result['reconciliation']['valid_rows']}")
        print(f"Rejected rows: {result['reconciliation']['rejected_rows']}")
        print(f"Output parquet: {result['output_path']}")
        return

    if args.command == "benchmark":
        from .pipeline import benchmark_pipeline
        benchmark_pipeline(Path(args.config))
        print("Benchmark complete")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
