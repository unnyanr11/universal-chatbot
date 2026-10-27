"""Durable, bounded JSON workflows over an explicit set of local operations."""

import json
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from . import booking
from .context import database, identity, project_scope, require_writer
from .database import Assistant, AuditEvent, Operation, Workflow, WorkflowRun, WorkflowVersion
from .knowledge import retrieve

router = APIRouter(prefix="/v1/projects/{project_id}")


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal[
        "collect",
        "validate",
        "branch",
        "knowledge",
        "services",
        "slots",
        "propose_booking",
        "confirmation",
        "end",
    ]
    key: str = Field(default="input", pattern=r"^[a-z][a-zA-Z0-9_]{0,39}$")
    label: str = Field(default="", max_length=200)
    value_type: Literal["string", "integer", "boolean"] = "string"
    arguments: dict[str, str | int | bool] = Field(default_factory=dict, max_length=8)
    equals: str | int | bool = ""
    target: int | None = Field(default=None, ge=0)


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    nodes: list[Node] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_graph(self):
        if self.nodes[-1].type != "end":
            raise ValueError("The final node must end the workflow")
        fields = set()
        for index, node in enumerate(self.nodes):
            if node.type == "collect":
                if node.key in fields:
                    raise ValueError("Input fields must be unique")
                fields.add(node.key)
            if node.type == "branch" and (
                node.target is None or not index < node.target < len(self.nodes)
            ):
                raise ValueError("Branches must target a later node; cycles are not allowed")
            if any(len(str(v)) > 4000 for v in node.arguments.values()):
                raise ValueError("Argument exceeds input budget")
        return self


class StartRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=100)
    dry_run: bool = True


class ResumeRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    value: str | int | bool | None = None
    approve: bool = False


def own_run(db, run_id, project_id, user_id):
    run = db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.project_id == project_id,
            WorkflowRun.user_id == user_id,
        )
    )
    if not run:
        raise HTTPException(404, "WORKFLOW_RUN_NOT_FOUND")
    return run


def run_record(db, run):
    definition = Definition.model_validate_json(
        db.get(WorkflowVersion, run.workflow_version_id).definition
    )
    current = definition.nodes[run.cursor] if run.cursor < len(definition.nodes) else None
    result = {
        "id": run.id,
        "state": run.state,
        "cursor": run.cursor,
        "revision": run.revision,
        "dry_run": run.dry_run,
        "variables": json.loads(run.variables),
        "trace": json.loads(run.trace),
        "next": current.model_dump() if current else None,
    }
    op_id = result["variables"].get("_operation")
    if op_id:
        op = db.get(Operation, op_id)
        if op and op.user_id == run.user_id and op.project_id == run.project_id:
            result["approval"] = booking.receipt(db, op)
    return result


def resolve_arguments(arguments, variables):
    result = {}
    for key, value in arguments.items():
        if isinstance(value, str) and value.startswith("$"):
            if value[1:] not in variables:
                raise ValueError("MISSING_VARIABLE_" + value[1:])
            result[key] = variables[value[1:]]
        else:
            result[key] = value
    return result


def drive(db, run, scope, session, revision, value=None, approve=False, initial=False):
    now = int(time.time())
    if run.state in {"succeeded", "failed", "cancelled"}:
        return run_record(db, run)
    if run.state == "running" and run.lease_until >= now:
        raise HTTPException(409, "WORKFLOW_BUSY")
    claimed = db.execute(
        update(WorkflowRun)
        .where(WorkflowRun.id == run.id, WorkflowRun.revision == revision)
        .values(state="running", revision=WorkflowRun.revision + 1, lease_until=now + 90)
        .returning(WorkflowRun.id)
    ).scalar_one_or_none()
    if not claimed:
        db.rollback()
        raise HTTPException(409, "WORKFLOW_CHANGED_REFRESH")
    db.commit()
    definition = Definition.model_validate_json(
        db.get(WorkflowVersion, run.workflow_version_id).definition
    )
    variables, trace = json.loads(run.variables), json.loads(run.trace)
    node = definition.nodes[run.cursor]
    try:
        if not initial and node.type == "collect":
            valid = {
                "string": type(value) is str and 0 < len(value) <= 4000,
                "integer": type(value) is int,
                "boolean": type(value) is bool,
            }[node.value_type]
            if not valid or approve:
                raise ValueError("INVALID_INPUT_TYPE")
            variables[node.key] = value
            run.cursor += 1
        elif not initial and node.type != "confirmation" and approve:
            raise ValueError("UNEXPECTED_APPROVAL")
        for _ in range(30):
            node = definition.nodes[run.cursor]
            arguments = resolve_arguments(node.arguments, variables)
            output = None
            if node.type == "collect":
                run.state = "waiting"
                break
            if node.type == "validate":
                if variables.get(node.key) != node.equals:
                    raise ValueError("VALIDATION_FAILED_" + node.key)
            elif node.type == "branch":
                if variables.get(node.key) == node.equals:
                    trace.append({"node": run.cursor, "type": node.type, "state": "branched"})
                    run.cursor = node.target
                    continue
            elif node.type == "services":
                output = booking.services(scope, db)["items"]
            elif node.type == "slots":
                output = booking.available_slots(str(arguments["service_id"]), scope, db)["items"]
            elif node.type == "knowledge":
                assistant = db.get(Assistant, arguments["assistant_id"])
                if not assistant or assistant.project_id != scope[0].id:
                    raise ValueError("ASSISTANT_NOT_FOUND")
                output = retrieve(db, assistant.id, str(arguments["query"]))
            elif node.type == "propose_booking":
                if run.dry_run:
                    output = {
                        "state": "simulated",
                        "arguments": arguments,
                        "notice": "Dry run; no appointment or action was created.",
                    }
                else:
                    op = booking.propose(
                        booking.Proposal(
                            kind="book",
                            slot_id=str(arguments["slot_id"]),
                            idempotency_key=f"workflow:{run.id}:{run.cursor}",
                        ),
                        scope,
                        session,
                        db,
                    )
                    variables["_operation"] = op["id"]
                    output = op
            elif node.type == "confirmation":
                if not approve:
                    run.state = "awaiting_confirmation"
                    break
                if run.dry_run:
                    output = {"state": "simulated", "notice": "Dry run; no booking executed."}
                else:
                    op_id = variables.get("_operation")
                    if not op_id:
                        raise ValueError("NO_PROPOSED_OPERATION")
                    output = booking.confirm(op_id, scope, session, db)
                    if output["state"] != "succeeded":
                        raise ValueError("BOOKING_" + output["state"].upper())
                approve = False
            elif node.type == "end":
                run.state = "succeeded"
                run.cursor += 1
                break
            if output is not None:
                variables[node.key] = output
            trace.append(
                {
                    "node": run.cursor,
                    "type": node.type,
                    "state": "simulated"
                    if run.dry_run and node.type in {"propose_booking", "confirmation"}
                    else "completed",
                }
            )
            run.cursor += 1
            run.variables, run.trace = json.dumps(variables), json.dumps(trace)
            db.commit()  # Each node is a recovery checkpoint; write tools use deterministic operation IDs.
        else:
            raise ValueError("WORKFLOW_STEP_BUDGET_EXHAUSTED")
    except (ValueError, KeyError, HTTPException) as exc:
        db.rollback()
        run = db.get(WorkflowRun, run.id)
        run.state = "failed"
        code = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
        trace.append(
            {"node": run.cursor, "type": node.type, "state": "failed", "error": code[:200]}
        )
    run.variables, run.trace, run.lease_until = json.dumps(variables), json.dumps(trace), 0
    db.commit()
    return run_record(db, run)


@router.get("/workflows")
def workflows(scope=Depends(project_scope), db=Depends(database)):
    return {
        "items": [
            {
                "id": w.id,
                "name": w.name,
                "versions": [
                    {"number": v.number, "definition": json.loads(v.definition)}
                    for v in db.scalars(
                        select(WorkflowVersion)
                        .where(WorkflowVersion.workflow_id == w.id)
                        .order_by(WorkflowVersion.number)
                    )
                ],
            }
            for w in db.scalars(
                select(Workflow).where(Workflow.project_id == scope[0].id).limit(100)
            )
        ]
    }


@router.post("/workflows", status_code=201)
def create_workflow(
    body: Definition, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    require_writer(scope)
    workflow = Workflow(project_id=scope[0].id, name=body.name)
    db.add(workflow)
    db.flush()
    db.add(WorkflowVersion(workflow_id=workflow.id, number=1, definition=body.model_dump_json()))
    db.add(
        AuditEvent(
            project_id=scope[0].id,
            actor_id=session.user_id,
            kind="workflow_created",
            object_id=workflow.id,
        )
    )
    db.commit()
    return {"id": workflow.id, "version": 1}


@router.post("/workflows/{workflow_id}/versions", status_code=201)
def version_workflow(
    workflow_id: str, body: Definition, scope=Depends(project_scope), db=Depends(database)
):
    require_writer(scope)
    workflow = db.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.project_id == scope[0].id)
    )
    if not workflow:
        raise HTTPException(404, "WORKFLOW_NOT_FOUND")
    number = (
        db.scalar(
            select(func.max(WorkflowVersion.number)).where(
                WorkflowVersion.workflow_id == workflow.id
            )
        )
        or 0
    ) + 1
    db.add(
        WorkflowVersion(workflow_id=workflow.id, number=number, definition=body.model_dump_json())
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "WORKFLOW_VERSION_CONFLICT") from None
    return {"version": number}


@router.post("/workflows/{workflow_id}/runs", status_code=201)
def start_run(
    workflow_id: str,
    body: StartRun,
    scope=Depends(project_scope),
    session=Depends(identity),
    db=Depends(database),
):
    version = db.scalar(
        select(WorkflowVersion)
        .join(Workflow)
        .where(
            Workflow.id == workflow_id,
            Workflow.project_id == scope[0].id,
            WorkflowVersion.number == body.version,
        )
    )
    if not version:
        raise HTTPException(404, "WORKFLOW_VERSION_NOT_FOUND")
    previous = db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.project_id == scope[0].id,
            WorkflowRun.user_id == session.user_id,
            WorkflowRun.idempotency_key == body.idempotency_key,
        )
    )
    if previous:
        if previous.workflow_version_id != version.id or previous.dry_run != body.dry_run:
            raise HTTPException(409, "IDEMPOTENCY_ARGUMENT_MISMATCH")
        return run_record(db, previous)
    run = WorkflowRun(
        project_id=scope[0].id,
        user_id=session.user_id,
        workflow_version_id=version.id,
        dry_run=body.dry_run,
        idempotency_key=body.idempotency_key,
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "CONCURRENT_RUN_RETRY_SAME_KEY") from None
    return drive(db, run, scope, session, run.revision, initial=True)


@router.get("/workflow-runs")
def runs(scope=Depends(project_scope), session=Depends(identity), db=Depends(database)):
    return {
        "items": [
            run_record(db, run)
            for run in db.scalars(
                select(WorkflowRun)
                .where(
                    WorkflowRun.project_id == scope[0].id, WorkflowRun.user_id == session.user_id
                )
                .limit(50)
            )
        ]
    }


@router.post("/workflow-runs/{run_id}/resume")
def resume(
    run_id: str,
    body: ResumeRun,
    scope=Depends(project_scope),
    session=Depends(identity),
    db=Depends(database),
):
    run = own_run(db, run_id, scope[0].id, session.user_id)
    return drive(db, run, scope, session, body.revision, body.value, body.approve)


@router.post("/workflow-runs/{run_id}/cancel")
def cancel(
    run_id: str,
    body: ResumeRun,
    scope=Depends(project_scope),
    session=Depends(identity),
    db=Depends(database),
):
    run = own_run(db, run_id, scope[0].id, session.user_id)
    changed = db.execute(
        update(WorkflowRun)
        .where(
            WorkflowRun.id == run.id,
            WorkflowRun.revision == body.revision,
            WorkflowRun.state.in_(["waiting", "awaiting_confirmation"]),
        )
        .values(state="cancelled", revision=WorkflowRun.revision + 1)
        .returning(WorkflowRun.id)
    ).scalar_one_or_none()
    if not changed:
        raise HTTPException(409, "WORKFLOW_NOT_CANCELLABLE_REFRESH")
    db.commit()
    return run_record(db, run)
