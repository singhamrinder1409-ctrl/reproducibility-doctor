"""Controlled stale-input tests using an existing real approval and private input copies.

Targets never execute in these cases. Pre-staging cases use real Docker metadata
calls, with a fail-stop guard forbidding container creation if rejection fails.
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from reprodoctor.execution import Docker, _record, execute_plan
from reprodoctor.intake import IntakeError
from reprodoctor.planning import read_document, validate_approval, validate_plan
from reprodoctor.snapshot import load_snapshot


def validate(args):
    if not args.execute_approved_tests:
        raise ValueError("Explicit --execute-approved-tests required")
    if sys.flags.optimize:
        raise ValueError("Run validation harnesses without Python -O")
    plan = validate_plan(read_document(args.plan), args.snapshot, wheelhouse=args.wheelhouse)
    approval = read_document(args.approval)
    validate_approval(approval, plan)
    for source in (args.snapshot, args.wheelhouse):
        if args.output.resolve().is_relative_to(source.resolve()):
            raise ValueError("Output must be outside inputs")
    args.output.mkdir(mode=0o700)
    rows = []
    for target in ("source", "wheel"):
        for stage in ("before-validation", "before-staging"):
            name = target + "-" + stage
            with tempfile.TemporaryDirectory(prefix="doctor-mutation-validation-") as temporary:
                root = Path(temporary)
                snapshot, wheels = root / "snapshot", root / "wheels"
                shutil.copytree(args.snapshot, snapshot, symlinks=True)
                shutil.copytree(args.wheelhouse, wheels, symlinks=True)
                validate_plan(plan, snapshot, wheelhouse=wheels)
                _, contents = load_snapshot(snapshot)
                selected = next(path for path in contents if path.endswith(".py"))
                events = {
                    "backend_created": False,
                    "mutated": False,
                    "real_metadata_calls": 0,
                    "container_create_attempts": 0,
                }

                def mutate():
                    path = (
                        snapshot / "files" / selected
                        if target == "source"
                        else wheels / plan["payload"]["artifacts"]["files"][0]["name"]
                    )
                    if path.is_symlink():
                        raise ValueError("Refusing to mutate symlink")
                    path.chmod(path.stat().st_mode | 0o200)
                    with path.open("ab") as stream:
                        stream.write(b"\n# authored input mutation probe\n")
                    events["mutated"] = True

                def forbidden_backend(*args, **kwargs):
                    events["backend_created"] = True
                    raise AssertionError("Backend touched before stale-input rejection")

                class MutationObserver(Docker):
                    def __init__(self, *args, **kwargs):
                        events["backend_created"] = True
                        super().__init__(*args, **kwargs)

                    def document(self, command, **kwargs):
                        result = super().document(command, **kwargs)
                        events["real_metadata_calls"] += 1
                        if command[:2] == ["image", "inspect"] and not events["mutated"]:
                            mutate()
                        return result

                    def command(self, command, **kwargs):
                        if command[:2] == ["container", "create"]:
                            events["container_create_attempts"] += 1
                            raise AssertionError(
                                "Fail-stop: mutated input reached container creation"
                            )
                        return super().command(command, **kwargs)

                output = args.output / (name + ".json")
                if stage == "before-validation":
                    mutate()
                    try:
                        execute_plan(
                            plan,
                            approval,
                            snapshot,
                            output,
                            wheelhouse=wheels,
                            socket=args.docker_socket,
                            docker_factory=forbidden_backend,
                            experimental=True,
                        )
                    except IntakeError as error:
                        result = {"outcome": "rejected_before_backend", "error": str(error)}
                    else:
                        raise AssertionError("Stale input was accepted")
                    assert not events["backend_created"] and not output.exists()
                else:
                    result = execute_plan(
                        plan,
                        approval,
                        snapshot,
                        output,
                        wheelhouse=wheels,
                        socket=args.docker_socket,
                        docker_factory=MutationObserver,
                        experimental=True,
                    )
                    assert events["real_metadata_calls"] >= 2
                    assert result["execution_status"] == "infrastructure_error"
                    assert result["steps"] == [] and result["cleanup"]["status"] == "not_needed"
                    assert (
                        "snapshot" in result["error"].lower() or "wheel" in result["error"].lower()
                    )
                assert events["mutated"] and events["container_create_attempts"] == 0
                rows.append(
                    {
                        "case": name,
                        "events": events,
                        "outcome": result.get("outcome", result.get("execution_status")),
                        "error": result.get("error"),
                        "target_executed": False,
                    }
                )
                print(name + " rejected", flush=True)
    validate_plan(plan, args.snapshot, wheelhouse=args.wheelhouse)
    summary = {
        "schema_version": 1,
        "kind": "approved_input_mutation_validation",
        "plan_digest": plan["plan_digest"],
        "cases": rows,
        "original_inputs_unchanged": True,
        "limitations": [
            "These are controlled copy mutations with a host-side observer.",
            "No target code or container was created in these cases.",
            "Real Docker server/image metadata was used before staging mutations.",
            "This is not proof against arbitrary concurrent malicious host changes.",
        ],
    }
    _record(args.output / "summary.json", summary, new=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "snapshot", "approval", "wheelhouse", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--docker-socket", required=True)
    parser.add_argument("--execute-approved-tests", action="store_true")
    print(json.dumps(validate(parser.parse_args()), indent=2))


if __name__ == "__main__":
    main()
