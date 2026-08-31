from flask import request
from flask_restful import abort
from funcy import project

from redash import models
from redash.handlers.base import BaseResource, get_object_or_404, require_fields
from redash.permissions import require_access, require_permission, view_only


class AiInstructionListResource(BaseResource):
    @require_permission("create_query")
    def get(self):
        data_source_id = request.args.get("data_source_id")
        if not data_source_id:
            abort(400, message="data_source_id is required.")

        data_source = get_object_or_404(models.DataSource.get_by_id_and_org, data_source_id, self.current_org)
        require_access(data_source, self.current_user, view_only)

        instructions = (
            models.AiInstruction.query.filter(
                models.AiInstruction.data_source_id == data_source.id,
                models.AiInstruction.org_id == self.current_org.id,
            )
            .order_by(models.AiInstruction.updated_at.desc())
            .all()
        )
        return [instruction.to_dict() for instruction in instructions]

    @require_permission("create_query")
    def post(self):
        req = request.get_json(True) or {}
        require_fields(req, ("data_source_id", "content"))

        content = (req.get("content") or "").strip()
        title = (req.get("title") or "").strip() or None
        if not content:
            abort(400, message="ルール内容を入力してください。")

        data_source = get_object_or_404(models.DataSource.get_by_id_and_org, req["data_source_id"], self.current_org)
        require_access(data_source, self.current_user, view_only)

        instruction = models.AiInstruction(
            org=self.current_org,
            data_source=data_source,
            user=self.current_user,
            title=title,
            content=content,
        )
        models.db.session.add(instruction)
        models.db.session.commit()

        self.record_event({"action": "create", "object_id": instruction.id, "object_type": "ai_instruction"})
        return instruction.to_dict()


class AiInstructionResource(BaseResource):
    @require_permission("create_query")
    def delete(self, instruction_id):
        instruction = get_object_or_404(models.AiInstruction.get_by_id_and_org, instruction_id, self.current_org)
        require_access(instruction.data_source, self.current_user, view_only)

        models.db.session.delete(instruction)
        models.db.session.commit()

        self.record_event({"action": "delete", "object_id": instruction_id, "object_type": "ai_instruction"})
        return {"ok": True}

    @require_permission("create_query")
    def post(self, instruction_id):
        instruction = get_object_or_404(models.AiInstruction.get_by_id_and_org, instruction_id, self.current_org)
        require_access(instruction.data_source, self.current_user, view_only)

        req = request.get_json(True) or {}
        params = project(req, ("title", "content"))

        content = (params.get("content") or instruction.content).strip()
        title = params.get("title")
        if title is not None:
            title = title.strip() or None
        else:
            title = instruction.title

        if not content:
            abort(400, message="ルール内容を入力してください。")

        instruction.title = title
        instruction.content = content
        models.db.session.add(instruction)
        models.db.session.commit()

        self.record_event({"action": "edit", "object_id": instruction.id, "object_type": "ai_instruction"})
        return instruction.to_dict()
