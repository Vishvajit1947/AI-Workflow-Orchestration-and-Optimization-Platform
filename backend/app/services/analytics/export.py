"""
Analytics Export Service.
Summary report (all aggregate sections) or raw stage runs, as CSV or JSON.
"""
import csv
import json
from datetime import datetime, timezone
from io import StringIO
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.analytics.aggregator import AnalyticsAggregator, AnalyticsFilter

Dataset = Literal["summary", "stage_runs"]


class AnalyticsExporter:
    def __init__(self, db: AsyncSession):
        self.aggregator = AnalyticsAggregator(db)

    async def summary(self, flt: AnalyticsFilter) -> dict:
        agg = self.aggregator
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "filters": {
                "start_date": flt.start_date.isoformat() if flt.start_date else None,
                "end_date": flt.end_date.isoformat() if flt.end_date else None,
                "workflow_id": str(flt.workflow_id) if flt.workflow_id else None,
            },
            "overview": await agg.get_workflow_metrics(flt),
            "cache": await agg.get_cache_metrics(flt),
            "latency": await agg.get_latency_metrics(flt),
            "routing": await agg.get_routing_effectiveness(flt),
            "models": await agg.get_model_utilization(flt),
            "stage_types": await agg.get_stage_type_metrics(flt),
            "cost_trend": await agg.get_cost_trend(flt),
            "token_trend": await agg.get_token_usage_trend(flt),
        }

    async def export_json(self, flt: AnalyticsFilter, dataset: Dataset = "summary") -> str:
        if dataset == "stage_runs":
            data = {"exported_at": datetime.now(timezone.utc).isoformat(),
                    "stage_runs": await self.aggregator.get_stage_runs(flt)}
        else:
            data = await self.summary(flt)
        return json.dumps(data, indent=2)

    async def export_csv(self, flt: AnalyticsFilter, dataset: Dataset = "summary") -> str:
        output = StringIO()
        writer = csv.writer(output)

        if dataset == "stage_runs":
            rows = await self.aggregator.get_stage_runs(flt)
            if rows:
                writer.writerow(rows[0].keys())
                writer.writerows(r.values() for r in rows)
            return output.getvalue()

        data = await self.summary(flt)
        # Key/value sections
        for section in ("overview", "cache", "latency"):
            writer.writerow([f"# {section}"])
            writer.writerow(["metric", "value"])
            writer.writerows(data[section].items())
            writer.writerow([])
        routing = {k: v for k, v in data["routing"].items() if not isinstance(v, (dict, list))}
        writer.writerow(["# routing"])
        writer.writerow(["metric", "value"])
        writer.writerows(routing.items())
        writer.writerow([])
        # Table sections
        for section in ("models", "stage_types", "cost_trend", "token_trend"):
            rows = data[section]
            writer.writerow([f"# {section}"])
            if rows:
                writer.writerow(rows[0].keys())
                writer.writerows(r.values() for r in rows)
            writer.writerow([])
        return output.getvalue()
