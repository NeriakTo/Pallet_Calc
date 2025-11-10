"""Core pallet and volume calculations."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Dict, Iterable, List, Tuple

CUFT_PER_CBM = 35.3146667

_CONTAINER_HEIGHTS_CM = {
    "20CY": 239.0,
    "40CY": 239.0,
    "40HQ": 269.0,
}


@dataclass(frozen=True)
class ProductSpec:
    """Input data describing a product that must be palletised."""

    name: str
    order_quantity_pcs: int
    pcs_per_carton: int
    carton_length_cm: float
    carton_width_cm: float
    carton_height_cm: float

    @property
    def cartons_required(self) -> int:
        return math.ceil(self.order_quantity_pcs / self.pcs_per_carton)

    @property
    def carton_volume_cbm(self) -> float:
        return (
            self.carton_length_cm
            * self.carton_width_cm
            * self.carton_height_cm
            / 1_000_000.0
        )


@dataclass(frozen=True)
class PalletSpec:
    length_cm: float
    width_cm: float
    height_cm: float
    base_height_cm: float = 15.0

    def goods_height_limit(self, container_height_cm: float) -> float:
        """Return the maximum allowable goods height above the pallet base."""

        limit = min(self.height_cm, container_height_cm) - self.base_height_cm
        if limit <= 0:
            raise ValueError(
                "Pallet/base height exceeds available container height."
            )
        return limit


@dataclass
class OrientationPlan:
    cartons_per_layer: int
    cartons_along_length: int
    cartons_along_width: int
    carton_length_cm: float
    carton_width_cm: float


@dataclass
class ProductPlan:
    product: ProductSpec
    orientation: OrientationPlan
    layers_per_pallet: int
    cartons_per_pallet: int
    full_pallets: int
    remainder_cartons: int

    @property
    def goods_height_cm(self) -> float:
        return self.layers_per_pallet * self.product.carton_height_cm


@dataclass
class Layer:
    product_name: str
    cartons: int
    layer_height_cm: float


@dataclass
class PalletDetail:
    label: str
    count: int
    cartons_by_product: Dict[str, int]
    goods_height_cm: float
    total_height_cm: float


@dataclass
class CalculationInput:
    products: Iterable[Dict[str, object]]
    pallet: Dict[str, float]
    allow_mixed_remainders: bool
    container_height: str


@dataclass
class CalculationResult:
    product_plans: List[ProductPlan]
    pallets: List[PalletDetail]
    total_cartons: int
    total_pallets: int
    volume_without_pallets_cbm: float
    volume_with_pallets_cbm: float

    @property
    def volume_without_pallets_cuft(self) -> float:
        return self.volume_without_pallets_cbm * CUFT_PER_CBM

    @property
    def volume_with_pallets_cuft(self) -> float:
        return self.volume_with_pallets_cbm * CUFT_PER_CBM


def _load_products(raw_products: Iterable[Dict[str, object]]) -> List[ProductSpec]:
    products: List[ProductSpec] = []
    for raw in raw_products:
        try:
            dims = raw["carton_dimensions_cm"]
            length_cm, width_cm, height_cm = (
                float(dims[0]),
                float(dims[1]),
                float(dims[2]),
            )
            product = ProductSpec(
                name=str(raw["name"]),
                order_quantity_pcs=int(raw["order_quantity_pcs"]),
                pcs_per_carton=int(raw["pcs_per_carton"]),
                carton_length_cm=length_cm,
                carton_width_cm=width_cm,
                carton_height_cm=height_cm,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid product specification: {json.dumps(raw)}") from exc
        products.append(product)
    if not products:
        raise ValueError("At least one product must be provided.")
    return products


def _load_pallet(raw_pallet: Dict[str, float]) -> PalletSpec:
    try:
        length_cm = float(raw_pallet["length_cm"])
        width_cm = float(raw_pallet["width_cm"])
        height_cm = float(raw_pallet["height_cm"])
        base_height_cm = float(raw_pallet.get("base_height_cm", 15.0))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid pallet specification.") from exc
    if any(value <= 0 for value in (length_cm, width_cm, height_cm, base_height_cm)):
        raise ValueError("Pallet dimensions must be positive numbers.")
    if base_height_cm >= height_cm:
        raise ValueError("Pallet base height must be lower than total pallet height.")
    return PalletSpec(length_cm, width_cm, height_cm, base_height_cm)


def _resolve_container_height(container_height: str) -> float:
    try:
        return _CONTAINER_HEIGHTS_CM[container_height.upper()]
    except KeyError as exc:
        valid = ", ".join(sorted(_CONTAINER_HEIGHTS_CM))
        raise ValueError(f"Unsupported container height '{container_height}'. Valid values: {valid}.") from exc


def _best_orientation(product: ProductSpec, pallet: PalletSpec) -> OrientationPlan:
    options: List[OrientationPlan] = []
    for length, width in (
        (product.carton_length_cm, product.carton_width_cm),
        (product.carton_width_cm, product.carton_length_cm),
    ):
        count_length = math.floor(pallet.length_cm / length)
        count_width = math.floor(pallet.width_cm / width)
        per_layer = count_length * count_width
        if per_layer <= 0:
            continue
        options.append(
            OrientationPlan(
                cartons_per_layer=per_layer,
                cartons_along_length=count_length,
                cartons_along_width=count_width,
                carton_length_cm=length,
                carton_width_cm=width,
            )
        )
    if not options:
        raise ValueError(
            f"Product {product.name} cannot fit on the pallet footprint with either orientation."
        )
    options.sort(
        key=lambda plan: (
            plan.cartons_per_layer,
            plan.cartons_along_length,
            plan.cartons_along_width,
        ),
        reverse=True,
    )
    return options[0]


def _build_layers(plan: ProductPlan) -> List[Layer]:
    layers: List[Layer] = []
    if plan.remainder_cartons <= 0:
        return layers
    per_layer = plan.orientation.cartons_per_layer
    full_layers = plan.remainder_cartons // per_layer
    for _ in range(full_layers):
        layers.append(
            Layer(
                product_name=plan.product.name,
                cartons=per_layer,
                layer_height_cm=plan.product.carton_height_cm,
            )
        )
    remaining = plan.remainder_cartons % per_layer
    if remaining:
        layers.append(
            Layer(
                product_name=plan.product.name,
                cartons=remaining,
                layer_height_cm=plan.product.carton_height_cm,
            )
        )
    return layers


def _pack_layers(layers: List[Layer], goods_height_limit_cm: float) -> List[List[Layer]]:
    if not layers:
        return []
    # Sort by descending height to keep taller layers together.
    ordered = sorted(layers, key=lambda layer: layer.layer_height_cm, reverse=True)
    pallets: List[List[Layer]] = []
    current: List[Layer] = []
    current_height = 0.0
    for layer in ordered:
        if layer.layer_height_cm > goods_height_limit_cm:
            raise ValueError("Layer height exceeds available stacking limit.")
        if current_height + layer.layer_height_cm <= goods_height_limit_cm:
            current.append(layer)
            current_height += layer.layer_height_cm
        else:
            pallets.append(current)
            current = [layer]
            current_height = layer.layer_height_cm
    if current:
        pallets.append(current)
    return pallets


def calculate_palletization(data: CalculationInput) -> CalculationResult:
    products = _load_products(data.products)
    pallet = _load_pallet(data.pallet)
    container_height_cm = _resolve_container_height(data.container_height)
    goods_limit_cm = pallet.goods_height_limit(container_height_cm)

    product_plans: List[ProductPlan] = []
    remainder_layers: List[Layer] = []
    pallets: List[PalletDetail] = []
    total_cartons = 0
    volume_without_pallets = 0.0

    for product in products:
        orientation = _best_orientation(product, pallet)
        layers_per_pallet = math.floor(goods_limit_cm / product.carton_height_cm)
        if layers_per_pallet <= 0:
            raise ValueError(
                f"Product {product.name} exceeds the allowable stacking height."
            )
        cartons_per_pallet = orientation.cartons_per_layer * layers_per_pallet
        if cartons_per_pallet <= 0:
            raise ValueError(
                f"Product {product.name} cannot be placed on the pallet with the given constraints."
            )
        cartons_required = product.cartons_required
        full_pallets = cartons_required // cartons_per_pallet
        remainder = cartons_required % cartons_per_pallet
        plan = ProductPlan(
            product=product,
            orientation=orientation,
            layers_per_pallet=layers_per_pallet,
            cartons_per_pallet=cartons_per_pallet,
            full_pallets=full_pallets,
            remainder_cartons=remainder,
        )
        product_plans.append(plan)
        volume_without_pallets += cartons_required * product.carton_volume_cbm
        total_cartons += cartons_required

        if full_pallets:
            pallets.append(
                PalletDetail(
                    label=f"{product.name} full pallet",
                    count=full_pallets,
                    cartons_by_product={product.name: cartons_per_pallet},
                    goods_height_cm=plan.goods_height_cm,
                    total_height_cm=plan.goods_height_cm + pallet.base_height_cm,
                )
            )

        if data.allow_mixed_remainders:
            remainder_layers.extend(_build_layers(plan))
        elif remainder:
            goods_height_cm = (
                math.ceil(remainder / plan.orientation.cartons_per_layer)
                * product.carton_height_cm
            )
            pallets.append(
                PalletDetail(
                    label=f"{product.name} remainder pallet",
                    count=1,
                    cartons_by_product={product.name: remainder},
                    goods_height_cm=goods_height_cm,
                    total_height_cm=goods_height_cm + pallet.base_height_cm,
                )
            )

    if data.allow_mixed_remainders and remainder_layers:
        packed = _pack_layers(remainder_layers, goods_limit_cm)
        for index, layer_stack in enumerate(packed, start=1):
            cartons_by_product: Dict[str, int] = {}
            goods_height_cm = 0.0
            for layer in layer_stack:
                cartons_by_product[layer.product_name] = (
                    cartons_by_product.get(layer.product_name, 0) + layer.cartons
                )
                goods_height_cm += layer.layer_height_cm
            pallets.append(
                PalletDetail(
                    label=f"Mixed remainder pallet #{index}",
                    count=1,
                    cartons_by_product=cartons_by_product,
                    goods_height_cm=goods_height_cm,
                    total_height_cm=goods_height_cm + pallet.base_height_cm,
                )
            )

    total_pallets = sum(detail.count for detail in pallets)
    volume_with_pallets = 0.0
    pallet_footprint_sqm = (pallet.length_cm / 100.0) * (pallet.width_cm / 100.0)
    for detail in pallets:
        height_m = detail.total_height_cm / 100.0
        volume_with_pallets += detail.count * pallet_footprint_sqm * height_m

    return CalculationResult(
        product_plans=product_plans,
        pallets=pallets,
        total_cartons=total_cartons,
        total_pallets=total_pallets,
        volume_without_pallets_cbm=volume_without_pallets,
        volume_with_pallets_cbm=volume_with_pallets,
    )
