import time
from pathlib import Path

import httpx

from sap_tutor.history import MessageHistory


DEFAULT_SIGNAL_API_URL = "http://127.0.0.1:8080"


def message_key(envelope):
    timestamp = envelope.get("timestamp") or envelope.get("dataMessage", {}).get("timestamp")
    source = envelope.get("source") or envelope.get("sourceNumber") or "unknown"
    body = envelope.get("dataMessage", {}).get("message") or ""
    return f"{source}:{timestamp}:{body}"


def normalize_received_messages(result):
    if not result:
        return []
    if isinstance(result, list):
        items = result
    else:
        items = [result]

    messages = []
    for item in items:
        envelope = item.get("envelope", item)
        data_message = envelope.get("dataMessage") or {}
        body = data_message.get("message")
        if not body:
            continue

        group_info = data_message.get("groupInfo") or {}
        messages.append(
            {
                "body": body.strip(),
                "source": envelope.get("source") or envelope.get("sourceNumber"),
                "group_id": group_info.get("groupId"),
                "envelope": envelope,
            }
        )

    return messages


def should_reply(message, test_mode):
    body = message["body"]
    if test_mode:
        return True, body
    if body.startswith("/faq"):
        return True, body[4:].strip()
    return False, None


def send_signal_message(api_url, account, recipient, message, group_id=None):
    payload = {
        "message": message,
        "number": account,
        "recipients": [group_id] if group_id else [recipient],
    }
    try:
        response = httpx.post(f"{api_url}/v2/send", json=payload, timeout=60)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Failed to send message via REST API: {exc}")


def run(
    answer_fn,
    api_url=DEFAULT_SIGNAL_API_URL,
    poll_interval=2.0,
    test_mode=False,
    multi_account=False,
    account=None,
    db_path=None,
):
    if not account:
        raise SystemExit("Signal account is required for REST API. Set SIGNAL_ACCOUNT in .env")

    history = MessageHistory(db_path=db_path)

    # Automatically migrate from old JSON file if present
    history.migrate_from_json(Path(".signal-bot-seen.json"))

    while True:
        try:
            timeout_val = max(1, int(poll_interval))
            response = httpx.get(
                f"{api_url}/v1/receive/{account}",
                params={"timeout": timeout_val},
                timeout=timeout_val + 5
            )
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPError as exc:
            print(f"signal-cli REST connection error: {exc}")
            time.sleep(poll_interval)
            continue

        for message in normalize_received_messages(result):
            key = message_key(message["envelope"])
            if history.is_seen(key):
                continue

            should_send, query = should_reply(message, test_mode)
            envelope = message["envelope"]
            timestamp = (
                envelope.get("timestamp")
                or envelope.get("dataMessage", {}).get("timestamp")
                or 0
            )

            # Store message in history as seen immediately to avoid processing it again
            history.add_message(
                message_key=key,
                source=message["source"] or "unknown",
                timestamp=timestamp,
                body=message["body"],
                group_id=message["group_id"],
                is_faq=should_send,
                query=query,
            )

            if not should_send:
                continue

            try:
                if not query:
                    reply_text = "Після /faq напишіть питання. Наприклад: /faq Як сторнувати документ матеріалу?"
                else:
                    result = answer_fn(query)
                    reply_text = result["text"]
                    if result["sources"]:
                        reply_text += "\n\nДжерела: " + ", ".join(result["sources"])

                send_signal_message(
                    api_url=api_url,
                    account=account,
                    recipient=message["source"],
                    message=reply_text,
                    group_id=message["group_id"],
                )

                # Store the reply in SQLite DB
                history.update_reply(key, reply_text)

                target = message["group_id"] or message["source"]
                print(f"Answered message from {target}")
            except Exception as exc:
                target = message["group_id"] or message["source"]
                print(f"Failed to answer message from {target}: {exc}")

        time.sleep(poll_interval)
