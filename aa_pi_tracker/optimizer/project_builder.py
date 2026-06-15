from ..models import PiPlanet, PiProject, PiProjectPlanet


def create_project(user, name, assignments, *, allowed_owner_ids=None):
    """
    Create a PiProject and assign planets with their role + P0.

    assignments: list of dicts with either:
        - {pk, role, p0}  existing colonized planet
        - {new_slot:True, char_id, char, type, example_system, role, p0}  planned slot
        or list of int planet pks (legacy)

    allowed_owner_ids: set of PiOwner PKs to accept planets from (corp mode);
        if None, only accepts planets owned by user.
    """
    project = PiProject.objects.create(user=user, name=name)

    normalized = []
    for a in assignments:
        if isinstance(a, dict):
            normalized.append(a)
        else:
            normalized.append({"pk": int(a), "role": "", "p0": ""})

    pks = [a["pk"] for a in normalized if a.get("pk")]
    if allowed_owner_ids is not None:
        planets_by_pk = {
            p.pk: p
            for p in PiPlanet.objects.filter(pk__in=pks, owner_id__in=allowed_owner_ids)
        }
    else:
        planets_by_pk = {
            p.pk: p for p in PiPlanet.objects.filter(pk__in=pks, owner__user=user)
        }

    rows = []
    for a in normalized:
        if a.get("pk") and a["pk"] in planets_by_pk:
            rows.append(
                PiProjectPlanet(
                    project=project,
                    planet=planets_by_pk[a["pk"]],
                    role=a.get("role") or "",
                    assigned_p0=a.get("p0") or "",
                )
            )
        elif a.get("new_slot"):
            rows.append(
                PiProjectPlanet(
                    project=project,
                    planet=None,
                    role=a.get("role") or "",
                    assigned_p0=a.get("p0") or "",
                    planned_char_id=a.get("char_id"),
                    planned_char_name=a.get("char") or "",
                    planned_planet_type=a.get("type") or "",
                    planned_system_name=a.get("example_system") or "",
                )
            )

    PiProjectPlanet.objects.bulk_create(rows)
    return project
