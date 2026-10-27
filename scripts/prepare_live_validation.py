"""Prepare authored live fixtures and plans. Never approves, installs or executes targets."""

import argparse
import json
from pathlib import Path

from evaluate import fixture_repository

from reprodoctor.extraction import encode_candidates
from reprodoctor.intake import intake
from reprodoctor.planning import build_plan

CASES = {
    "state-success": {
        "README.md": "# Configuration\n```sh\nexport DOCTOR_FIXTURE=reviewed\ncd app\n```\n"
        "# Run\n```sh\npython main.py\n```\n",
        "app/main.py": "import os\nfrom pathlib import Path\n"
        "assert os.environ['DOCTOR_FIXTURE'] == 'reviewed'\n"
        "assert Path.cwd() == Path('/workspace/app')\n"
        "print('DOCTOR_STATE_SUCCESS', flush=True)\n",
    },
    "failure-stops": {
        "README.md": "# Tests\n```sh\npython fail.py\npython later.py\n```\n",
        "fail.py": "print('DOCTOR_EXPECTED_FAILURE', flush=True)\nraise SystemExit(7)\n",
        "later.py": "raise RuntimeError('DOCTOR_LATER_STEP_MUST_NOT_START')\n",
    },
}


def prepare(output: Path, *, image: str | None = None, platform: str = "linux/amd64") -> dict:
    output.mkdir()  # New directory only; no existing inputs are overwritten.
    cases = []
    for name, files in CASES.items():
        base = output / name
        base.mkdir()
        fixture_repository(files, base / "source")
        intake(str(base / "source"), base / "snapshot")
        plan = build_plan(base / "snapshot", image=image, platform=platform)
        (base / "plan.json").write_text(encode_candidates(plan))
        cases.append(
            {
                "id": name,
                "plan_digest": plan["plan_digest"],
                "state": plan["payload"]["state"],
                "expected_execution_status": "completed" if name == "state-success" else "failed",
                "expected_exit_code": 0 if name == "state-success" else 7,
            }
        )
    manifest = {
        "schema_version": 1,
        "kind": "live_validation_preparation",
        "execution_status": "not_run",
        "approval_created": False,
        "image_verified": False,
        "cases": cases,
        "limitations": [
            "Preparation is not live validation. No container or fixture code ran.",
            "Read all source, plans and settings before interactive approval.",
            "Two basic fixtures do not satisfy the full containment checklist.",
        ],
    }
    (output / "preparation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", required=True, type=Path, help="New directory outside the checkout"
    )
    parser.add_argument(
        "--image", help="Explicit digest-pinned trusted local image; otherwise blocked drafts"
    )
    parser.add_argument("--platform", choices=["linux/amd64", "linux/arm64"], default="linux/amd64")
    args = parser.parse_args()
    print(encode_candidates(prepare(args.output, image=args.image, platform=args.platform)), end="")


if __name__ == "__main__":
    main()
