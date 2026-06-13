from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ..models import PiOwner, PiProject, PiProjectObjective
from ..pi_data import SCHEMATIC_CHOICES, SCHEMATICS
from .helpers import get_owners, manager_corp_id, nav_data
from .helpers import get_corp_owners


@login_required
@permission_required("aa_pi_tracker.view_pi")
@require_POST
def toggle_share_character(request):
    owner = get_object_or_404(PiOwner, pk=request.POST.get("owner_pk"), user=request.user)
    owner.shared_with_corp = not owner.shared_with_corp
    owner.save(update_fields=["shared_with_corp"])
    return JsonResponse({"ok": True, "shared": owner.shared_with_corp})


@login_required
@permission_required("aa_pi_tracker.manage_corp_pi")
def corp_projects_page(request):
    corp_id, corp_name = manager_corp_id(request.user)
    shared_owners = (
        PiOwner.objects.filter(
            shared_with_corp=True,
            character__corporation_id=corp_id,
        ).select_related("character", "user")
        if corp_id
        else PiOwner.objects.none()
    )
    corp_projects = (
        PiProject.objects.filter(user=request.user, is_corp_project=True)
        .prefetch_related("participants__character", "objectives")
        .order_by("name")
    )
    owners = get_owners(request.user)
    ctx = {
        "active_page": "corp_projects",
        "corp_id": corp_id,
        "corp_name": corp_name,
        "shared_owners": shared_owners,
        "corp_projects": corp_projects,
        "schematic_choices": SCHEMATIC_CHOICES,
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/corp_projects.html", ctx)


@login_required
@permission_required("aa_pi_tracker.view_pi")
def corp_projects_member_page(request):
    member_projects = (
        PiProject.objects.filter(
            is_corp_project=True,
            participants__user=request.user,
        )
        .distinct()
        .prefetch_related("objectives", "participants__character")
        .order_by("name")
    )
    owners = get_owners(request.user)
    ctx = {
        "active_page": "corp_projects",
        "member_projects": member_projects,
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/corp_projects_member.html", ctx)


@login_required
@permission_required("aa_pi_tracker.manage_corp_pi")
@require_POST
def create_corp_project(request):
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Name is required."}, status=400)
    corp_id, corp_name = manager_corp_id(request.user)
    project = PiProject.objects.create(
        user=request.user,
        name=name,
        is_corp_project=True,
        corp_id=corp_id,
        corp_name=corp_name,
    )
    return JsonResponse({"ok": True, "pk": project.pk, "name": project.name})


@login_required
@permission_required("aa_pi_tracker.manage_corp_pi")
@require_POST
def delete_corp_project(request, pk):
    project = get_object_or_404(PiProject, pk=pk, user=request.user, is_corp_project=True)
    project.delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_pi_tracker.manage_corp_pi")
@require_POST
def corp_project_set_participants(request, pk):
    project = get_object_or_404(PiProject, pk=pk, user=request.user, is_corp_project=True)
    corp_id, _ = manager_corp_id(request.user)
    owner_pks = request.POST.getlist("owner_pks[]") or request.POST.getlist("owner_pks")
    allowed = (
        PiOwner.objects.filter(
            pk__in=owner_pks,
            shared_with_corp=True,
            character__corporation_id=corp_id,
        )
        if corp_id
        else PiOwner.objects.none()
    )
    project.participants.set(allowed)
    names = list(allowed.values_list("character__character_name", flat=True))
    return JsonResponse({"ok": True, "count": len(names), "names": names})


@login_required
@permission_required("aa_pi_tracker.manage_corp_pi")
@require_POST
def corp_project_add_objective(request, pk):
    project = get_object_or_404(PiProject, pk=pk, user=request.user, is_corp_project=True)
    schematic_name = request.POST.get("schematic_name", "")
    target = max(1, min(50, int(request.POST.get("target_qty_per_hour", 1))))
    if schematic_name not in SCHEMATICS:
        return JsonResponse({"ok": False, "error": "Unknown schematic."}, status=400)
    obj, _ = PiProjectObjective.objects.update_or_create(
        project=project,
        schematic_name=schematic_name,
        defaults={"target_qty_per_hour": target},
    )
    return JsonResponse({"ok": True, "id": obj.pk, "schematic_name": schematic_name, "target": target})


@login_required
@permission_required("aa_pi_tracker.manage_corp_pi")
@require_POST
def corp_project_delete_objective(request, pk):
    obj = get_object_or_404(
        PiProjectObjective, pk=pk,
        project__user=request.user, project__is_corp_project=True,
    )
    obj.delete()
    return JsonResponse({"ok": True})
