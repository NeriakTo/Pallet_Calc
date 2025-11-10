import math

from pallet_calc import CalculationInput, calculate_palletization


def build_example_input(allow_mixed: bool = True):
    return CalculationInput(
        products=[
            {
                "name": "999-00031",
                "order_quantity_pcs": 800,
                "pcs_per_carton": 10,
                "carton_dimensions_cm": [56, 26, 20],
            },
            {
                "name": "999-00166",
                "order_quantity_pcs": 580,
                "pcs_per_carton": 10,
                "carton_dimensions_cm": [97, 26, 20],
            },
        ],
        pallet={"length_cm": 120, "width_cm": 105, "height_cm": 195},
        allow_mixed_remainders=allow_mixed,
        container_height="20CY",
    )


def test_calculates_expected_pallets_with_mixing():
    result = calculate_palletization(build_example_input(True))
    assert result.total_pallets == 3
    assert math.isclose(result.volume_with_pallets_cbm, 6.867, rel_tol=1e-3)
    assert math.isclose(result.volume_without_pallets_cbm, 5.25512, rel_tol=1e-5)

    plan_a, plan_b = result.product_plans
    assert plan_a.full_pallets == 1
    assert plan_a.remainder_cartons == 8
    assert plan_b.full_pallets == 1
    assert plan_b.remainder_cartons == 22


def test_calculates_expected_pallets_without_mixing():
    result = calculate_palletization(build_example_input(False))
    assert result.total_pallets == 4
    # Ensure the remainder pallet was created for each product.
    labels = [detail.label for detail in result.pallets]
    assert "999-00031 remainder pallet" in labels
    assert "999-00166 remainder pallet" in labels
