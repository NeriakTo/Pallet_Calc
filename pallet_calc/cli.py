"""Command-line interface for the pallet calculator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from .calculator import CalculationInput, calculate_palletization


def _load_input(path: str | Path) -> Dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _format_pallet(detail) -> str:
    products = ", ".join(
        f"{name}: {count} cartons" for name, count in sorted(detail.cartons_by_product.items())
    )
    return (
        f"- {detail.count} × {detail.label}"
        f" (goods height {detail.goods_height_cm:.0f} cm, total height {detail.total_height_cm:.0f} cm)"
        f" -> {products}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calculate pallet requirements and volumes.")
    parser.add_argument(
        "input",
        type=str,
        help="Path to a JSON file describing the shipment (use '-' for stdin).",
    )
    args = parser.parse_args(argv)

    data = _load_input(args.input)
    calc_input = CalculationInput(
        products=data["products"],
        pallet=data["pallet_dimensions_cm"],
        allow_mixed_remainders=data.get("allow_mixed_remainders", False),
        container_height=data["container_height"],
    )
    result = calculate_palletization(calc_input)

    print(f"Total pallets required: {result.total_pallets}\n")
    print("Per-product summary:")
    for plan in result.product_plans:
        print(f"- {plan.product.name}:")
        print(f"  Order quantity: {plan.product.order_quantity_pcs} pcs")
        print(f"  Cartons required: {plan.product.cartons_required}")
        print(
            "  Best orientation:"
            f" {plan.orientation.carton_length_cm:.0f} × {plan.orientation.carton_width_cm:.0f} cm"
            f" ({plan.orientation.cartons_along_length} × {plan.orientation.cartons_along_width} per layer)"
        )
        print(f"  Cartons per layer: {plan.orientation.cartons_per_layer}")
        print(f"  Layers per pallet: {plan.layers_per_pallet}")
        print(f"  Full pallets: {plan.full_pallets}")
        print(f"  Remainder cartons: {plan.remainder_cartons}\n")

    print("Pallet breakdown:")
    for detail in result.pallets:
        print(_format_pallet(detail))
    print()

    print(
        "Total volume without pallets: "
        f"{result.volume_without_pallets_cbm:.3f} CBM / {result.volume_without_pallets_cuft:.2f} CUFT"
    )
    print(
        "Total volume with pallets: "
        f"{result.volume_with_pallets_cbm:.3f} CBM / {result.volume_with_pallets_cuft:.2f} CUFT"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    import sys

    raise SystemExit(main())
