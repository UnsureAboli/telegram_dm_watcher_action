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
    آخرین پیام‌ها را بر اساس نوع و تعداد مشخص شده واکشی می‌کند.
    """
    messages: List[Message] = []

    # برای جلوگیری از واکشی تعداد زیادی پیام از هر چت، یک محدودیت اولیه در نظر می‌گیریم.
    # این یک بهینه‌سازی است تا مجبور نباشیم تمام پیام‌های هر چت را بخوانیم.
    fetch_limit_per_dialog = max(limit, 20)

    async for dialog in client.iter_dialogs(limit=None): # limit=None برای بررسی همه دیالوگ‌ها
        # فیلتر بر اساس نوع چت
        if message_type == "private":
            if not dialog.is_user or getattr(dialog.entity, "bot", False):
                continue
        elif message_type == "channel":
            if not dialog.is_channel:
                continue
        # برای 'all' هیچ فیلتری روی نوع دیالوگ اعمال نمی‌شود

        # فقط پیام‌های ورودی (نه خروجی) را در نظر می‌گیریم
        dialog_messages = await client.get_messages(dialog.entity, limit=fetch_limit_per_dialog)
        if dialog_messages:
            messages.extend(m for m in dialog_messages if not m.out)

    # مرتب‌سازی تمام پیام‌های جمع‌آوری شده بر اساس تاریخ (از جدید به قدیم)
    messages.sort(key=lambda m: m.date, reverse=True)

    # برگرداندن تعداد `limit` از جدیدترین پیام‌ها
    return messages[:limit]


def serialize_message_to_dict(m: Message) -> dict:
    """
    یک آبجکت پیام تلگرام را به یک دیکشنری پایتون قابل تبدیل به JSON تبدیل می‌کند.
    """
    # تعیین نام فرستنده
    sender_name = "Unknown"
    if m.sender:
        if getattr(m.sender, 'first_name', None):
            sender_name = m.sender.first_name
            if getattr(m.sender, 'last_name', None):
                sender_name += f" {m.sender.last_name}"
        elif getattr(m.sender, 'username', None):
            sender_name = f"@{m.sender.username}"
        elif getattr(m.sender, 'title', None):  # برای کانال‌ها
            sender_name = m.sender.title

    # تعیین محتوای پیام
    content = ""
    if m.message:
        content = m.message
    elif m.media:
        media_type = type(m.media).__name__.replace("MessageMedia", "")
        content = f"<Media: {media_type}>"
    else:
        content = "<Empty Message>"

    # تعیین نوع چت
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
    parser = argparse.ArgumentParser(description="پیام‌های تلگرام را بر اساس نوع و تعداد مشخص شده دریافت می‌کند.")
    parser.add_argument("--session", required=True, help="رشته session string تلگرام")
    parser.add_argument("--api-id", required=True, type=int, help="شناسه API تلگرام")
    parser.add_argument("--api-hash", required=True, help="هش API تلگرام")
    parser.add_argument(
        "--type",
        required=True,
        choices=["private", "channel", "all"],
        help="نوع پیام‌ها برای دریافت: private, channel, یا all",
    )
    parser.add_argument("--limit", type=int, default=10, help="تعداد پیام‌ها برای دریافت (پیش‌فرض: 10)")
    args = parser.parse_args()

    api_id = args.api_id
    api_hash = args.api_hash
    session_str = args.session

    try:
        # استفاده از StringSession جهت ورود بدون کد
        async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
            print(f"در حال واکشی {args.limit} پیام از نوع '{args.type}'...", file=sys.stderr)

            messages = await fetch_recent_messages(
                client, message_type=args.type, limit=args.limit
            )

            if not messages:
                print("✅ هیچ پیامی یافت نشد.", file=sys.stderr)
                print("[]")  # چاپ آرایه خالی JSON در خروجی اصلی
                return 0

            # تبدیل پیام‌ها به لیست دیکشنری‌ها
            output_data = [serialize_message_to_dict(m) for m in messages]

            # چاپ خروجی نهایی به صورت JSON
            # ensure_ascii=False برای پشتیبانی از حروف فارسی
            json_output = json.dumps(output_data, indent=2, ensure_ascii=False)
            print(json_output)

            print(f"✅ {len(messages)} پیام با موفقیت واکشی و در خروجی چاپ شد.", file=sys.stderr)

    except Exception as e:
        print(f"❌ خطایی در حین اجرای عملیات رخ داد: {e}", file=sys.stderr)
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
