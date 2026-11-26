from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from .builders import REPORT_BY_SLUG, REPORTS
from .exporters import csv_response, pdf_response, xlsx_response


def can_view(user, report):
    return user.is_superuser or user.groups.filter(name__in=report["roles"]).exists()


def read_period(request):
    """From and to dates from the address. Default: this month so far."""
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET.get("start", ""))
    except ValueError:
        start = today.replace(day=1)
    try:
        end = date.fromisoformat(request.GET.get("end", ""))
    except ValueError:
        end = today
    if end < start:
        start, end = end, start
    return start, end


@login_required
def report_index(request):
    available = [r for r in REPORTS if can_view(request.user, r)]
    if not available:
        raise PermissionDenied
    start, end = read_period(request)
    return render(
        request,
        "reports/index.html",
        {"reports": available, "start": start, "end": end, "query": f"start={start}&end={end}"},
    )


@login_required
def report_view(request, slug):
    report = REPORT_BY_SLUG.get(slug)
    if report is None:
        raise Http404
    if not can_view(request.user, report):
        raise PermissionDenied

    start, end = read_period(request)
    data = report["build"](start, end)
    if report["dated"]:
        period = f"Period: {start:%d-%m-%Y} to {end:%d-%m-%Y}"
        filename = f"{slug}_{start}_{end}"
    else:
        today = timezone.localdate()
        period = f"As on {today:%d-%m-%Y}"
        filename = f"{slug}_{today}"

    export = request.GET.get("format", "html")
    if export == "csv":
        return csv_response(data, filename)
    if export == "xlsx":
        return xlsx_response(data, report["title"], filename)
    if export == "pdf":
        return pdf_response(data, report["title"], period, filename)

    return render(
        request,
        "reports/report.html",
        {
            "report": report,
            "period": period,
            "headers": data["headers"],
            "rows": data["rows"],
            "totals": data["totals"],
            "start": start,
            "end": end,
            "query": f"start={start}&end={end}",
        },
    )