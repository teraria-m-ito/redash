from flask import request
from flask_restful import abort
from funcy import project

from redash import models
from redash.handlers.base import BaseResource, get_object_or_404, require_fields
from redash.permissions import require_access, require_permission, view_only


class AiSqlPairListResource(BaseResource):
    @require_permission("create_query")
    def get(self):
        data_source_id = request.args.get("data_source_id")
        if not data_source_id:
            abort(400, message="data_source_id is required.")

        data_source = get_object_or_404(models.DataSource.get_by_id_and_org, data_source_id, self.current_org)
        require_access(data_source, self.current_user, view_only)

        pairs = (
            models.AiSqlPair.query.filter(
                models.AiSqlPair.data_source_id == data_source.id,
                models.AiSqlPair.org_id == self.current_org.id,
            )
            .order_by(models.AiSqlPair.updated_at.desc())
            .all()
        )
        return [pair.to_dict() for pair in pairs]

    @require_permission("create_query")
    def post(self):
        req = request.get_json(True) or {}
        require_fields(req, ("data_source_id", "question", "query"))

        question = (req.get("question") or "").strip()
        query = (req.get("query") or "").strip()
        if not question:
            abort(400, message="質問を入力してください。")
        if not query:
            abort(400, message="クエリを入力してください。")

        data_source = get_object_or_404(models.DataSource.get_by_id_and_org, req["data_source_id"], self.current_org)
        require_access(data_source, self.current_user, view_only)

        pair = models.AiSqlPair(
            org=self.current_org,
            data_source=data_source,
            user=self.current_user,
            question=question,
            query=query,
        )
        models.db.session.add(pair)
        models.db.session.commit()

        self.record_event({"action": "create", "object_id": pair.id, "object_type": "ai_sql_pair"})
        return pair.to_dict()


class AiSqlPairResource(BaseResource):
    @require_permission("create_query")
    def delete(self, pair_id):
        pair = get_object_or_404(models.AiSqlPair.get_by_id_and_org, pair_id, self.current_org)
        require_access(pair.data_source, self.current_user, view_only)

        models.db.session.delete(pair)
        models.db.session.commit()

        self.record_event({"action": "delete", "object_id": pair_id, "object_type": "ai_sql_pair"})
        return {"ok": True}

    @require_permission("create_query")
    def post(self, pair_id):
        pair = get_object_or_404(models.AiSqlPair.get_by_id_and_org, pair_id, self.current_org)
        require_access(pair.data_source, self.current_user, view_only)

        req = request.get_json(True) or {}
        params = project(req, ("question", "query"))

        question = (params.get("question") or pair.question).strip()
        query = (params.get("query") or pair.query).strip()
        if not question:
            abort(400, message="質問を入力してください。")
        if not query:
            abort(400, message="クエリを入力してください。")

        pair.question = question
        pair.query = query
        models.db.session.add(pair)
        models.db.session.commit()

        self.record_event({"action": "edit", "object_id": pair.id, "object_type": "ai_sql_pair"})
        return pair.to_dict()
