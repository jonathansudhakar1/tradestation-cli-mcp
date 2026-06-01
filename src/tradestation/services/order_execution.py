"""OrderExecutionService — all D-series endpoint methods.

See docs/03-endpoint-inventory.md §"D. OrderExecution" for the full inventory.
See docs/05-python-library.md §"Service surface" for method signatures.

All methods raise ``NotImplementedError`` in Phase 0 (scaffolding only).
Implementation tracked in Phase 2.
"""

from __future__ import annotations

from typing import Any

from tradestation.services.base import BaseService


class OrderExecutionService(BaseService):
    """Service wrapping all TradeStation OrderExecution v3 endpoints (D1-D8).

    Obtain via ``client.order_execution`` — do not construct directly.
    """

    async def confirm_order(self, request: Any) -> Any:
        """Preview an order without submitting it.

        Returns fee and buying-power impact estimates without placing the order.

        Maps to: D1 POST /orderexecution/orderconfirm

        Args:
            request: Order request (model TBD — Phase 2).

        Returns:
            Order confirmation preview (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' D1")

    async def place_order(self, request: Any) -> Any:
        """Submit a single order to TradeStation.

        Maps to: D2 POST /orderexecution/orders

        Args:
            request: Order request (model TBD — Phase 2).

        Returns:
            Submitted order response (model TBD — Phase 2).

        Raises:
            tradestation.errors.OrderRejectedError: If the order is rejected.
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' D2")

    async def replace_order(self, order_id: str, request: Any) -> Any:
        """Replace (modify) an existing working order.

        Maps to: D3 PUT /orderexecution/orders/{orderID}

        Args:
            order_id: The ID of the order to replace.
            request: Replacement request (model TBD — Phase 2).

        Returns:
            Updated order response (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' D3")

    async def cancel_order(self, order_id: str) -> Any:
        """Cancel an existing working order.

        Maps to: D4 DELETE /orderexecution/orders/{orderID}

        Args:
            order_id: The ID of the order to cancel.

        Returns:
            Cancellation confirmation (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' D4")

    async def confirm_order_group(self, request: Any) -> Any:
        """Preview a grouped order (OCO / OSO / bracket) without submitting.

        Maps to: D5 POST /orderexecution/ordergroupconfirm

        Args:
            request: Order-group request (model TBD — Phase 2).

        Returns:
            Order-group confirmation preview (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' D5")

    async def place_order_group(self, request: Any) -> Any:
        """Submit a grouped order (OCO / OSO / bracket).

        Maps to: D6 POST /orderexecution/ordergroups

        Args:
            request: Order-group request (model TBD — Phase 2).

        Returns:
            Submitted order-group response (model TBD — Phase 2).

        Raises:
            tradestation.errors.OrderRejectedError: If the group is rejected.
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' D6")

    async def list_activation_triggers(self) -> Any:
        """List all available conditional activation triggers.

        Maps to: D7 GET /orderexecution/activationtriggers

        Returns:
            Parsed activation-trigger list (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' D7")

    async def list_routes(self) -> Any:
        """List all available order execution routes.

        Maps to: D8 GET /orderexecution/routes

        Returns:
            Parsed routes list (model TBD — Phase 2).

        Raises:
            NotImplementedError: Until Phase 2 implementation.
        """
        raise NotImplementedError("see docs/05-python-library.md §'Service surface' D8")
