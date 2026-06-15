# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from ..models import PiMarketPrice
from ..pi_data import SCHEMATICS
from .helpers import load_prices, nav_data


def _build_profit_data(prices: dict) -> list:
    rows = []
    for name, data in SCHEMATICS.items():
        tier = data["tier"]
        output_qty = data["output_qty"]
        cycle_time = data["cycle_time"]
        cycles_h = 3600 / cycle_time
        out_h = output_qty * cycles_h

        direct_inputs = [
            {
                "name": mat,
                "qty_per_cycle": qty,
                "unit_price": prices.get(mat, 0.0),
                "cost_per_hour": round(qty * cycles_h * prices.get(mat, 0.0), 0),
            }
            for mat, qty in data["inputs"].items()
            if prices.get(mat, 0.0) > 0
        ]
        input_cost_h = 0  # fully integrated chain: P0 is self-extracted, no input cost

        output_price = prices.get(name, 0.0)
        output_value_h = out_h * output_price
        profit_h = output_value_h - input_cost_h
        margin = (profit_h / output_value_h * 100) if output_value_h > 0 else 0.0

        rows.append(
            {
                "name": name,
                "tier": tier,
                "cycle_time_s": cycle_time,
                "cycles_per_hour": round(cycles_h, 4),
                "inputs": direct_inputs,
                "output_qty_per_cycle": output_qty,
                "output_qty_per_hour": out_h,
                "output_unit_price": output_price,
                "output_value_per_hour": output_value_h,
                "input_cost_per_hour": input_cost_h,
                "profit_per_hour": profit_h,
                "margin_pct": round(margin, 1),
            }
        )

    rows.sort(key=lambda x: -x["profit_per_hour"])
    return rows


@login_required
@permission_required("aa_pi_tracker.view_pi")
def profit_page(request):
    prices = load_prices()
    prices_synced = bool(prices)
    price_updated_at = (
        PiMarketPrice.objects.order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    profit_data = _build_profit_data(prices) if prices_synced else []
    ctx = {
        "active_page": "profit",
        "profit_data": profit_data,
        "prices_synced": prices_synced,
        "price_updated_at": price_updated_at,
        **nav_data(request),
    }
    return render(request, "aa_pi_tracker/view/profit.html", ctx)
