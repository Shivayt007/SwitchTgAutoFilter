import asyncio, re, ast, math, logging, pyrogram
from pyrogram.errors.exceptions.bad_request_400 import (
    MediaEmpty,
    PhotoInvalidDimensions,
    WebpageMediaEmpty,
)
from Script import script
from utils import get_shortlink
from config import SPELL_FILTER, SPELL_FILTER_VERBOSE
from tgconfig import (
    AUTH_USERS,
    PM_IMDB,
    SINGLE_BUTTON,
    PROTECT_CONTENT,
    SPELL_CHECK_REPLY,
    IMDB_TEMPLATE,
    IMDB_DELET_TIME,
    PMFILTER,
    G_FILTER,
    SHORT_URL,
    SHORT_API,
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import (
    get_size,
    get_poster,
    search_gagala,
    temp,
)
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results
from tgplugins.group_filter import global_filters
from tgconfig import DISABLE_PM_SEARCH
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


@Client.on_message(
    filters.private & filters.text & filters.chat(AUTH_USERS)
    if AUTH_USERS
    else filters.text & filters.private
)
async def auto_pm_fill(b, m):
    if DISABLE_PM_SEARCH:
        return

    if PMFILTER:
        if G_FILTER:
            kd = await global_filters(b, m)
            if kd == False:
                await pm_AutoFilter(b, m)
        else:
            await pm_AutoFilter(b, m)
    else:
        return


@Client.on_callback_query(filters.regex("shorturl"))
async def openShort(bot, query):
    files = query.data.split("|")[-1]
    file = await get_file_details(files)

    # link = get_shortlink(f'https://telegram.dog/{temp.U_NAME}?start=files_{file.file_id}')
    await bot.send_message(
        chat_id=query.from_user.id,
        text=f"{file.file_name}\n\n{file.file_size}\n\n{get_shortlink(f'https://telegram.dog/{temp.U_NAME}?start=files_{files}')}",
    )
    await query.answer("Check On Pm Of Bot", show_alert=True)


@Client.on_callback_query(
    filters.create(lambda _, __, query: query.data.startswith("pmnext"))
)
async def pm_next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    try:
        offset = int(offset)
    except:
        offset = 0
    search = temp.PM_BUTTONS.get(str(key))
    if not search:
        return await query.answer(
            "Yᴏᴜ Aʀᴇ Usɪɴɢ Oɴᴇ Oғ Mʏ Oʟᴅ Mᴇssᴀɢᴇs, Pʟᴇᴀsᴇ Sᴇɴᴅ Tʜᴇ Rᴇǫᴜᴇsᴛ Aɢᴀɪɴ",
            show_alert=True,
        )

    files, n_offset, total = await get_search_results(
        search.lower(), offset=offset, filter=True
    )
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0
    if not files:
        return

    if SHORT_URL and SHORT_API:
        if SINGLE_BUTTON:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {file.file_name}",
                        callback_data=f"shorturl|{file.file_id}",
                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}",
                        callback_data=f"shorturl|{file.file_id}",
                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                        callback_data=f"shorturl|{file.file_id}",
                    ),
                ]
                for file in files
            ]
    else:
        if SINGLE_BUTTON:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {getattr(file, 'description', file.file_name)}",
                        callback_data=f"pmfile#{file.file_id}",
                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}", callback_data=f"pmfile#{file.file_id}"
                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                        callback_data=f"pmfile#{file.file_id}",
                    ),
                ]
                for file in files
            ]

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                "🔗 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ 🔗", url=f"https://t.me/tgtamillinks/49"
            )
        ],
    )
    if 0 < offset <= 10:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - 10
    if n_offset == 0:
        btn.append(
            [
                InlineKeyboardButton(
                    "⬅️ ʙᴀᴄᴋ", callback_data=f"pmnext_{req}_{key}_{off_set}"
                ),
                InlineKeyboardButton(
                    f"❄️ ᴩᴀɢᴇꜱ {(offset or 0) + 1} / {math.ceil(total / 10)}",
                    callback_data="pages",
                ),
            ]
        )
    elif off_set is None:
        btn.append(
            [
                InlineKeyboardButton(
                    f"❄️ {(offset or 0) + 1} / {math.ceil(total / 10)}",
                    callback_data="pages",
                ),
                InlineKeyboardButton(
                    "ɴᴇxᴛ ➡️", callback_data=f"pmnext_{req}_{key}_{n_offset}"
                ),
            ]
        )
    else:
        btn.append(
            [
                InlineKeyboardButton(
                    "⬅️ ʙᴀᴄᴋ", callback_data=f"pmnext_{req}_{key}_{off_set}"
                ),
                InlineKeyboardButton(
                    f"❄️ {offset + 1} / {math.ceil(total / 10)}",
                    callback_data="pages",
                ),
                InlineKeyboardButton(
                    "ɴᴇxᴛ ➡️", callback_data=f"pmnext_{req}_{key}_{n_offset}"
                ),
            ]
        )
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    await query.answer()


@Client.on_callback_query(
    filters.create(lambda _, __, query: query.data.startswith("pmspolling"))
)
async def pm_spoll_tester(bot, query):
    if DISABLE_PM_SEARCH:
        return

    _, user, movie_ = query.data.split("#")
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    movies = temp.PM_SPELL.get(str(query.message.reply_to_message.id))
    if not movies:
        return await query.answer(
            "Yᴏᴜ Aʀᴇ Usɪ��ɢ Oɴᴇ Oғ Mʏ Oʟᴅ Mᴇssᴀɢᴇs, Pʟᴇᴀsᴇ Sᴇɴᴅ Tʜᴇ Rᴇǫᴜᴇsᴛ Aɢᴀɪɴ",
            show_alert=True,
        )
    movie = movies[(int(movie_))]
    await query.answer("Cʜᴇᴄᴋɪɴɢ Fᴏʀ Mᴏᴠɪᴇ Iɴ Dᴀᴛᴀʙᴀsᴇ...")
    files, offset, total_results = await get_search_results(movie, offset=0)
    if files:
        k = (movie, files, offset, total_results)
        await pm_AutoFilter(bot, query, k)
    else:
        k = await query.message.edit("Tʜɪs Mᴏᴠɪᴇ Nᴏᴛ Fᴏᴜɴᴅ Iɴ Dᴀᴛᴀʙᴀsᴇ")
        await asyncio.sleep(10)
        await k.delete()


async def pm_AutoFilter(client, msg, pmspoll=False):
    if not pmspoll:
        message = msg
        if message.text.startswith("/"):
            return  # ignore commands
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if 2 < len(message.text) < 100:
            search = message.text
            files, offset, total_results = await get_search_results(
                search.lower(), offset=0, filter=True
            )
            print(files, offset, total_results)
            if not files:
                return await pm_spoll_choker(msg)
        else:
            return
    else:
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = pmspoll
    pre = "pmfilep" if PROTECT_CONTENT else "pmfile"

    if SHORT_URL and SHORT_API:
        if SINGLE_BUTTON:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {file.file_name}",
                        callback_data=f"shorturl|{file.file_id}",
                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}",
                        callback_data=f"shorturl|{file.file_id}",
                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                        callback_data=f"shorturl|{file.file_id}",
                    ),
                ]
                for file in files
            ]
    else:
        if SINGLE_BUTTON:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {getattr(file, 'description', file.file_name)}",
                        callback_data=f"{pre}#{file.file_id}",
                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}",
                        callback_data=f"{pre}#{req}#{file.file_id}",
                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                        callback_data=f"{pre}#{file.file_id}",
                    ),
                ]
                for file in files
            ]

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                "🔗 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ 🔗", url=f"https://t.me/tgtamillinks/49"
            )
        ],
    )
    if offset != "":
        key = f"{message.id}"
        temp.PM_BUTTONS[key] = search
        req = message.from_user.id if message.from_user else 0
        btn.append(
            [
                InlineKeyboardButton(
                    text=f"❄️ ᴩᴀɢᴇꜱ 1/{math.ceil(int(total_results) / 10)}",
                    callback_data="pages",
                ),
                InlineKeyboardButton(
                    text="ɴᴇxᴛ ➡️", callback_data=f"pmnext_{req}_{key}_{offset}"
                ),
            ]
        )
    else:
        btn.append([InlineKeyboardButton(text="❄️ ᴩᴀɢᴇꜱ 1/1", callback_data="pages")])
    if PM_IMDB:
        imdb = await get_poster(search)
    else:
        imdb = None
    TEMPLATE = IMDB_TEMPLATE
    if imdb:
        cap = TEMPLATE.format(
            group=message.chat.title,
            requested=message.from_user.mention,
            query=search,
            title=imdb["title"],
            votes=imdb["votes"],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb["box_office"],
            localized_title=imdb["localized_title"],
            kind=imdb["kind"],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb["release_date"],
            year=imdb["year"],
            genres=imdb["genres"],
            poster=imdb["poster"],
            plot=imdb["plot"],
            rating=imdb["rating"],
            url=imdb["url"],
            **locals(),
        )
    else:
        cap = f"Hᴇʀᴇ Is Wʜᴀᴛ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Qᴜᴇʀʏ {search}"
    if imdb and imdb.get("poster"):
        try:
            hehe = await message.reply_photo(
                photo=imdb.get("poster"),
                caption=cap,
                quote=True,
                reply_markup=InlineKeyboardMarkup(btn),
            )
            await asyncio.sleep(IMDB_DELET_TIME)
            await hehe.delete()
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get("poster")
            poster = pic.replace(".jpg", "._V1_UX360.jpg")
            hmm = await message.reply_photo(
                photo=poster,
                caption=cap,
                quote=True,
                reply_markup=InlineKeyboardMarkup(btn),
            )
            await asyncio.sleep(IMDB_DELET_TIME)
            await hmm.delete()
        except Exception as e:
            logger.exception(e)
            cdp = await message.reply_text(
                cap, quote=True, reply_markup=InlineKeyboardMarkup(btn)
            )
            await asyncio.sleep(IMDB_DELET_TIME)
            await cdp.delete()
    else:
        abc = await message.reply_text(
            cap, quote=True, reply_markup=InlineKeyboardMarkup(btn)
        )
        await asyncio.sleep(IMDB_DELET_TIME)
        await abc.delete()
    if pmspoll:
        await msg.message.delete()


async def pm_spoll_choker(msg):
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "",
        msg.text,
        flags=re.IGNORECASE,
    )
    query = query.strip() + " movie"
    logger.info(f"Searching for: {query}")
    g_s = await search_gagala(query)
    g_s += await search_gagala(msg.text)
    logger.info(f"Search results: {g_s}")
    
    if not g_s:
        k = await msg.reply("I Cᴏᴜʟᴅɴ'ᴛ Fɪɴᴅ Aɴʏ Mᴏᴠɪᴇ Iɴ Tʜᴀᴛ Nᴀᴍᴇ", quote=True)
        await asyncio.sleep(10)
        return await k.delete()

    def extract_movie_name(result):
        patterns = [
            r'(?:.*?›.*?)?([^›]+?)\s*\(\d{4}\)',
            r'(?:.*?›.*?)?([^›]+?)\s*-\s*(?:IMDb|Wikipedia|BookMyShow)',
            r'Watch\s+([^›]+?)\s*(?:-|\|)',
            r'(?:.*?›.*?)?([^›]+?)\s*(?:Full Movie|Movie)',
            r'(?:.*?›.*?)?([^›]+?)\s*\|\s*.*?(?:Movie|Film)',
            r'(?:OFFICIAL.*?MOVIE\s*-\s*)([^›]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def clean_movie_name(name):
        name = re.sub(r'^.*?›\s*', '', name)
        name = re.sub(r'^.*?(?:tt\d+|www\.[^›]+›)', '', name)
        name = re.sub(r"(\-|\(|\)|_)", " ", name)
        name = re.sub(r"\b(imdb|wikipedia|reviews|full|all|episode(s)?|film|movie|series|official|trailer|video song|videos|songs)\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r'\|.*', '', name)
        name = re.sub(r'\d{4}\s*AD', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'\s+\d{4}$', '', name)
        name = re.sub(r'(.+?)\1+', r'\1', name)
        
        invalid_entries = ['images', 'videos', 'search', 'news']
        if name.lower() in invalid_entries:
            return None
        
        return name

    def fuzzy_dedupe(names, threshold=75):
        unique_names = []
        for name in names:
            if not unique_names or all(fuzz.ratio(name, un) < threshold for un in unique_names):
                unique_names.append(name)
        return unique_names

    movie_names = []
    for result in g_s:
        movie_name = extract_movie_name(result)
        if movie_name:
            cleaned_name = clean_movie_name(movie_name)
        else:
            cleaned_name = clean_movie_name(result)
        
        if cleaned_name and len(cleaned_name) > 1:
            movie_names.append(cleaned_name)

    unique_names = fuzzy_dedupe(movie_names)
    
    if not unique_names:
        k = await msg.reply(
            "I Cᴏᴜʟᴅɴ'ᴛ Fɪɴᴅ Aɴʏᴛʜɪɴɢ Rᴇʟᴀᴛᴇᴅ Tᴏ Tʜᴀᴛ. Cʜᴇᴄᴋ Yᴏᴜʀ Sᴘᴇʟʟɪɴɢ", quote=True
        )
        await asyncio.sleep(10)
        return await k.delete()

    movielist = unique_names
    temp.PM_SPELL[str(msg.id)] = movielist

    user = msg.from_user.id if msg.from_user else 0

    async def check_results(query, clb):
        query = query.strip()
        res = await get_file_details(query)
        if res:
            return [InlineKeyboardButton(query, callback_data=clb)]

    if SPELL_FILTER and SPELL_FILTER_VERBOSE:
        filtered = await asyncio.gather(
            *[
                check_results(movie, f"pmspolling#{user}#{k}")
                for k, movie in enumerate(movielist)
            ]
        )
        if not filtered:
            await msg.reply("I Cᴏᴜʟᴅɴ'ᴛ Fɪɴᴅ Aɴʏᴛʜɪɴɢ Rᴇʟᴀᴛᴇᴅ Tᴏ Tʜᴀᴛ", quote=True)
            return
        btn = [list(filter(lambda x: x, filtered))]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=movie.strip(), callback_data=f"pmspolling#{user}#{k}"
                )
            ]
            for k, movie in enumerate(movielist)
        ]
    btn.append(
        [
            InlineKeyboardButton(
                text="Close", callback_data=f"pmspolling#{user}#close_spellcheck"
            )
        ]
    )
    await msg.reply(
        "I Cᴏᴜʟᴅɴ'ᴛ Fɪɴᴅ Aɴʏᴛʜɪɴɢ Rᴇʟᴀᴛᴇᴅ Tᴏ Tʜᴀᴛ. Dɪᴅ Yᴏᴜ Mᴇᴀɴ Aɴʏ Oɴᴇ Oғ Tʜᴇsᴇ?",
        reply_markup=InlineKeyboardMarkup(btn),
        quote=True,
    )
