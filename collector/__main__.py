import argparse

from collector.run import load_env_secrets, main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="collector")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_env_secrets()
    raise SystemExit(main(dry_run=args.dry_run))
