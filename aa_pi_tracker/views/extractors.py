from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render
from django.utils import timezone

from .helpers import compute_extractors, get_owners, load_prices, nav_data


@login_required
@permission_required("aa_pi_tracker.view_pi")
def extractors_page(request):
    owners = get_owners(request.user, prefetch_planets=True)
    now = timezone.now()
    prices = load_prices()
    extractors = compute_extractors(owners, prices, now)
    ctx = {
        "active_page": "extractors",
        "extractors": extractors,
        "prices_synced": bool(prices),
        **nav_data(request, owners),
    }
    return render(request, "aa_pi_tracker/view/extractors.html", ctx)
