class ToolError(Exception):
    pass


ORDERS = {
    "ORD-001": {"status": "delayed", "eta": "2026-10-22"},
}

ORDER_HISTORY = {
    "ORD-001": [{"event": "address_changed", "date": "2026-10-15"}],
}

POLICIES = {
    "delayed": "Apologize and offer a 20k voucher. Changing the address may add 2 days to delivery.",
}

failures_left = 0


def set_failures(count):
    global failures_left
    failures_left = count


def lookup_order(order_id):
    global failures_left
    if failures_left > 0:
        failures_left -= 1
        raise ToolError("order service timeout")
    return ORDERS[order_id]


def get_order_history(order_id):
    return ORDER_HISTORY.get(order_id, [])


def get_policy(status):
    return POLICIES.get(status, "No policy found")


def ask_customer(question):
    return f"[asked customer] {question}"