from django.contrib import admin, messages

from jobs.models import JobCard, JobMaterial


class JobMaterialInline(admin.TabularInline):
    model = JobMaterial
    extra = 3
    autocomplete_fields = ("item",)
    readonly_fields = ("unit_cost", "is_issued", "issued_at")


@admin.register(JobCard)
class JobCardAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer", "title", "start_date", "status", "quoted_amount")
    list_filter = ("status", "start_date")
    search_fields = ("reference", "title", "customer__name", "equipment")
    readonly_fields = ("reference",)
    autocomplete_fields = ("customer",)
    inlines = [JobMaterialInline]
    actions = ["issue_materials"]

    @admin.action(description="Take the parts from the store")
    def issue_materials(self, request, queryset):
        for job in queryset:
            for material in job.materials.filter(is_issued=False):
                try:
                    material.issue(user=request.user)
                except Exception as exc:
                    self.message_user(request, f"{job.reference}/{material.item.code}: {exc}", messages.ERROR)
            self.message_user(request, f"{job.reference}: parts taken from the store.", messages.SUCCESS)
