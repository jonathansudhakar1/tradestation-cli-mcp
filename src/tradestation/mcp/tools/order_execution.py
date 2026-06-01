"""Order execution MCP tools (D-series).

Each ``register_*`` function registers one MCP tool on the given FastMCP
server.  Destructive tools (D2/D3/D4/D6) integrate the safety confirmation
gate from :mod:`tradestation.mcp.safety`.

Inventory coverage: D1-D8 (8 tools).

Safety modes (controlled by ``confirm_mode``):
    off     — execute immediately.
    require — require a confirmation_token; first call returns preview + token.
    review  — preview only; placement via out-of-band CLI step.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from tradestation.mcp.safety import (
    generate_token,
    hash_payload,
    verify_token,
    write_audit_log,
)

# ---------------------------------------------------------------------------
# D1 — POST /orderexecution/orderconfirm  (safe)
# ---------------------------------------------------------------------------


def register_order_confirm(mcp: FastMCP, client: Any) -> None:
    """Register the ``order_confirm`` tool (D1)."""

    @mcp.tool(name="order_confirm")
    async def order_confirm(
        request: dict[str, Any],
    ) -> Any:
        """Preview an order without submitting it (D1).

        Returns fee and buying-power impact estimates without placing the order.
        This tool is safe — it never submits an order.

        Args:
            request: Order request dict (AccountID, Symbol, Quantity, OrderType,
                TradeAction, etc.).
        """
        return await client.order_execution.confirm_order(request)

    order_confirm._ts_op_id = "D1"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D2 — POST /orderexecution/orders  (destructive)
# ---------------------------------------------------------------------------


def register_order_place(
    mcp: FastMCP,
    client: Any,
    *,
    confirm_mode: str = "require",
    max_order_notional: float | None = None,
    allowed_symbols: list[str] | None = None,
) -> None:
    """Register the ``order_place`` tool (D2) with safety gate."""

    @mcp.tool(name="order_place")
    async def order_place(
        request: dict[str, Any],
        confirmation_token: str | None = None,
    ) -> Any:
        """Submit a single order to TradeStation (D2).

        Safety gate behaviour depends on --confirm-trades mode:
        - require (default): call without confirmation_token to receive a
          preview + token; resubmit with the token to place the order.
        - off: executes immediately.
        - review: returns preview only; use the CLI to actually place.

        Args:
            request: Order request dict (AccountID, Symbol, Quantity, OrderType,
                TradeAction, LimitPrice/StopPrice as applicable).
            confirmation_token: Single-use token from a previous preview call.
                Required when --confirm-trades=require.
        """
        payload_hash = hash_payload(request)
        symbol = request.get("Symbol", request.get("symbol", "unknown"))
        account = request.get("AccountID", request.get("account_id"))

        # Symbol allowlist check
        if allowed_symbols:
            from tradestation.mcp.safety import assert_symbol_allowed

            assert_symbol_allowed(str(symbol), allowed_symbols)

        if confirm_mode == "off":
            write_audit_log(
                tool="order_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="skip",
                result="executing",
            )
            result = await client.order_execution.place_order(request)
            write_audit_log(
                tool="order_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="skip",
                result="success",
            )
            return result

        # Build preview
        preview = await client.order_execution.confirm_order(request)

        # Notional cap check
        if max_order_notional is not None:
            from tradestation.mcp.safety import assert_notional_within_cap

            preview_dict = preview if isinstance(preview, dict) else {}
            assert_notional_within_cap(preview_dict, max_order_notional)

        if confirm_mode == "review":
            write_audit_log(
                tool="order_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="preview",
                result="review_mode",
            )
            return {
                "status": "preview_only",
                "message": (
                    "Server is in review mode. "
                    "Use `ts order place` CLI to actually submit this order."
                ),
                "preview": preview,
            }

        # confirm_mode == "require"
        if confirmation_token is None:
            token = generate_token(payload_hash)
            write_audit_log(
                tool="order_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="preview",
                result="token_issued",
            )
            return {
                "status": "preview",
                "message": (
                    "Resubmit with confirmation_token to place this order. "
                    "Token expires in 60 seconds."
                ),
                "preview": preview,
                "confirmation_token": token,
            }

        # Token provided — verify it
        if not verify_token(confirmation_token, payload_hash):
            write_audit_log(
                tool="order_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="reject",
                result="invalid_token",
            )
            return {
                "status": "error",
                "message": (
                    "Confirmation token is invalid or expired. "
                    "Resubmit without confirmation_token to receive a new token."
                ),
            }

        # Execute
        write_audit_log(
            tool="order_place",
            account=str(account) if account else None,
            payload=request,
            preview_hash=payload_hash,
            decision="confirm",
            result="executing",
        )
        result = await client.order_execution.place_order(request)
        write_audit_log(
            tool="order_place",
            account=str(account) if account else None,
            payload=request,
            preview_hash=payload_hash,
            decision="confirm",
            result="success",
        )
        return result

    order_place._ts_op_id = "D2"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D3 — PUT /orderexecution/orders/{orderID}  (destructive)
# ---------------------------------------------------------------------------


def register_order_replace(
    mcp: FastMCP,
    client: Any,
    *,
    confirm_mode: str = "require",
    max_order_notional: float | None = None,
    allowed_symbols: list[str] | None = None,
) -> None:
    """Register the ``order_replace`` tool (D3) with safety gate."""

    @mcp.tool(name="order_replace")
    async def order_replace(
        order_id: str,
        request: dict[str, Any],
        confirmation_token: str | None = None,
    ) -> Any:
        """Replace (modify) an existing working order (D3).

        Safety gate behaviour depends on --confirm-trades mode.
        Call without confirmation_token to receive a preview + token;
        resubmit with the token to apply the modification.

        Args:
            order_id: The ID of the order to replace.
            request: Replacement request dict.
            confirmation_token: Single-use token from a previous preview call.
        """
        payload = {"order_id": order_id, **request}
        payload_hash = hash_payload(payload)
        account = request.get("AccountID", request.get("account_id"))

        if confirm_mode == "off":
            write_audit_log(
                tool="order_replace",
                account=str(account) if account else None,
                payload=payload,
                preview_hash=payload_hash,
                decision="skip",
                result="executing",
            )
            result = await client.order_execution.replace_order(order_id, request)
            write_audit_log(
                tool="order_replace",
                account=str(account) if account else None,
                payload=payload,
                preview_hash=payload_hash,
                decision="skip",
                result="success",
            )
            return result

        if confirm_mode == "review":
            write_audit_log(
                tool="order_replace",
                account=str(account) if account else None,
                payload=payload,
                preview_hash=payload_hash,
                decision="preview",
                result="review_mode",
            )
            return {
                "status": "preview_only",
                "message": (
                    "Server is in review mode. "
                    "Use `ts order replace` CLI to actually modify this order."
                ),
                "order_id": order_id,
                "request": request,
            }

        # confirm_mode == "require"
        if confirmation_token is None:
            token = generate_token(payload_hash)
            write_audit_log(
                tool="order_replace",
                account=str(account) if account else None,
                payload=payload,
                preview_hash=payload_hash,
                decision="preview",
                result="token_issued",
            )
            return {
                "status": "preview",
                "message": (
                    "Resubmit with confirmation_token to replace this order. "
                    "Token expires in 60 seconds."
                ),
                "order_id": order_id,
                "request": request,
                "confirmation_token": token,
            }

        if not verify_token(confirmation_token, payload_hash):
            write_audit_log(
                tool="order_replace",
                account=str(account) if account else None,
                payload=payload,
                preview_hash=payload_hash,
                decision="reject",
                result="invalid_token",
            )
            return {
                "status": "error",
                "message": "Confirmation token is invalid or expired.",
            }

        write_audit_log(
            tool="order_replace",
            account=str(account) if account else None,
            payload=payload,
            preview_hash=payload_hash,
            decision="confirm",
            result="executing",
        )
        result = await client.order_execution.replace_order(order_id, request)
        write_audit_log(
            tool="order_replace",
            account=str(account) if account else None,
            payload=payload,
            preview_hash=payload_hash,
            decision="confirm",
            result="success",
        )
        return result

    order_replace._ts_op_id = "D3"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D4 — DELETE /orderexecution/orders/{orderID}  (destructive)
# ---------------------------------------------------------------------------


def register_order_cancel(
    mcp: FastMCP,
    client: Any,
    *,
    confirm_mode: str = "require",
    max_order_notional: float | None = None,
    allowed_symbols: list[str] | None = None,
) -> None:
    """Register the ``order_cancel`` tool (D4) with safety gate."""

    @mcp.tool(name="order_cancel")
    async def order_cancel(
        order_id: str,
        confirmation_token: str | None = None,
    ) -> Any:
        """Cancel an existing working order (D4).

        Safety gate behaviour depends on --confirm-trades mode.
        Call without confirmation_token to receive a token;
        resubmit with the token to cancel.

        Args:
            order_id: The ID of the order to cancel.
            confirmation_token: Single-use token from a previous preview call.
        """
        payload = {"order_id": order_id, "action": "cancel"}
        payload_hash = hash_payload(payload)

        if confirm_mode == "off":
            write_audit_log(
                tool="order_cancel",
                account=None,
                payload=payload,
                preview_hash=payload_hash,
                decision="skip",
                result="executing",
            )
            result = await client.order_execution.cancel_order(order_id)
            write_audit_log(
                tool="order_cancel",
                account=None,
                payload=payload,
                preview_hash=payload_hash,
                decision="skip",
                result="success",
            )
            return result

        if confirm_mode == "review":
            write_audit_log(
                tool="order_cancel",
                account=None,
                payload=payload,
                preview_hash=payload_hash,
                decision="preview",
                result="review_mode",
            )
            return {
                "status": "preview_only",
                "message": (
                    "Server is in review mode. "
                    "Use `ts order cancel` CLI to actually cancel this order."
                ),
                "order_id": order_id,
            }

        # confirm_mode == "require"
        if confirmation_token is None:
            token = generate_token(payload_hash)
            write_audit_log(
                tool="order_cancel",
                account=None,
                payload=payload,
                preview_hash=payload_hash,
                decision="preview",
                result="token_issued",
            )
            return {
                "status": "preview",
                "message": (
                    "Resubmit with confirmation_token to cancel order "
                    f"{order_id}. Token expires in 60 seconds."
                ),
                "order_id": order_id,
                "confirmation_token": token,
            }

        if not verify_token(confirmation_token, payload_hash):
            write_audit_log(
                tool="order_cancel",
                account=None,
                payload=payload,
                preview_hash=payload_hash,
                decision="reject",
                result="invalid_token",
            )
            return {
                "status": "error",
                "message": "Confirmation token is invalid or expired.",
            }

        write_audit_log(
            tool="order_cancel",
            account=None,
            payload=payload,
            preview_hash=payload_hash,
            decision="confirm",
            result="executing",
        )
        result = await client.order_execution.cancel_order(order_id)
        write_audit_log(
            tool="order_cancel",
            account=None,
            payload=payload,
            preview_hash=payload_hash,
            decision="confirm",
            result="success",
        )
        return result

    order_cancel._ts_op_id = "D4"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D5 — POST /orderexecution/ordergroupconfirm  (safe)
# ---------------------------------------------------------------------------


def register_order_group_confirm(mcp: FastMCP, client: Any) -> None:
    """Register the ``order_group_confirm`` tool (D5)."""

    @mcp.tool(name="order_group_confirm")
    async def order_group_confirm(
        request: dict[str, Any],
    ) -> Any:
        """Preview a grouped order (OCO/OSO/bracket) without submitting it (D5).

        This tool is safe — it never submits an order.

        Args:
            request: Order-group request dict.
        """
        return await client.order_execution.confirm_order_group(request)

    order_group_confirm._ts_op_id = "D5"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D6 — POST /orderexecution/ordergroups  (destructive)
# ---------------------------------------------------------------------------


def register_order_group_place(
    mcp: FastMCP,
    client: Any,
    *,
    confirm_mode: str = "require",
    max_order_notional: float | None = None,
    allowed_symbols: list[str] | None = None,
) -> None:
    """Register the ``order_group_place`` tool (D6) with safety gate."""

    @mcp.tool(name="order_group_place")
    async def order_group_place(
        request: dict[str, Any],
        confirmation_token: str | None = None,
    ) -> Any:
        """Submit a grouped order (OCO/OSO/bracket) to TradeStation (D6).

        Safety gate behaviour depends on --confirm-trades mode.
        Call without confirmation_token to receive a preview + token;
        resubmit with the token to place the order group.

        Args:
            request: Order-group request dict.
            confirmation_token: Single-use token from a previous preview call.
        """
        payload_hash = hash_payload(request)
        account = request.get("AccountID", request.get("account_id"))

        if confirm_mode == "off":
            write_audit_log(
                tool="order_group_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="skip",
                result="executing",
            )
            result = await client.order_execution.place_order_group(request)
            write_audit_log(
                tool="order_group_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="skip",
                result="success",
            )
            return result

        preview = await client.order_execution.confirm_order_group(request)

        if max_order_notional is not None:
            from tradestation.mcp.safety import assert_notional_within_cap

            preview_dict = preview if isinstance(preview, dict) else {}
            assert_notional_within_cap(preview_dict, max_order_notional)

        if confirm_mode == "review":
            write_audit_log(
                tool="order_group_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="preview",
                result="review_mode",
            )
            return {
                "status": "preview_only",
                "message": (
                    "Server is in review mode. "
                    "Use `ts order group place` CLI to submit this order group."
                ),
                "preview": preview,
            }

        # confirm_mode == "require"
        if confirmation_token is None:
            token = generate_token(payload_hash)
            write_audit_log(
                tool="order_group_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="preview",
                result="token_issued",
            )
            return {
                "status": "preview",
                "message": (
                    "Resubmit with confirmation_token to place this order group. "
                    "Token expires in 60 seconds."
                ),
                "preview": preview,
                "confirmation_token": token,
            }

        if not verify_token(confirmation_token, payload_hash):
            write_audit_log(
                tool="order_group_place",
                account=str(account) if account else None,
                payload=request,
                preview_hash=payload_hash,
                decision="reject",
                result="invalid_token",
            )
            return {
                "status": "error",
                "message": "Confirmation token is invalid or expired.",
            }

        write_audit_log(
            tool="order_group_place",
            account=str(account) if account else None,
            payload=request,
            preview_hash=payload_hash,
            decision="confirm",
            result="executing",
        )
        result = await client.order_execution.place_order_group(request)
        write_audit_log(
            tool="order_group_place",
            account=str(account) if account else None,
            payload=request,
            preview_hash=payload_hash,
            decision="confirm",
            result="success",
        )
        return result

    order_group_place._ts_op_id = "D6"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D7 — GET /orderexecution/activationtriggers  (safe)
# ---------------------------------------------------------------------------


def register_order_list_activation_triggers(mcp: FastMCP, client: Any) -> None:
    """Register the ``order_list_activation_triggers`` tool (D7)."""

    @mcp.tool(name="order_list_activation_triggers")
    async def order_list_activation_triggers() -> Any:
        """List all available conditional activation triggers (D7).

        Returns the list of trigger types (e.g. STT, SST, STTS) that can
        be used with conditional orders.
        """
        return await client.order_execution.list_activation_triggers()

    order_list_activation_triggers._ts_op_id = "D7"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D8 — GET /orderexecution/routes  (safe)
# ---------------------------------------------------------------------------


def register_order_list_routes(mcp: FastMCP, client: Any) -> None:
    """Register the ``order_list_routes`` tool (D8)."""

    @mcp.tool(name="order_list_routes")
    async def order_list_routes() -> Any:
        """List all available order execution routes (D8).

        Returns the list of execution route names (e.g. AUTO, ARCX, NSDQ).
        """
        return await client.order_execution.list_routes()

    order_list_routes._ts_op_id = "D8"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Bulk registration
# ---------------------------------------------------------------------------


def register_all(
    mcp: FastMCP,
    client: Any,
    *,
    confirm_mode: str = "require",
    max_order_notional: float | None = None,
    allowed_symbols: list[str] | None = None,
) -> None:
    """Register all D-series order execution tools on *mcp*.

    Args:
        mcp: The FastMCP server instance.
        client: A ``TradeStationClient`` (or fake) providing ``.order_execution``.
        confirm_mode: Safety mode for destructive tools (off/require/review).
        max_order_notional: Maximum order notional value in USD.
        allowed_symbols: Allowlist of permitted symbols; empty = all allowed.
    """
    register_order_confirm(mcp, client)

    destructive_kwargs: dict[str, Any] = {
        "confirm_mode": confirm_mode,
        "max_order_notional": max_order_notional,
        "allowed_symbols": allowed_symbols or [],
    }

    register_order_place(mcp, client, **destructive_kwargs)
    register_order_replace(mcp, client, **destructive_kwargs)
    register_order_cancel(mcp, client, **destructive_kwargs)
    register_order_group_confirm(mcp, client)
    register_order_group_place(mcp, client, **destructive_kwargs)
    register_order_list_activation_triggers(mcp, client)
    register_order_list_routes(mcp, client)
