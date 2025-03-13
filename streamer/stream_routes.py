import pyrogram
import re
import time
import asyncio
import json
import math
import hmac
import hashlib
import base64
import mimetypes
import logging
from random import choice
from itertools import cycle
from os import getenv
from typing import Union
from aiohttp import web
from aiohttp.web import Request
from pyrogram import raw
from streamer import utils
from streamer.exceptions import InvalidHash, FIleNotFound
from streamer.utils.constants import work_loads, multi_clients
from database.ia_filterdb import get_file_details, decode_file_ref
from pyrogram.file_id import FileId

logger = logging.getLogger("routes")
StartTime = time.time()

routes = web.RouteTableDef()
class_cache = {}
fileHolder = {}

SECRET_KEY = getenv("SECRET_KEY", "super_secret_key")  # Set a strong secret key!

# -------------------- TOKEN GENERATION & VALIDATION --------------------

def generate_download_token(file_id: str, expiry: int = 3600) -> str:
    """Generate a secure token for temporary file access."""
    expires_at = int(time.time()) + expiry
    data = f"{file_id}:{expires_at}"
    token = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{file_id}:{expires_at}:{token}".encode()).decode()

def validate_download_token(token: str) -> str:
    """Validate a token and extract the file ID."""
    try:
        decoded_data = base64.urlsafe_b64decode(token).decode()
        file_id, expires_at, received_hash = decoded_data.split(":")
        expected_hash = hmac.new(SECRET_KEY.encode(), f"{file_id}:{expires_at}".encode(), hashlib.sha256).hexdigest()
        
        if received_hash != expected_hash or int(expires_at) < int(time.time()):
            raise web.HTTPForbidden(text="Invalid or expired token")
        return file_id  # Return valid file ID
    except Exception:
        raise web.HTTPForbidden(text="Invalid token")

# -------------------- ROUTES --------------------

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": utils.get_readable_time(time.time() - StartTime),
            "loads": {f"bot{c+1}": l for c, (_, l) in enumerate(sorted(work_loads.items(), key=lambda x: x[1], reverse=True))}
        }
    )

@routes.get("/download")
async def download_handler(request: web.Request):
    """Handles secure download requests using token authentication."""
    token = request.query.get("token")
    if not token:
        raise web.HTTPForbidden(text="Missing token")

    file_id = validate_download_token(token)
    return await media_streamer(request, None, None, False, file_id)

async def media_streamer(request: web.Request, channel: Union[str, int], message_id: int, thumb: bool = False, file_id: str = None):
    """Handles secure media streaming from Telegram."""
    from tclient import tgclient as bot

    range_header = request.headers.get("Range")
    class_cache.setdefault(0, utils.ByteStreamer(bot))

    index = min(work_loads, key=work_loads.get)
    client = multi_clients[index]
    tg_connect = class_cache.setdefault(client, utils.ByteStreamer(client))

    file_id = await tg_connect.get_file_properties(channel, message_id, thumb, file_id)
    file_size = file_id.file_size

    from_bytes, until_bytes = 0, file_size - 1
    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            from_bytes = int(match.group(1))
            until_bytes = int(match.group(2)) if match.group(2) else until_bytes

    if until_bytes >= file_size or from_bytes < 0 or until_bytes < from_bytes:
        return web.Response(status=416, text="416: Range Not Satisfiable")

    chunk_size = 1024 * 1024
    offset = from_bytes - (from_bytes % chunk_size)
    body = yield_complete_part(math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size), channel, message_id, offset, chunk_size)
    
    mime_type = file_id.mime_type or mimetypes.guess_type(utils.get_name(file_id))[0] or "application/octet-stream"
    disposition = "inline" if "video/" in mime_type or "audio/" in mime_type else "attachment"

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": mime_type,
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(until_bytes - from_bytes + 1),
            "Content-Disposition": f'{disposition}; filename="{utils.get_name(file_id)}"',
            "Accept-Ranges": "bytes",
        },
    )

async def yield_complete_part(part_count, channel_id, message_id, offset, chunk_size, threads: int = 5):
    """Efficiently yields file parts using concurrent tasks."""
    clients = cycle(multi_clients.values())
    tasks = {}

    for current_part in range(1, part_count + 1):
        client = next(clients)
        tasks[current_part] = asyncio.create_task(
            yield_files(client, channel_id, message_id, current_part, offset, chunk_size)
        )
        offset += chunk_size

        if len(tasks) >= threads:
            done, _ = await asyncio.wait(tasks.values(), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                yield task.result()[1]
                tasks = {k: v for k, v in tasks.items() if v not in done}

    for task in tasks.values():
        yield (await task)[1]

async def yield_files(client, channel_id, message_id, current_part, offset, chunk_size):
    """Fetch file chunks efficiently using Telegram client."""
    streamer = class_cache.setdefault(client, utils.ByteStreamer(client))

    file_id = await streamer.generate_file_properties(channel_id, message_id, thumb=False)
    media_session = await streamer.generate_media_session(client, file_id)
    location = await streamer.get_location(file_id)

    response = await media_session.invoke(
        raw.functions.upload.GetFile(location=location, offset=offset, limit=chunk_size)
    )

    return current_part, response.bytes if isinstance(response, raw.types.upload.File) else b""

APP_AUTH_TOKEN = getenv("APP_AUTH_TOKEN", "")

def notVerified(request: Request):
    headers = request.headers
    return APP_AUTH_TOKEN and headers.get("Authorization") != APP_AUTH_TOKEN

@routes.get("/messageInfo")
async def getMessage(request: Request):
    """Fetches message information securely."""
    if notVerified(request):
        return web.json_response({"ok": False, "message": "UNAUTHORIZED"})

    bot = choice(list(multi_clients.values()))

    channel = request.query.get("channel")
    try:
        msgId = int(request.query.get("messageId"))
    except ValueError:
        return web.json_response({"ok": False, "message": "INVALID_RESPONSE"})

    try:
        channel = int(channel)
    except ValueError:
        pass

    message = await bot.get_messages(chat_id=channel, message_ids=msgId)
    return web.json_response(json.loads(str(message)))
