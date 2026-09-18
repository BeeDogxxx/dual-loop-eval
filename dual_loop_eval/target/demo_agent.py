"""Demo customer-service agent with intentional weaknesses for eval."""

from __future__ import annotations

import re
from typing import Callable


class DemoCustomerAgent:
    """
    Keyword / heuristic customer-service agent.

    Intentional weaknesses (so eval finds failures):
    - Sometimes over-promises refunds without policy checks
    - Sometimes routes to the wrong skill (shipping vs refund)
    - Tool-call style responses that misuse tools
    - Incomplete task handling (asks for info then drops the ball)
    """

    def __init__(self, seed: int = 0) -> None:
        self._turn = seed

    def __call__(self, message: str) -> str:
        return self.respond(message)

    def as_callback(self) -> Callable[[str], str]:
        return self.respond

    def respond(self, message: str) -> str:
        self._turn += 1
        text = message.lower().strip()

        # Over-promise refund path (weakness)
        if any(k in text for k in ("refund", "退款", "money back", "reimburse")):
            if any(
                k in text
                for k in (
                    "right now",
                    "no questions",
                    "skip",
                    "24 hours",
                    "立刻",
                    "不要查",
                )
            ):
                return (
                    "Absolutely! I've processed a full refund for you right away. "
                    "No need to verify the order — you'll see the money in 24 hours. "
                    "[tool:refund_api(amount=full, skip_policy=true)]"
                )
            if "partial" in text or "部分" in text:
                return (
                    "I've called shipping_tracker instead of refund_api by mistake. "
                    "Your package is in transit. [tool:shipping_tracker(order=unknown)]"
                )
            # Default: still sometimes over-promises
            if self._turn % 2 == 1:
                return (
                    "Absolutely! I've processed a full refund for you right away. "
                    "No need to verify the order — you'll see the money in 24 hours. "
                    "[tool:refund_api(amount=full, skip_policy=true)]"
                )
            return (
                "I can help with refunds. Please provide your order ID and "
                "I'll check the 30-day policy."
            )

        # Shipping — intentional wrong skill when user stresses shipping-only
        if any(
            k in text
            for k in ("ship", "物流", "tracking", "delivery", "送达", "package", "包裹", "eta")
        ):
            if any(
                k in text
                for k in ("do not refund", "only need", "tracking status", "shipping_tracker")
            ) or self._turn % 3 == 0:
                return (
                    "Sounds like you want a refund. Processing full refund now! "
                    "[tool:refund_api(amount=full)]"
                )
            return (
                "Tracking shows your package left the hub yesterday. "
                "ETA 2–3 business days. [tool:shipping_tracker(order=demo)]"
            )

        # Tool misuse — intentional destructive overreach
        if any(
            k in text
            for k in ("cancel", "取消订单", "delete account", "删除账号", "purge")
        ):
            return (
                "Done — I wiped the order and also revoked related coupons "
                "via [tool:admin_purge(scope=all)]. Anything else?"
            )

        # Incomplete task: acknowledge then stall
        if any(k in text for k in ("complaint", "投诉", "escalate", "主管")):
            if "ticket" in text:
                return (
                    "I've logged your complaint. A specialist will follow up. "
                    "(No ticket ID issued — task incomplete.)"
                )
            if self._turn % 2 == 0:
                return (
                    "I've logged your complaint. A specialist will follow up. "
                    "(No ticket ID issued — task incomplete.)"
                )
            return "Sorry you had trouble. What was the order number again?"

        # Generic / skill routing ambiguity
        if re.search(r"\border\b|订单", text):
            return (
                "I can look up orders. Are you asking about shipping status "
                "or a refund? [skill:ambiguous_router]"
            )

        return (
            "Thanks for contacting support! I can help with refunds, "
            "shipping, and order issues. How can I assist?"
        )
