"""OrderExecutionService — all D-series endpoint methods.

See docs/03-endpoint-inventory.md §"D. OrderExecution" for the full inventory.
See docs/05-python-library.md §"Service surface" for method signatures.

All D1-D8 endpoints are implemented. Destructive endpoints (D2/D3/D4/D6) are
covered by unit tests with mocked HTTP only — never live-tested.
"""

from __future__ import annotations

from tradestation.models.orders import (
    ActivationTrigger,
    ExecutionRoute,
    OrderConfirmation,
    OrderGroupRequest,
    OrderRequest,
    OrderResponse,
    parse_activation_triggers,
    parse_confirmations,
    parse_order_response,
    parse_routes,
)
from tradestation.services.base import BaseService


class OrderExecutionService(BaseService):
    """Service wrapping all TradeStation OrderExecution v3 endpoints (D1-D8).

    Obtain via ``client.order_execution`` — do not construct directly.
    """

    async def confirm_order(self, request: OrderRequest) -> list[OrderConfirmation]:
        """Preview an order without submitting it.

        Returns fee and buying-power impact estimates without placing the order.

        Maps to: D1 POST /orderexecution/orderconfirm

        Args:
            request: The single-leg order request to preview.

        Returns:
            A list of :class:`~tradestation.models.orders.OrderConfirmation`.
        """
        raw = await self._transport.request(
            "POST", "/orderexecution/orderconfirm", json=request.to_api()
        )
        return parse_confirmations(raw)

    async def place_order(self, request: OrderRequest) -> OrderResponse:
        """Submit a single order to TradeStation.

        Maps to: D2 POST /orderexecution/orders

        Args:
            request: The single-leg order request to submit.

        Returns:
            The :class:`~tradestation.models.orders.OrderResponse`.

        Raises:
            tradestation.errors.ApiError: On 4xx / 5xx from the API.
        """
        raw = await self._transport.request(
            "POST", "/orderexecution/orders", json=request.to_api()
        )
        return parse_order_response(raw)

    async def replace_order(self, order_id: str, request: OrderRequest) -> OrderResponse:
        """Replace (modify) an existing working order.

        Maps to: D3 PUT /orderexecution/orders/{orderID}

        Args:
            order_id: The ID of the order to replace.
            request: The replacement order request.

        Returns:
            The :class:`~tradestation.models.orders.OrderResponse`.
        """
        raw = await self._transport.request(
            "PUT", f"/orderexecution/orders/{order_id}", json=request.to_api()
        )
        return parse_order_response(raw)

    async def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel an existing working order.

        Maps to: D4 DELETE /orderexecution/orders/{orderID}

        Args:
            order_id: The ID of the order to cancel.

        Returns:
            The :class:`~tradestation.models.orders.OrderResponse`.
        """
        raw = await self._transport.request(
            "DELETE", f"/orderexecution/orders/{order_id}"
        )
        return parse_order_response(raw)

    async def confirm_order_group(
        self, request: OrderGroupRequest
    ) -> list[OrderConfirmation]:
        """Preview a grouped order (OCO / OSO / bracket) without submitting.

        Maps to: D5 POST /orderexecution/ordergroupconfirm

        Args:
            request: The order-group request to preview.

        Returns:
            A list of :class:`~tradestation.models.orders.OrderConfirmation`.
        """
        raw = await self._transport.request(
            "POST", "/orderexecution/ordergroupconfirm", json=request.to_api()
        )
        return parse_confirmations(raw)

    async def place_order_group(self, request: OrderGroupRequest) -> OrderResponse:
        """Submit a grouped order (OCO / OSO / bracket).

        Maps to: D6 POST /orderexecution/ordergroups

        Args:
            request: The order-group request to submit.

        Returns:
            The :class:`~tradestation.models.orders.OrderResponse`.
        """
        raw = await self._transport.request(
            "POST", "/orderexecution/ordergroups", json=request.to_api()
        )
        return parse_order_response(raw)

    async def list_activation_triggers(self) -> list[ActivationTrigger]:
        """List all available conditional activation triggers.

        Maps to: D7 GET /orderexecution/activationtriggers

        Returns:
            A list of :class:`~tradestation.models.orders.ActivationTrigger`.
        """
        raw = await self._transport.request("GET", "/orderexecution/activationtriggers")
        return parse_activation_triggers(raw)

    async def list_routes(self) -> list[ExecutionRoute]:
        """List all available order execution routes.

        Maps to: D8 GET /orderexecution/routes

        Returns:
            A list of :class:`~tradestation.models.orders.ExecutionRoute`.
        """
        raw = await self._transport.request("GET", "/orderexecution/routes")
        return parse_routes(raw)
