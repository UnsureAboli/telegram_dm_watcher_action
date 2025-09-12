import os
import sys
import asyncio
import argparse
import json
from typing import List, Optional
from datetime import datetime

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message


async def fetch_recent_messages(
    client: TelegramClient, message_type: str, limit: int
) -> List[Message]:
    """
    Fetches the latest messages based on the specified type and limit.
    """
    messages: List[Message] = []

    # To avoid fetching too many messages from each chat, we set an initial limit.
    # This is an optimization to avoid reading all messages from every chat.
    fetch_limit_per_dialog = max(limit, 20)

    async for dialog in client.iter_dialogs(limit=None):  # limit=None to check all dialogs
        # Filter based on chat type
        if message_type == "private":
            if not dialog.is_user or getattr(dialog.entity, "bot", False):
                continue
        elif message_type == "channel":
            if not dialog.is_channel:
                continue
        # For 'all', no filter is applied to the dialog type

        # We only consider incoming messages (not outgoing)
        dialog_messages = await client.get_messages(dialog.entity, limit=fetch_limit_per_dialog)
        if dialog_messages:
            messages.extend(m for m in dialog_messages if not m.out)

    # Sort all collected messages by date (newest to oldest)
    messages.sort(key=lambda m: m.date, reverse=True)

    # Return the requested number of the most recent messages
    return messages[:limit]


def serialize_message_to_dict(m: Message) -> dict:
    """
    Converts a Telethon Message object to a JSON-serializable Python dictionary.
    """
    # Determine sender name
    sender_name = "Unknown"
    if m.sender:
        if getattr(m.sender, 'first_name', None):
            sender_name = m.sender.first_name
            if getattr(m.sender, 'last_name', None):
                sender_name += f" {m.sender.last_name}"
        elif getattr(m.sender, 'username', None):
            sender_name = f"@{m.sender.username}"
        elif getattr(m.sender, 'title', None):  # For channels
            sender_name = m.sender.title

    # Determine message content
    content = ""
    if m.message:
        content = m.message
    elif m.media:
        media_type = type(m.media).__name__.replace("MessageMedia", "")
        content = f"<Media: {media_type}>"
    else:
        content = "<Empty Message>"

    # Determine chat type
    chat_type = "unknown"
    if m.is_private:
        chat_type = "private"
    elif m.is_group:
        chat_type = "group"
    elif m.is_channel:
        chat_type = "channel"

    return {
        "sender": sender_name.strip(),
        "content": content,
        "date": m.date.isoformat() if m.date else None,
        "chat_type": chat_type,
        "sender_id": m.sender_id,
        "message_id": m.id,
    }


async def amain() -> int:
    parser = argparse.ArgumentParser(description="Fetch recent Telegram messages based on specified type and count.")
    parser.add_argument("--api-id", required=True, help="Your Telegram API ID")
    parser.add_argument("--api-hash", required=True, help="Your Telegram API Hash")
    parser.add_argument("--session", required=True, help="Telegram session string")
    parser.add_argument(
        "--type",
        required=True,
        choices=["private", "channel", "all"],
        help="Type of messages to fetch: private, channel, or all",
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of messages to fetch (default: 10)")
    args = parser.parse_args()

    try:
        api_id = int(args.api_id)
    except ValueError:
        print("❌ API ID must be an integer.", file=sys.stderr)
        return 1

    session_str = args.session
    api_hash = args.api_hash

    try:
        # Using StringSession to log in without a phone code
        async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
            print(f"Fetching {args.limit} messages of type '{args.type}'...", file=sys.stderr)

            messages = await fetch_recent_messages(
                client, message_type=args.type, limit=args.limit
            )

            if not messages:
                print("✅ No new messages found.", file=sys.stderr)
                print("[]")  # Print empty JSON array to stdout
                return 0

            # Convert messages to a list of dictionaries
            output_data = [serialize_message_to_dict(m) for m in messages]

            # Print the final output as JSON
            # ensure_ascii=False is used to support non-ASCII characters
            json_output = json.dumps(output_data, indent=2, ensure_ascii=False)
            print(json_output)

            print(f"✅ Successfully fetched and printed {len(messages)} messages.", file=sys.stderr)

    except Exception as e:
        print(f"❌ An error occurred during operation: {e}", file=sys.stderr)
        return 1

    return 0


def main() -> None:
    try:
        code = asyncio.run(amain())
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
