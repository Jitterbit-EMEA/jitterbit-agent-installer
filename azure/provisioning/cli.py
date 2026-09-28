"""Callable CLI for external orchestration. Mutations require explicit --execute."""

import argparse
import json
import sys

import yaml

from .adapter import DeploymentError, Provisioner, load_yaml, plan


def main(argv=None):
    parser = argparse.ArgumentParser(prog="jbpa-azure")
    parser.add_argument(
        "operation", choices=["plan", "provision", "deploy-jbpa", "execute", "status", "destroy"]
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--state-file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.config) as stream:
            config = load_yaml(stream.read())
        if (
            args.operation == "plan"
            or args.plan
            or (args.operation in {"provision", "execute", "deploy-jbpa"} and not args.execute)
        ):
            result = plan(config)
        else:
            if not args.state_file:
                raise DeploymentError("AZURE_STATE_FILE_REQUIRED")
            adapter = Provisioner(config)
            if args.operation == "status":
                result = adapter.status(args.state_file)
            elif args.operation == "destroy":
                result = adapter.destroy(args.state_file, execute=args.execute)
            elif args.operation == "deploy-jbpa":
                result = adapter.deploy(args.state_file, execute=True)
            else:
                result = adapter.provision(args.state_file, execute=True)
                if args.operation == "execute" and result["status"] == "SUCCESS":
                    result = adapter.deploy(args.state_file, execute=True)
        code = 0 if result["status"] == "SUCCESS" else 1
    except DeploymentError as error:
        result = {
            "schemaVersion": "1.0",
            "status": "FAILED",
            "operation": args.operation.upper(),
            "error": {"category": error.code},
        }
        code = 1
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        result = {
            "schemaVersion": "1.0",
            "status": "FAILED",
            "operation": args.operation.upper(),
            "error": {"category": "AZURE_CONFIG_INVALID"},
        }
        code = 1
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
