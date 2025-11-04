from pyrogram import Client, filters
from pyrogram.types import Message
import database
from config import ADMIN_IDS
import logging

logger = logging.getLogger(__name__)

async def init_api_commands(bot: Client):
    """Initialize API command handlers"""
    
    @bot.on_message(filters.command(["changeapi"]))
    async def change_api_cmd(bot: Client, m: Message):
        try:
            # Check if user is admin
            if m.from_user.id not in ADMIN_IDS:
                await m.reply_text(
                    "╭━━━━━━━━━━━━━━━━━╮\n"
                    "┣⪼ ❌ 𝐀𝐝𝐦𝐢𝐧 𝐎𝐧𝐥𝐲 𝐂𝐨𝐦𝐦𝐚𝐧𝐝\n"
                    "╰━━━━━━━━━━━━━━━━━╯"
                )
                return

            # Check command format
            if len(m.command) != 2:
                await m.reply_text(
                    "╭━━━━━━━━━━━━━━━━━╮\n"
                    "┣⪼ ℹ️ 𝐂𝐨𝐫𝐫𝐞𝐜𝐭 𝐅𝐨𝐫𝐦𝐚𝐭:\n"
                    "┣⪼ /changeapi new_url\n"
                    "╰━━━━━━━━━━━━━━━━━╯"
                )
                return

            new_url = m.command[1].strip()
            if not new_url.startswith(('http://', 'https://')):
                await m.reply_text(
                    "╭━━━━━━━━━━━━━━━━━╮\n"
                    "┣⪼ ❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐔𝐑𝐋 𝐟𝐨𝐫𝐦𝐚𝐭\n"
                    "┣⪼ 𝐌𝐮𝐬𝐭 𝐬𝐭𝐚𝐫𝐭 𝐰𝐢𝐭𝐡 𝐡𝐭𝐭𝐩:// 𝐨𝐫 𝐡𝐭𝐭𝐩𝐬://\n"
                    "╰━━━━━━━━━━━━━━━━━╯"
                )
                return

            # Update the API URL in the database
            success = await database.update_nirvana_api(new_url)
            if success:
                await m.reply_text(
                    "╭━━━━━━━━━━━━━━━━━╮\n"
                    "┣⪼ ✅ 𝐍𝐢𝐫𝐯𝐚𝐧𝐚 𝐏𝐥𝐚𝐲𝐞𝐫 𝐀𝐏𝐈 𝐔𝐩𝐝𝐚𝐭𝐞𝐝\n"
                    "╰━━━━━━━━━━━━━━━━━╯\n\n"
                    "╭─────────────────\n"
                    f"┣⪼ 🔗 𝐍𝐞𝐰 𝐔𝐑𝐋: {new_url}\n"
                    "╰─────────────────"
                )
            else:
                await m.reply_text(
                    "╭━━━━━━━━━━━━━━━━━╮\n"
                    "┣⪼ ❌ 𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐮𝐩𝐝𝐚𝐭𝐞 𝐀𝐏𝐈 𝐔𝐑𝐋\n"
                    "┣⪼ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐭𝐫𝐲 𝐚𝐠𝐚𝐢𝐧 𝐥𝐚𝐭𝐞𝐫\n"
                    "╰━━━━━━━━━━━━━━━━━╯"
                )

        except Exception as e:
            await m.reply_text(
                "╭━━━━━━━━━━━━━━━━━╮\n"
                f"┣⪼ ⚠️ 𝐄𝐫𝐫𝐨𝐫: {str(e)}\n"
                "╰━━━━━━━━━━━━━━━━━╯"
            )

    @bot.on_message(filters.command(["getapi"]))
    async def get_api_cmd(bot: Client, m: Message):
        try:
            # Check if user is admin
            if m.from_user.id not in ADMIN_IDS:
                await m.reply_text(
                    "╭━━━━━━━━━━━━━━━━━╮\n"
                    "┣⪼ ❌ 𝐀𝐝𝐦𝐢𝐧 𝐎𝐧𝐥𝐲 𝐂𝐨𝐦𝐦𝐚𝐧𝐝\n"
                    "╰━━━━━━━━━━━━━━━━━╯"
                )
                return

            # Get current API URL
            current_url = await database.get_nirvana_api()
            await m.reply_text(
                "╭━━━━━━━━━━━━━━━━━╮\n"
                "┣⪼ 🔗 𝐂𝐮𝐫𝐫𝐞𝐧𝐭 𝐍𝐢𝐫𝐯𝐚𝐧𝐚 𝐀𝐏𝐈\n"
                "╰━━━━━━━━━━━━━━━━━╯\n\n"
                "╭─────────────────\n"
                f"┣⪼ 🌐 𝐔𝐑𝐋: {current_url}\n"
                "╰─────────────────"
            )

        except Exception as e:
            await m.reply_text(
                "╭━━━━━━━━━━━━━━━━━╮\n"
                f"┣⪼ ⚠️ 𝐄𝐫𝐫𝐨𝐫: {str(e)}\n"
                "╰━━━━━━━━━━━━━━━━━╯"
            ) 