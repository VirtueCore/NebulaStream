import asyncio
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote, unquote, urljoin, urlparse

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nebulastream")

class Config:
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "7001"))
    CACHE_TTL = int(os.getenv("CACHE_TTL", "1800"))
    CACHE_TTL_CATALOG = int(os.getenv("CACHE_TTL_CATALOG", "3600"))
    DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ANILIST_GQL = "https://graphql.anilist.co"
    MEGAVID_API = "https://megavid.buzz/api/ani/{anilist_id}/{episode}/{lang}"
    MEGAVID_REFERER = "https://megavid.buzz/"
    STATIC_DIR = Path(__file__).parent / "static"
    TEMPLATES_DIR = Path(__file__).parent / "templates"

class AppState:
    client: Optional[httpx.AsyncClient] = None
    stream_cache: Dict[str, dict] = {}
    catalog_cache: Dict[str, dict] = {}
    home_cache: Optional[dict] = None
    home_cache_ts: float = 0.0
    cache_lock = asyncio.Lock()
    in_flight: Dict[str, asyncio.Task] = {}

state = AppState()

# ------------------------------------------------------------------------------
def get_current_season():
    month = datetime.now().month
    year = datetime.now().year
    if month in (1, 2, 3):
        season = "WINTER"
    elif month in (4, 5, 6):
        season = "SPRING"
    elif month in (7, 8, 9):
        season = "SUMMER"
    else:
        season = "FALL"
    return season, year

async def _fetch_media_list(variables: dict) -> tuple:
    has_genre = bool(variables.get("genre"))
    genre_var_decl = "$genre: String, " if has_genre else ""
    genre_arg = "genre_in: [$genre], " if has_genre else ""

    query = f"""
    query ($page: Int, $perPage: Int, {genre_var_decl}$sort: [MediaSort], $season: MediaSeason, $seasonYear: Int, $status: MediaStatus, $format: MediaFormat) {{
        Page(page: $page, perPage: $perPage) {{
            media({genre_arg}sort: $sort, type: ANIME, format: $format, season: $season, seasonYear: $seasonYear, status: $status) {{
                id
                title {{ romaji english }}
                coverImage {{ large }}
                bannerImage
                episodes
                seasonYear
                genres
                format
                status
                description(asHtml: false)
                nextAiringEpisode {{ airingAt episode }}
                startDate {{ year month day }}
                averageScore
                popularity
            }}
            pageInfo {{ hasNextPage }}
        }}
    }}
    """
    if not has_genre:
        variables.pop("genre", None)

    try:
        resp = await state.client.post(
            Config.ANILIST_GQL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=20.0
        )
        if resp.status_code != 200:
            logger.error(f"AniList returned {resp.status_code}: {resp.text[:200]}")
            return [], False
        data = resp.json()
        if not data:
            logger.error("Empty response from AniList")
            return [], False
        media_list = data.get("data", {}).get("Page", {}).get("media", [])
        has_next = data.get("data", {}).get("Page", {}).get("pageInfo", {}).get("hasNextPage", False)
    except Exception as e:
        logger.error(f"AniList fetch error: {e}")
        return [], False

    metas = []
    for m in media_list:
        title = m["title"].get("english") or m["title"].get("romaji") or "Unknown"
        metas.append({
            "id": m["id"],
            "title": title,
            "poster": m["coverImage"]["large"],
            "banner": m.get("bannerImage"),
            "episodes": m.get("episodes") or 0,
            "year": m.get("seasonYear"),
            "genres": m.get("genres", []),
            "format": m.get("format"),
            "status": m.get("status"),
            "description": m.get("description"),
            "nextAiringEpisode": m.get("nextAiringEpisode"),
            "startDate": m.get("startDate"),
            "score": m.get("averageScore"),
            "popularity": m.get("popularity"),
        })
    return metas, has_next

async def fetch_home_data() -> dict:
    now = time.time()
    if state.home_cache and (now - state.home_cache_ts < 1800):
        return state.home_cache

    season, year = get_current_season()
    try:
        hero_metas, _ = await _fetch_media_list({"page": 1, "perPage": 1, "sort": "TRENDING_DESC", "format": "TV"})
        hero = hero_metas[0] if hero_metas else None
    except:
        hero = None

    tasks = {
        "trending": _fetch_media_list({"page": 1, "perPage": 20, "sort": "TRENDING_DESC", "format": "TV"}),
        "popular_season": _fetch_media_list({"page": 1, "perPage": 20, "season": season, "seasonYear": year, "sort": "POPULARITY_DESC", "format": "TV"}),
        "recent": _fetch_media_list({"page": 1, "perPage": 20, "sort": "ID_DESC", "format": "TV"}),
        "coming_soon": _fetch_media_list({"page": 1, "perPage": 20, "status": "NOT_YET_RELEASED", "sort": "POPULARITY_DESC", "format": "TV"}),
    }

    results = {"hero": hero}
    for key, coro in tasks.items():
        try:
            metas, _ = await coro
            results[key] = metas
        except:
            results[key] = []

    state.home_cache = results
    state.home_cache_ts = now
    return results

async def fetch_megavid(anilist_id: int, episode: int, lang: str) -> Optional[dict]:
    url = Config.MEGAVID_API.format(anilist_id=anilist_id, episode=episode, lang=lang)
    headers = {"User-Agent": Config.DEFAULT_UA, "Referer": Config.MEGAVID_REFERER}
    last_error = None

    for attempt in range(3):
        try:
            resp = await state.client.get(url, headers=headers, timeout=30.0)

            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                if resp.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(1 + attempt)
                    continue
                return None

            data = resp.json()
            payload = data.get("data") if isinstance(data.get("data"), dict) else data

            # Check alternative keys in case of API schema shifts
            source = (
                data.get("source") or payload.get("source") or
                data.get("file") or payload.get("file") or
                data.get("link") or payload.get("link")
            )

            if not source:
                logger.warning(
                    f"No stream found for ani={anilist_id} ep={episode} ({lang}). "
                    f"Keys returned -> Root: {list(data.keys())} | Payload: {list(payload.keys()) if isinstance(payload, dict) else type(payload)}"
                )
                # Immediately return None to avoid hitting the endpoint repeatedly when no media source exists
                return None

            if data.get("tracks") is None and isinstance(payload.get("tracks"), list):
                data["tracks"] = payload["tracks"]

            data["source"] = source
            return data

        except (httpx.HTTPError, ValueError) as e:
            last_error = str(e)
            await asyncio.sleep(1 + attempt)

    logger.warning(f"Megavid fetch failed for ani={anilist_id} ep={episode} lang={lang}: {last_error}")
    return None

def build_headers(target_url: str, referer: str, incoming_headers: Optional[dict] = None) -> dict:
    domain = urlparse(target_url).netloc
    headers = {"User-Agent": Config.DEFAULT_UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
    if "megavid.buzz" in domain:
        headers["Origin"] = "https://megavid.buzz"
        headers["Referer"] = "https://megavid.buzz/"
    else:
        if referer:
            headers["Referer"] = referer
            headers["Origin"] = f"{urlparse(referer).scheme}://{urlparse(referer).netloc}"
        else:
            headers["Origin"] = f"{urlparse(target_url).scheme}://{domain}"
    if incoming_headers:
        for k, v in incoming_headers.items():
            if k.lower() in ("range", "if-none-match"):
                headers[k.capitalize()] = v
    return headers

async def fetch_upstream_m3u8(target_url: str, ref_header: str) -> str:
    headers = build_headers(target_url, ref_header)
    for _ in range(3):
        resp = await state.client.get(target_url, headers=headers)
        if resp.status_code == 200:
            return resp.text
        await asyncio.sleep(0.5)
    raise HTTPException(502, "Upstream M3U8 fetch failed")

async def proxy_segment(target_url: str, ref_header: str, req: Request):
    headers = build_headers(target_url, ref_header, dict(req.headers))
    async def chunk_generator():
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=60.0)) as client:
            async with client.stream("GET", target_url, headers=headers, follow_redirects=True) as resp:
                if resp.status_code not in (200, 206):
                    raise HTTPException(resp.status_code, "Segment fetch failed")
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk
    return StreamingResponse(chunk_generator(), status_code=200, media_type="video/mp2t",
                             headers={"Access-Control-Allow-Origin": "*", "Accept-Ranges": "bytes"})

async def proxy_subtitle(target_url: str):
    headers = {"User-Agent": Config.DEFAULT_UA, "Referer": Config.MEGAVID_REFERER}
    resp = await state.client.get(target_url, headers=headers)
    return Response(content=resp.text, media_type="text/vtt", headers={"Access-Control-Allow-Origin": "*"})

# ------------------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    state.client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(10.0, read=30.0),
        limits=httpx.Limits(max_keepalive_connections=100, max_connections=300)
    )
    logger.info("NebulaStream started.")
    yield
    await state.client.aclose()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Config.STATIC_DIR), name="static")

# ------------------------------------------------------------------------------
# API Routes
# ------------------------------------------------------------------------------
@app.get("/api/home")
async def home():
    return await fetch_home_data()

@app.get("/api/catalog")
async def api_catalog(genre: Optional[str] = None, page: int = 1, perPage: int = 30, sort: str = "TRENDING_DESC"):
    variables = {"page": page, "perPage": perPage, "sort": sort, "format": "TV"}
    if genre:
        variables["genre"] = genre
    metas, has_next = await _fetch_media_list(variables)
    return {"metas": metas, "hasNextPage": has_next}

@app.get("/api/genres")
async def api_genres():
    return [
        "Action", "Adventure", "Comedy", "Drama", "Ecchi", "Fantasy",
        "Horror", "Mahou Shoujo", "Mecha", "Music", "Mystery", "Psychological",
        "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Thriller"
    ]

@app.get("/api/search")
async def api_search(q: str):
    query = """
    query ($search: String) {
        Page(page: 1, perPage: 20) {
            media(search: $search, type: ANIME) {
                id title { romaji english } coverImage { large } episodes seasonYear genres format status averageScore
            }
        }
    }
    """
    resp = await state.client.post(Config.ANILIST_GQL,
                                   json={"query": query, "variables": {"search": q}},
                                   headers={"Content-Type": "application/json"})
    media = resp.json().get("data", {}).get("Page", {}).get("media", [])
    return [{"id": m["id"], "title": m["title"].get("english") or m["title"].get("romaji") or "",
             "poster": m["coverImage"]["large"], "episodes": m.get("episodes") or 0,
             "year": m.get("seasonYear"), "genres": m.get("genres", []),
             "score": m.get("averageScore")} for m in media]

@app.get("/api/episodes/{anilist_id}")
async def api_episodes(anilist_id: str):
    clean = anilist_id.replace("anilist:", "")
    try:
        aid = int(clean)
    except:
        return {"total": 0}
    query = """
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            episodes
            nextAiringEpisode { episode }
        }
    }
    """
    resp = await state.client.post(Config.ANILIST_GQL,
                                   json={"query": query, "variables": {"id": aid}},
                                   headers={"Content-Type": "application/json"})
    data = resp.json().get("data", {}).get("Media", {})
    if not data:
        return {"total": 0}
    total = data.get("episodes")
    if total is None or total == 0:
        next_ep = data.get("nextAiringEpisode")
        if next_ep and next_ep.get("episode"):
            total = next_ep["episode"] - 1
    return {"total": max(total or 0, 0)}

@app.get("/api/anime/{anilist_id}")
async def anime_details(anilist_id: str):
    clean = anilist_id.replace("anilist:", "")
    query = """
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english native }
            coverImage { large }
            bannerImage
            description(asHtml: false)
            genres
            episodes
            seasonYear
            format
            status
            averageScore
            popularity
            nextAiringEpisode { airingAt episode }
            startDate { year month day }
            recommendations(sort: RATING_DESC) {
                edges {
                    node {
                        mediaRecommendation {
                            id
                            title { romaji english }
                            coverImage { large }
                            averageScore
                            episodes
                            seasonYear
                            format
                        }
                    }
                }
            }
            relations {
                edges {
                    relationType
                    node {
                        id
                        title { romaji english }
                        coverImage { large }
                        format
                        episodes
                        seasonYear
                    }
                }
            }
        }
    }
    """
    resp = await state.client.post(Config.ANILIST_GQL,
                                   json={"query": query, "variables": {"id": int(clean)}},
                                   headers={"Content-Type": "application/json"})
    media = resp.json().get("data", {}).get("Media", {})
    if not media:
        raise HTTPException(status_code=404, detail="Anime not found")

    recs = []
    for edge in media.get("recommendations", {}).get("edges", []):
        node = edge.get("node", {}).get("mediaRecommendation", {})
        if node:
            recs.append({
                "id": node["id"],
                "title": node["title"].get("english") or node["title"].get("romaji") or "?",
                "poster": node["coverImage"]["large"],
                "score": node.get("averageScore"),
                "episodes": node.get("episodes"),
                "year": node.get("seasonYear"),
                "format": node.get("format"),
            })
    media["recommendations"] = recs

    relations = []
    for edge in media.get("relations", {}).get("edges", []):
        rel_type = edge.get("relationType", "")
        node = edge.get("node", {})
        if node and node["format"] in ("TV", "OVA", "ONA", "MOVIE", "SPECIAL"):
            relations.append({
                "id": node["id"],
                "title": node["title"].get("english") or node["title"].get("romaji") or "?",
                "poster": node["coverImage"]["large"],
                "format": node["format"],
                "episodes": node.get("episodes"),
                "year": node.get("seasonYear"),
                "relationType": rel_type
            })
    media["relations"] = relations

    return media

@app.get("/stream/{anilist_id}/{episode}")
async def stream_endpoint(
    anilist_id: str,
    episode: int,
    req: Request
):
    clean = anilist_id.replace("anilist:", "")
    try:
        aid = int(clean)
    except ValueError:
        logger.warning(f"Invalid AniList ID: {anilist_id}")
        return {"streams": []}

    base = str(req.base_url).rstrip("/")

    async def fetch_stream_for_lang(lang: str) -> Optional[dict]:
        data = await fetch_megavid(aid, episode, lang)
        if not data:
            return None

        source = data.get("source")
        if not source:
            return None

        proxy_url = f"{base}/proxy/m3u8?url={quote(source)}&referer={quote(Config.MEGAVID_REFERER)}"
        label = "English Dub" if lang == "dub" else "Japanese Sub"
        stream_obj = {"name": label, "url": proxy_url}

        tracks = data.get("tracks") or []
        if tracks:
            stream_obj["subtitles"] = [
                {
                    "url": f"{base}/proxy/sub?url={quote(t['file'])}",
                    "lang": t.get("label", "eng")
                }
                for t in tracks if t.get("file")
            ]

        hints = {}
        intro = data.get("intro")
        outro = data.get("outro")

        if intro and isinstance(intro, dict) and "start" in intro and "end" in intro:
            hints["skipIntroTimestamps"] = [intro["start"], intro["end"]]
        if outro and isinstance(outro, dict) and "start" in outro and "end" in outro:
            hints["skipOutroTimestamps"] = [outro["start"], outro["end"]]

        if hints:
            stream_obj["behaviorHints"] = hints

        return stream_obj

    # Fetch sub and dub in parallel directly using AniList ID
    sub_task = asyncio.create_task(fetch_stream_for_lang("sub"))
    dub_task = asyncio.create_task(fetch_stream_for_lang("dub"))
    sub_stream, dub_stream = await asyncio.gather(sub_task, dub_task)

    streams = [s for s in (sub_stream, dub_stream) if s is not None]
    return {"streams": streams}

# Proxy routes
@app.get("/proxy/m3u8")
async def proxy_m3u8(url: str, referer: str, req: Request):
    target = unquote(url)
    ref = unquote(referer)
    base = str(req.base_url).rstrip("/")
    content = await fetch_upstream_m3u8(target, ref)
    lines = content.splitlines()
    rewritten = []
    is_variant = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if "#EXT-X-STREAM-INF" in stripped or "#EXT-I-FRAME-STREAM-INF" in stripped:
                is_variant = True
            def rewrite_uri(m):
                tag, raw = m.group(1), m.group(2)
                full = urljoin(target, raw)
                endpoint = "proxy/m3u8" if "EXT-X-MEDIA" in stripped else "proxy/segment"
                return f'{tag}="{base}/{endpoint}?url={quote(full)}&referer={quote(ref)}"'
            line = re.sub(r'(URI)=["\']([^"\']+)["\']', rewrite_uri, stripped)
            rewritten.append(line)
        else:
            full = urljoin(target, stripped)
            ep = "proxy/m3u8" if (is_variant or ".m3u8" in full.lower()) else "proxy/segment"
            rewritten.append(f"{base}/{ep}?url={quote(full)}&referer={quote(ref)}")
            is_variant = False
    return Response("\n".join(rewritten), media_type="application/vnd.apple.mpegurl",
                    headers={"Access-Control-Allow-Origin": "*"})

@app.get("/proxy/segment")
async def segment(url: str, referer: str, req: Request):
    return await proxy_segment(unquote(url), unquote(referer), req)

@app.get("/proxy/sub")
async def sub_proxy(url: str):
    return await proxy_subtitle(unquote(url))

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(Config.TEMPLATES_DIR / "index.html")

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str):
    return FileResponse(Config.TEMPLATES_DIR / "index.html")

if __name__ == "__main__":
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")

    if ssl_keyfile and ssl_certfile:
        logger.info("Starting with HTTPS")
        uvicorn.run(
            app,
            host=Config.HOST,
            port=Config.PORT,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
        )
    else:
        logger.info("Starting with HTTP (no SSL configured)")
        uvicorn.run(app, host=Config.HOST, port=Config.PORT)
