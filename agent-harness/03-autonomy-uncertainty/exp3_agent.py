import json

from llm import chat
from tools import get_order_history, get_policy, lookup_order, ask_customer

SYSTEM_PROMPT = """You are the brain of a customer-support agent.
Each turn you must PROPOSE exactly ONE next step.
Allowed actions:
- lookup_order(order_id)
- get_order_history(order_id)
- get_policy(status)
- ask_customer(question)
- finish()   # use when you have enough information to answer the customer
Reply with a single JSON object: {"action": "...", "args": {...}}"""


def propose_next_action(customer_message, observations):
    user_message = (
        f"Customer message: {customer_message}\n"
        f"Observations so far: {json.dumps(observations, ensure_ascii=False)}"
    )
    raw_text = chat(SYSTEM_PROMPT, user_message, json_mode=True)
    return json.loads(raw_text)


if __name__ == "__main__":
    print(propose_next_action("Đơn ORD-001 sao giao trễ vậy?", []))