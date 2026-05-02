import datetime
import re

import numpy as np
import pandas as pd
from django.http import HttpResponseNotAllowed, JsonResponse

from apps.operation_logs.models import OperationLogs


GRANULARITY_TO_FREQ = {
    "hour": "h",
    "day": "D",
    "week": "W-MON",
    "month": "MS",
}


def _parse_datetime(value, field_name):
    if not value:
        return None

    try:
        parsed_value = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Invalid '{field_name}' format. Use ISO format, for example 2026-05-02 or 2026-05-02T10:00:00")

    if parsed_value.tzinfo:
        parsed_value = parsed_value.astimezone(datetime.timezone.utc).replace(tzinfo=None)

    return parsed_value


def _get_product_data(log):
    product = log.product

    if not product and log.manipulator_task:
        product = log.manipulator_task.product

    if not product:
        return None, None, None

    return str(product.id), product.sku, product.name


def _get_log_quantity(log):
    if log.product_quantity:
        return log.product_quantity

    match = re.search(r"Dispensed\s+(\d+)\s+units", log.message or "", re.IGNORECASE)
    if match:
        return int(match.group(1))

    if log.manipulator_task and log.manipulator_task.product_quantity:
        return log.manipulator_task.product_quantity

    return 0


def _logs_to_dataframe(logs):
    rows = []

    for log in logs:
        product_id, product_sku, product_name = _get_product_data(log)
        rows.append(
            {
                "created_at": log.created_at or datetime.datetime.utcnow(),
                "quantity": _get_log_quantity(log),
                "duration_ms": log.manipulator_task.duration_ms if log.manipulator_task else 0,
                "product_id": product_id,
                "sku": product_sku,
                "name": product_name,
            }
        )

    return pd.DataFrame(rows)


def _period_label(value, granularity):
    if pd.isna(value):
        return None

    timestamp = pd.Timestamp(value)

    if granularity == "hour":
        return timestamp.strftime("%Y-%m-%dT%H:00:00")
    if granularity == "day":
        return timestamp.strftime("%Y-%m-%d")
    if granularity == "week":
        iso_year, iso_week, _ = timestamp.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if granularity == "month":
        return timestamp.strftime("%Y-%m")

    return str(timestamp)


def _create_period_index(start_date, end_date, df, granularity):
    freq = GRANULARITY_TO_FREQ[granularity]

    start = pd.Timestamp(start_date) if start_date else df["created_at"].min()
    end = pd.Timestamp(end_date) if end_date else df["created_at"].max()

    start = start.floor("h") if granularity == "hour" else start.normalize()
    end = end.floor("h") if granularity == "hour" else end.normalize()

    if granularity == "week":
        start = start - pd.Timedelta(days=start.weekday())
        end = end - pd.Timedelta(days=end.weekday())
    elif granularity == "month":
        start = start.replace(day=1)
        end = end.replace(day=1)

    return pd.date_range(start=start, end=end, freq=freq)


def _empty_response(start_date, end_date, granularity):
    return {
        "success": True,
        "filters": {
            "from": start_date.isoformat() if start_date else None,
            "to": end_date.isoformat() if end_date else None,
            "granularity": granularity,
        },
        "summary": {
            "dispense_count": 0,
            "total_quantity": 0,
            "average_quantity": 0,
            "total_duration_ms": 0,
            "average_duration_ms": 0,
            "peak_period": None,
        },
        "series": {
            "total": [],
            "by_product": [],
        },
    }


def _build_total_series(df, period_index, granularity):
    grouped = (
        df.groupby("period_start", dropna=False)
        .agg(
            dispense_count=("quantity", "size"),
            quantity=("quantity", "sum"),
            duration_ms=("duration_ms", "sum"),
        )
        .reindex(period_index, fill_value=0)
        .reset_index(names="period_start")
    )

    grouped["period"] = grouped["period_start"].apply(lambda value: _period_label(value, granularity))

    return grouped[["period", "dispense_count", "quantity", "duration_ms"]].astype(
        {
            "dispense_count": int,
            "quantity": int,
            "duration_ms": int,
        }
    )


def _build_product_series(df, period_index, granularity):
    product_df = df.dropna(subset=["product_id"]).copy()
    if product_df.empty:
        return []

    grouped = (
        product_df.groupby(["product_id", "sku", "name", "period_start"], dropna=False)["quantity"]
        .sum()
        .reset_index()
    )

    products = product_df[["product_id", "sku", "name"]].drop_duplicates()
    by_product = []

    for _, product in products.iterrows():
        product_quantity = grouped[grouped["product_id"] == product["product_id"]].set_index("period_start")["quantity"]
        product_points = product_quantity.reindex(period_index, fill_value=0).reset_index()
        product_points.columns = ["period_start", "quantity"]
        product_points["period"] = product_points["period_start"].apply(lambda value: _period_label(value, granularity))

        points = [
            {
                "period": row["period"],
                "quantity": int(row["quantity"]),
            }
            for _, row in product_points.iterrows()
        ]

        by_product.append(
            {
                "product_id": product["product_id"],
                "sku": product["sku"],
                "name": product["name"],
                "data": points,
            }
        )

    by_product.sort(key=lambda item: sum(point["quantity"] for point in item["data"]), reverse=True)
    return by_product


def dispense_load_analytics(request):
    """
    GET /analytics/dispense-load

    Query params:
      from=ISO datetime/date
      to=ISO datetime/date
      granularity=hour|day|week|month
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    granularity = request.GET.get("granularity", "day")
    if granularity not in GRANULARITY_TO_FREQ:
        return JsonResponse(
            {"success": False, "error": "Invalid granularity. Use one of: hour, day, week, month"},
            status=400,
        )

    try:
        start_date = _parse_datetime(request.GET.get("from"), "from")
        end_date = _parse_datetime(request.GET.get("to"), "to")
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

    if start_date and end_date and start_date > end_date:
        return JsonResponse({"success": False, "error": "'from' cannot be later than 'to'"}, status=400)

    query_filter = {"operation_type": "DISPENSE"}
    if start_date:
        query_filter["created_at__gte"] = start_date
    if end_date:
        query_filter["created_at__lte"] = end_date

    logs = list(OperationLogs.objects(**query_filter).order_by("created_at"))
    if not logs:
        return JsonResponse(_empty_response(start_date, end_date, granularity), status=200)

    df = _logs_to_dataframe(logs)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["duration_ms"] = pd.to_numeric(df["duration_ms"], errors="coerce").fillna(0).astype(int)

    freq = GRANULARITY_TO_FREQ[granularity]
    if granularity == "week":
        df["period_start"] = df["created_at"].dt.normalize() - pd.to_timedelta(df["created_at"].dt.weekday, unit="D")
    else:
        df["period_start"] = df["created_at"].dt.to_period(freq).dt.start_time

    period_index = _create_period_index(start_date, end_date, df, granularity)
    total_series_df = _build_total_series(df, period_index, granularity)
    total_series = total_series_df.to_dict("records")
    by_product = _build_product_series(df, period_index, granularity)

    dispense_count = int(len(df))
    total_quantity = int(np.sum(df["quantity"].to_numpy()))
    total_duration_ms = int(np.sum(df["duration_ms"].to_numpy()))
    peak_period = max(total_series, key=lambda item: item["quantity"]) if total_series else None

    return JsonResponse(
        {
            "success": True,
            "filters": {
                "from": start_date.isoformat() if start_date else None,
                "to": end_date.isoformat() if end_date else None,
                "granularity": granularity,
            },
            "summary": {
                "dispense_count": dispense_count,
                "total_quantity": total_quantity,
                "average_quantity": float(np.round(total_quantity / dispense_count, 2)) if dispense_count else 0,
                "total_duration_ms": total_duration_ms,
                "average_duration_ms": float(np.round(total_duration_ms / dispense_count, 2)) if dispense_count else 0,
                "peak_period": peak_period,
            },
            "series": {
                "total": total_series,
                "by_product": by_product,
            },
        },
        status=200,
    )
