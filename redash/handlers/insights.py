from flask import request
from funcy import project

from redash import models
from redash.handlers.base import (
    BaseResource,
    get_object_or_404,
    require_fields,
)
from redash.permissions import (
    require_access,
    require_admin_or_owner,
    require_permission,
    view_only,
)
from redash.serializers import serialize_insight_definition
from redash.tasks.insights import check_insight_definition


class InsightResource(BaseResource):
    def get(self, insight_id):
        insight = get_object_or_404(models.InsightDefinition.get_by_id_and_org, insight_id, self.current_org)
        require_access(insight, self.current_user, view_only)
        self.record_event({"action": "view", "object_id": insight.id, "object_type": "insight"})
        return serialize_insight_definition(insight, with_results=True)

    def post(self, insight_id):
        req = request.get_json(True)
        params = project(req, ("options", "name", "query_id", "analysis_perspective"))
        insight = get_object_or_404(models.InsightDefinition.get_by_id_and_org, insight_id, self.current_org)
        require_admin_or_owner(insight.user.id)

        self.update_model(insight, params)
        models.db.session.commit()

        self.record_event({"action": "edit", "object_id": insight.id, "object_type": "insight"})
        return serialize_insight_definition(insight)

    def delete(self, insight_id):
        insight = get_object_or_404(models.InsightDefinition.get_by_id_and_org, insight_id, self.current_org)
        require_admin_or_owner(insight.user_id)
        models.db.session.delete(insight)
        models.db.session.commit()
        self.record_event({"action": "delete", "object_id": insight_id, "object_type": "insight"})


class InsightEvaluateResource(BaseResource):
    def post(self, insight_id):
        insight = get_object_or_404(models.InsightDefinition.get_by_id_and_org, insight_id, self.current_org)
        require_admin_or_owner(insight.user.id)
        check_insight_definition.delay(insight.id)
        self.record_event({"action": "evaluate", "object_id": insight.id, "object_type": "insight"})
        return {"ok": True}


class InsightListResource(BaseResource):
    def post(self):
        req = request.get_json(True)
        require_fields(req, ("options", "name", "query_id", "analysis_perspective"))

        query = models.Query.get_by_id_and_org(req["query_id"], self.current_org)
        require_access(query, self.current_user, view_only)

        insight = models.InsightDefinition(
            name=req["name"],
            analysis_perspective=req.get("analysis_perspective") or "",
            query_rel=query,
            user=self.current_user,
            options=req["options"],
        )

        models.db.session.add(insight)
        models.db.session.commit()

        self.record_event({"action": "create", "object_id": insight.id, "object_type": "insight"})
        return serialize_insight_definition(insight)

    @require_permission("list_insights")
    def get(self):
        self.record_event({"action": "list", "object_type": "insight"})
        return [
            serialize_insight_definition(insight)
            for insight in models.InsightDefinition.all(group_ids=self.current_user.group_ids)
        ]
