import requests
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import urljoin

def clean_filename(name):
    """
    Limpia un string para usar como nombre de archivo.
    """
    return re.sub(r'[\\/*?:"<>|]', "", name)

def scrape_anime_data(url, download_root="/downloads"):
    """
    Scrapear la información de un anime: título, imagen principal,
    lista de temporadas y episodios, y su estado (bajado/no bajado).
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Título
    title = soup.title.text.strip() if soup.title else "Anime Series"

    # Buscar imagen principal (puede requerir ajuste según la página)
    img_el = soup.find("img", {"src": re.compile(r".*\.(jpg|jpeg|png|webp)$", re.I)})
    img_url = urljoin(url, img_el["src"]) if img_el else None

    # Buscar links a temporadas y capítulos
    season_dict = {}
    # Caminos que suelen tener la estructura: /Season-XX/ o /Episode-XX/
    season_links = soup.find_all('a', href=re.compile(r'Season-\d+', re.I))
    if not season_links:  # Puede que ya estés en la página de una temporada
        season_links = [soup]

    for season_el in season_links:
        # Puedes estar ya posicionado en la season o venir de la lista de seasons
        if isinstance(season_el, BeautifulSoup):  # primer ciclo, página ya es de la season
            season_url = url
            season_num = re.findall(r'Season-(\d+)', url)
            season_num = season_num[0] if season_num else "1"
            season_soup = season_el
        else:
            season_url = urljoin(url, season_el["href"])
            season_num = re.findall(r'Season-(\d+)', season_url)
            season_num = season_num[0] if season_num else "1"
            season_resp = requests.get(season_url)
            season_soup = BeautifulSoup(season_resp.text, "html.parser")

        episode_list = []
        episode_links = season_soup.find_all('a', href=re.compile(r'\.mp4$', re.I))
        for ep in episode_links:
            ep_name = ep.text.strip() or ep['href'].split('/')[-1]
            ep_url = urljoin(season_url, ep['href'])
            ep_file = clean_filename(ep_url.split('/')[-1])
            dest = os.path.join(download_root, f"Season {season_num}", ep_file)
            episode_list.append({
                "name": ep_name,
                "link": ep_url,
                "downloaded": os.path.exists(dest)
            })

        if episode_list:
            season_dict[season_num] = episode_list

    return {
        "title": title,
        "img_url": img_url,
        "seasons": season_dict
    }

# --- Descarga asíncrona de episodios ---
import aiohttp
import aiofiles
import asyncio

async def download_file(url, dest):
    chunk_size = 1024 * 1024  # 1MB
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
    if not os.path.exists(folder):
        os.makedirs(folder)
    to_download = []
    skipped = []
    for ep_url in episodes:
        ep_file = clean_filename(ep_url.split('/')[-1])
        # Buscar si pertenece a una season; si el frontend lo incluye en la data, puedes mejorar esto
        m = re.search(r'Season-(\d+)', ep_url)
        season_folder = f"Season {m.group(1)}" if m else ""
        dest = os.path.join(folder, season_folder, ep_file)
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
