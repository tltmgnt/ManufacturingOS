"""Installed command router; component parsers retain their existing behavior."""
import argparse
from importlib import import_module

from ._version import __version__

COMMANDS = {
    "plan": ("__main__", "Run deterministic mock-agent planning"),
    "estimate": ("calculations", "Calculate serial-route capacity, cost, and yield"),
    "experiment": ("experiments", "Sample uncertainty or validate arithmetic references"),
    "simulate": ("simulation", "Simulate a finite batch through a serial route"),
    "study": ("study", "Run a revision-bound integrated study"),
    "review": ("review", "Export an offline HTML study review"),
    "compare": ("compare", "Compare two reconstructable study reports"),
    "bundle": ("bundle", "Create or verify a portable study bundle"),
    "evidence": ("evidence", "Check evidence freshness and pinned source metadata"),
    "sources": ("sources", "Verify captured evidence bytes against declared hashes"),
    "capture": ("capture", "Capture manifest-selected files into a source snapshot"),
    "notes": ("notes", "Record or check revision-bound reviewer feedback"),
    "replicate": ("replications", "Repeat finite-batch simulation across recorded seeds"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="manufacturing-os", description="Advisory manufacturing studies; models are unvalidated and approvals remain pending.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Commands:\n"+"\n".join(f"  {name:12} {description}" for name, (_, description) in COMMANDS.items())+
               "\n\nUse manufacturing-os COMMAND --help for command arguments.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("command", nargs="?", choices=COMMANDS)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    module, _ = COMMANDS[args.command]
    return import_module(f"manufacturing_os.{module}").main(args.arguments)


if __name__ == "__main__":
    raise SystemExit(main())
