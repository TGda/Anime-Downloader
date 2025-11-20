import requests
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import urljoin
import aiohttp
import aiofiles
import asyncio

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def guess_season_from_url_or_title(url, node=None):
    m = re.search(r'Season[^\d]?(\d+)', url, re.I)
    if not m and node:
        m = re.search(r'Season[^\d]?(\d+)', node.text if hasattr(node, "text") else node, re.I)
    return m.group(1) if m else "1"

def find_mp4s_recursive(url, serie_root, season_hint=None):
    try:
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"Error accediendo {url}: {e}")
        return dict()
    mp4_links = [
        a for a in soup.find_all("a", href=re.compile(r"\.mp4$", re.I))
        if a and a.has_attr("href")
    ]
    if mp4_links:
        season = season_hint or guess_season_from_url_or_title(url, soup)
        episode_list = []
        for ep in mp4_links:
            ep_url = urljoin(url, ep['href'])
            ep_file = clean_filename(ep_url.split('/')[-1])
            ep_name = ep_file
            dest = os.path.join(serie_root, f"Season {season}", ep_file)
            episode_list.append({
                "name": ep_name,
                "link": ep_url,
                "downloaded": os.path.exists(dest)
            })
        return {season: episode_list}
    folder_links = [
        a for a in soup.find_all("a", href=True)
        if not a['href'].endswith(".mp4") and not a['href'].startswith("mailto:")
        and ("season" in a.text.lower() or "episode" in a.text.lower() or bool(re.match(r'[Ss]eason|[Ee]pisode|\d+', a.text)))
    ]
    result = {}
    for folder in folder_links:
        folder_url = urljoin(url, folder['href'])
        this_season = guess_season_from_url_or_title(folder_url, folder)
        data = find_mp4s_recursive(folder_url, serie_root, this_season)
        for season, eps in data.items():
            if season not in result:
                result[season] = []
            result[season].extend(eps)
    return result

def scrape_anime_data(url, download_root="/downloads"):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"Error accediendo {url}: {e}")
        return {"title":"Error", "img_url":None, "seasons":{}}
    title_div = soup.find("div", class_="Singamda")
    title = title_div.text.strip() if title_div else (soup.title.text.strip() if soup.title else "Anime Series")
    img_el = soup.find("img", {"src": re.compile(r".*\.(jpg|jpeg|png|webp)$", re.I)})
    img_url = urljoin(url, img_el["src"]) if img_el else None
    serie_root = os.path.join(download_root, clean_filename(title))
    seasons = find_mp4s_recursive(url, serie_root)
    return {
        "title": title,
        "img_url": img_url,
        "seasons": seasons
    }

# download_selected_episodes (sin cambios previos, ya gestiona skip si existe en disco)

async def download_file(url, dest):
    chunk_size = 1024 * 1024
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                async with aiofiles.open(dest, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(chunk_size):
                        await f.write(chunk)
        return dest, None
    except Exception as e:
        return dest, str(e)

def download_selected_episodes(main_url, folder, episodes, parallel=2):
    try:
        response = requests.get(main_url)
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"Error accediendo {main_url}: {e}")
    title_div = soup.find("div", class_="Singamda")
    title = title_div.text.strip() if title_div else (soup.title.text.strip() if soup.title else "Anime Series")
    serie_root = os.path.join(folder, clean_filename(title))
    if not os.path.exists(serie_root):
        os.makedirs(serie_root)
    to_download, skipped = [], []
    for ep_url in episodes:
        ep_file = clean_filename(ep_url.split('/')[-1])
        m = re.search(r'Season[^\d]?(\d+)', ep_url, re.I)
        season_folder = f"Season {m.group(1)}" if m else ""
        dest = os.path.join(serie_root, season_folder, ep_file)
        if os.path.exists(dest):
            skipped.append(dest)
        else:
            to_download.append((ep_url, dest))
    async def runner():
        sem = asyncio.Semaphore(parallel)
        async def sem_download(urldest):
            async with sem:
                return await download_file(*urldest)
        return await asyncio.gather(*(sem_download(pair) for pair in to_download))
    results = asyncio.run(runner())
    result_ok = [d for d, err in results if err is None]
    result_fail = [(d, err) for d, err in results if err is not None]
    return {
        "downloaded": result_ok,
        "skipped": skipped,
        "errors": result_fail
    }
