"""Offline checks of the escalation and Bedrock guarantees these policies are meant to give.

uv run --no-project --with pytest pytest infra/aws/iam -q
"""

import json
from fnmatch import fnmatchcase
from pathlib import Path

HERE = Path(__file__).parent
BOUNDARY = "arn:aws:iam::${aws:PrincipalAccount}:policy/Boundary-MiniEyes-Workload"
PROJECT_IAM = (
    "arn:aws:iam::*:role/minieyes-*",
    "arn:aws:iam::*:policy/minieyes-*",
    "arn:aws:iam::*:instance-profile/minieyes-*",
    "arn:aws:iam::*:oidc-provider/token.actions.githubusercontent.com",
    "arn:aws:iam::*:role/aws-service-role/*",
)
IAM_READ = ("iam:Get", "iam:List")
NO_AI = {"bedrock:*", "bedrock-agentcore:*", "sagemaker:*", "aws-marketplace:*"}


def statements(name):
    return json.loads((HERE / name).read_text())["Statement"]


def as_list(value):
    return value if isinstance(value, list) else [value]


def deployer_allows():
    for name in ("deployer-infra.json", "deployer-iam.json"):
        yield from (s for s in statements(name) if s["Effect"] == "Allow")


def test_deployer_allows_iam_writes_only_on_project_resources():
    for s in deployer_allows():
        actions = as_list(s["Action"])
        if any(a.startswith("iam:") and not a.startswith(IAM_READ) for a in actions):
            assert all(r in PROJECT_IAM for r in as_list(s["Resource"])), s["Sid"]


def test_role_permission_changes_require_the_workload_boundary():
    gated = {
        "iam:CreateRole",
        "iam:PutRolePermissionsBoundary",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
    }
    for s in deployer_allows():
        if gated & set(as_list(s["Action"])):
            assert s["Condition"]["StringEquals"]["iam:PermissionsBoundary"] == BOUNDARY, s["Sid"]


def test_guardrails_deny_iam_writes_everywhere_else_and_boundary_removal():
    by_sid = {s["Sid"]: s for s in statements("deployer-guardrails.json")}
    assert set(by_sid["IamWritesOnlyOnProjectResources"]["NotResource"]) == set(PROJECT_IAM)
    assert by_sid["BoundaryCannotBeRemoved"]["Action"] == "iam:DeleteRolePermissionsBoundary"
    assert "sts:AssumeRole" in by_sid["NoAssumingOtherRoles"]["Action"]


def test_the_deployer_and_the_devbox_role_names_are_outside_their_own_reach():
    for name in (
        "Deployer-MiniEyes-Infra",
        "Deployer-MiniEyes-Iam",
        "Deployer-MiniEyes-Guardrails",
        "Boundary-MiniEyes-Workload",
    ):
        arn = f"arn:aws:iam::123456789012:policy/{name}"
        assert not any(fnmatchcase(arn.lower(), p.lower()) for p in PROJECT_IAM), name
    role = "arn:aws:iam::123456789012:role/DevBox-MiniEyes-Claude"
    assert not any(fnmatchcase(role.lower(), p.lower()) for p in PROJECT_IAM)


def test_the_boundary_grants_no_iam_write_except_the_load_balancer_service_linked_role():
    for s in (s for s in statements("workload-boundary.json") if s["Effect"] == "Allow"):
        for a in as_list(s["Action"]):
            if a.startswith("iam:") and not a.startswith(IAM_READ):
                assert a == "iam:CreateServiceLinkedRole"
                assert s["Condition"]["StringEquals"]["iam:AWSServiceName"] == (
                    "elasticloadbalancing.amazonaws.com"
                )


def test_bedrock_and_other_paid_ai_are_denied_for_the_deployer_and_every_project_role():
    for name in ("deployer-guardrails.json", "workload-boundary.json"):
        denies = [s for s in statements(name) if s["Effect"] == "Deny"]
        denied = {a for s in denies for a in as_list(s.get("Action", []))}
        assert denied >= NO_AI, name


def test_no_allow_statement_grants_a_bare_wildcard():
    for name in ("deployer-infra.json", "deployer-iam.json", "workload-boundary.json"):
        for s in (s for s in statements(name) if s["Effect"] == "Allow"):
            assert "*" not in as_list(s["Action"]), (name, s["Sid"])
            assert not any(a.startswith(("bedrock", "sagemaker")) for a in as_list(s["Action"]))
