from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import user_is_manager
from accounts.permissions import inventory_required
from inventory import charts
from jobs.forms import JobCardForm, JobMaterialFormSet
from jobs.models import JobCard, JobStatus


@inventory_required
def job_list(request):
    jobs = JobCard.objects.select_related("customer")
    status = request.GET.get("status")
    if status:
        jobs = jobs.filter(status=status)
    jobs = list(jobs[:200])
    today = timezone.now().date()
    month_start = today.replace(day=1)
    show_money = user_is_manager(request.user)

    open_jobs = [j for j in jobs if j.is_open]
    return render(request, "inventory/job_list.html", {
        "jobs": jobs,
        "selected_status": status,
        "show_money": show_money,
        "summary": {
            "open": len(open_jobs),
            "late": sum(1 for j in open_jobs if j.is_overdue),
            "due_today": sum(1 for j in open_jobs if j.due_date == today),
            "finished_this_month": sum(
                1 for j in jobs if j.completed_date and j.completed_date >= month_start
            ),
            "profit": sum((j.profit for j in jobs if j.quoted_amount), Decimal("0")),
        },
        "profit_chart": charts.signed_bars([
            {"label": j.reference.split("-")[-1], "value": float(j.profit)}
            for j in jobs[:10] if j.quoted_amount
        ]) if show_money else None,
        "statuses": JobStatus.choices,
    })


@inventory_required
def job_create(request):
    form = JobCardForm(request.POST or None, initial={"start_date": timezone.now().date()})
    formset = JobMaterialFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        job = form.save(commit=False)
        job.created_by = request.user
        job.save()
        formset.instance = job
        formset.save()
        messages.success(request, f"Job {job.reference} created.")
        return redirect("inventory:job_detail", pk=job.pk)
    return render(request, "inventory/job_form.html", {
        "form": form, "formset": formset, "title": "New job card",
    })


@inventory_required
def job_detail(request, pk):
    job = get_object_or_404(
        JobCard.objects.select_related("customer").prefetch_related("materials__item"), pk=pk
    )
    form = JobCardForm(request.POST or None, instance=job)
    formset = JobMaterialFormSet(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        messages.success(request, f"{job.reference} updated.")
        return redirect("inventory:job_detail", pk=pk)
    return render(request, "inventory/job_detail.html", {
        "job": job, "form": form, "formset": formset,
    })


@inventory_required
def job_issue_materials(request, pk):
    job = get_object_or_404(JobCard, pk=pk)
    issued, failed = 0, []
    for material in job.materials.filter(is_issued=False).select_related("item"):
        try:
            material.issue(user=request.user)
            issued += 1
        except ValueError as exc:
            failed.append(f"{material.item.code}: {exc}")
    if issued:
        messages.success(request, f"{issued} part(s) taken from the store.")
    for error in failed:
        messages.error(request, error)
    return redirect("inventory:job_detail", pk=pk)
