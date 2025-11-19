import requests
from bs4 import BeautifulSoup
import os
import aiohttp
import asyncio

def scrape_anime_data(url):
    # Scrapear datos básicos, return dict como:
    # {"title":"Nombre Serie", "img_url":"...", "seasons":{3:[{"name":"Episode...","link":"...","downloaded":True/False}]}}
    # Aquí simulado; deberás adaptar a los datos reales de la web objetivo

    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.string if soup.title else "Anime Detected"
    img_url = None  # puedes buscar <img> principal
    seasons = {}

    # Simulación de scraping DE EPISODIOS TEMPORADA 3
    season_num = "3"
    downloaded_folder = "/downloads"  # cambia por dinámico
    eps_list = [
        {"name":"Episode 26", "link":".../26.mp4"},
        {"name":"Episode 27", "link":".../27.mp4"},
        {"name":"Episode 28 Counterattack Signal", "link":".../28.mp4"},
        {"name":"Episode 29 Monster King", "link":".../29.mp4"},
        {"name":"Episode 30 Motley Heroes", "link":".../30.mp4"},
    ]
    # Marca los ya bajados
    for ep in eps_list:
        ep_filename = ep['link'].split('/')[-1]
        ep['downloaded'] = os.path.exists(os.path.join(downloaded_folder, ep_filename))
    seasons[season_num] = eps_list

    return {"title":title, "img_url":img_url, "seasons":seasons}

async def download_file(url, dest):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                async with aiofiles.open(dest, 'wb') as f:
                    await f.write(await resp.read())

def download_selected_episodes(main_url, folder, episodes, parallel):
    os.makedirs(folder, exist_ok=True)
    to_download = []
    for ep_url in episodes:
        ep_filename = ep_url.split('/')[-1]
        dest_file = os.path.join(folder, ep_filename)
        if not os.path.exists(dest_file):
            to_download.append((ep_url, dest_file))
    # Descargas paralelas con asyncio
    async def runner():
        sem = asyncio.Semaphore(parallel)
        async def sem_download(urldest):
            async with sem:
                await download_file(*urldest)
        await asyncio.gather(*(sem_download(pair) for pair in to_download))
    asyncio.run(runner())
    return {"downloaded": [f for _, f in to_download], "skipped": [f for ep_url, f in episodes if os.path.exists(f)]}
