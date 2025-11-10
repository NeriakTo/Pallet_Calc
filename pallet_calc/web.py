"""Simple Flask web interface for the pallet calculator."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from flask import Flask, render_template, request

from .calculator import CalculationInput, calculate_palletization

app = Flask(__name__)

_CONTAINER_OPTIONS: Tuple[Tuple[str, str], ...] = (
    ("20CY", "20' (Standard)"),
    ("40CY", "40' (Standard)"),
    ("40HQ", "40' High Cube"),
)

_DEFAULT_FORM = {
    "product_name": "Product",
    "order_quantity_pcs": "",
    "pcs_per_carton": "",
    "carton_length_cm": "",
    "carton_width_cm": "",
    "carton_height_cm": "",
    "pallet_length_cm": "",
    "pallet_width_cm": "",
    "pallet_height_cm": "",
    "allow_mixed_remainders": "Yes",
    "container_height": "40HQ",
}


def _parse_yes_no(value: str) -> bool:
    return value.strip().lower() in {"y", "yes", "true", "1"}


@app.route("/", methods=["GET", "POST"])
def index():
    form_values = dict(_DEFAULT_FORM)
    error: str | None = None
    result: Dict[str, Any] | None = None

    if request.method == "POST":
        form_values.update(request.form)
        try:
            data = CalculationInput(
                products=[
                    {
                        "name": form_values.get("product_name") or "Product",
                        "order_quantity_pcs": int(form_values["order_quantity_pcs"]),
                        "pcs_per_carton": int(form_values["pcs_per_carton"]),
                        "carton_dimensions_cm": [
                            float(form_values["carton_length_cm"]),
                            float(form_values["carton_width_cm"]),
                            float(form_values["carton_height_cm"]),
                        ],
                    }
                ],
                pallet={
                    "length_cm": float(form_values["pallet_length_cm"]),
                    "width_cm": float(form_values["pallet_width_cm"]),
                    "height_cm": float(form_values["pallet_height_cm"]),
                },
                allow_mixed_remainders=_parse_yes_no(
                    form_values.get("allow_mixed_remainders", "no")
                ),
                container_height=form_values.get("container_height", "40HQ"),
            )
            calc_result = calculate_palletization(data)
            result = _serialise_result(calc_result)
        except Exception as exc:  # noqa: BLE001 - show all validation errors
            error = str(exc)

    return render_template(
        "index.html",
        form=form_values,
        container_options=_CONTAINER_OPTIONS,
        result=result,
        error=error,
    )


def _serialise_result(calc_result):
    """Convert the calculation result into JSON-like dictionaries."""

    product_plans = []
    for plan in calc_result.product_plans:
        product_plans.append(
            {
                "product": plan.product.name,
                "orientation": {
                    "cartons_per_layer": plan.orientation.cartons_per_layer,
                    "cartons_along_length": plan.orientation.cartons_along_length,
                    "cartons_along_width": plan.orientation.cartons_along_width,
                    "carton_length_cm": plan.orientation.carton_length_cm,
                    "carton_width_cm": plan.orientation.carton_width_cm,
                },
                "layers_per_pallet": plan.layers_per_pallet,
                "cartons_per_pallet": plan.cartons_per_pallet,
                "full_pallets": plan.full_pallets,
                "remainder_cartons": plan.remainder_cartons,
            }
        )

    pallet_details = []
    for detail in calc_result.pallets:
        pallet_details.append(
            {
                "label": detail.label,
                "count": detail.count,
                "cartons_by_product": detail.cartons_by_product,
                "goods_height_cm": detail.goods_height_cm,
                "total_height_cm": detail.total_height_cm,
            }
        )

    return {
        "product_plans": product_plans,
        "pallets": pallet_details,
        "total_cartons": calc_result.total_cartons,
        "total_pallets": calc_result.total_pallets,
        "volume_without_pallets_cbm": calc_result.volume_without_pallets_cbm,
        "volume_without_pallets_cuft": calc_result.volume_without_pallets_cuft,
        "volume_with_pallets_cbm": calc_result.volume_with_pallets_cbm,
        "volume_with_pallets_cuft": calc_result.volume_with_pallets_cuft,
    }


if __name__ == "__main__":
    app.run(debug=True)
