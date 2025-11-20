import requests
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import urljoin

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def find_mp4s_recursive(url, download_root, season_hint=None):
    """
    Navega recursivamente por folders hasta encontrar archivos mp4.
    Si detecta nivel de temporada en la URL o por texto, lo utiliza.
    Devuelve {season: [episodios...]}.
    """
    try:
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"Error accediendo {url}: {e}")
        return dict()
    
    # Buscar archivos mp4 en la página
    mp4_links = [
        a for a in soup.find_all("a", href=re.compile(r"\.mp4$", re.I))
        if a and a.has_attr("href")
    ]
    if mp4_links:
        # Si tiene mp4 aquí, infiere temporada
        season = season_hint or guess_season_from_url_or_title(url, soup)
        episode_list = []
        for ep in mp4_links:
            ep_url = urljoin(url, ep['href'])
            ep_file = clean_filename(ep_url.split('/')[-1])
            ep_name = ep.text.strip() or ep_file
            # Asumiendo que los mp4 están en /downloads/Season X
            dest = os.path.join(download_root, f"Season {season}", ep_file)
            episode_list.append({
                "name": ep_name,
                "link": ep_url,
                "downloaded": os.path.exists(dest)
            })
        return {season: episode_list}

    # Si no hay mp4, buscar subfolders y entrar recursivo
    folder_links = [
        a for a in soup.find_all("a", href=True)
        if not a['href'].endswith(".mp4") and not a['href'].startswith("mailto:")
        and ("season" in a.text.lower() or "episode" in a.text.lower() or bool(re.match(r'[Ss]eason|[Ee]pisode|\d+', a.text)))
        # Quitar links vacíos, up, etc.
    ]
    result = {}
    for folder in folder_links:
        folder_url = urljoin(url, folder['href'])
        this_season = guess_season_from_url_or_title(folder_url, folder)
        data = find_mp4s_recursive(folder_url, download_root, this_season)
        for season, eps in data.items():
            if season not in result:
                result[season] = []
            result[season].extend(eps)
    return result

def guess_season_from_url_or_title(url, node=None):
    # Intenta extraer el season de la url o del texto visible
    m = re.search(r'Season[^\d]?(\d+)', url, re.I)
    if not m and node:
        m = re.search(r'Season[^\d]?(\d+)', node.text if hasattr(node, "text") else node, re.I)
    return m.group(1) if m else "1"

def scrape_anime_data(url, download_root="/downloads"):
    """
    Dado el link de serie, navega folders hasta llegar a los mp4 y devuelve estructura:
    { "title": ..., "img_url": ..., "seasons": {sx:[episodios]} }
    """
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"Error accediendo {url}: {e}")
        return {"title":"Error", "img_url":None, "seasons":{}}

    # Título
    title = (soup.title.text.strip() if soup.title else "Anime Series")

    # Buscar imagen relacionada (puedes afinar el selector)
    img_el = soup.find("img", {"src": re.compile(r".*\.(jpg|jpeg|png|webp)$", re.I)})
    img_url = urljoin(url, img_el["src"]) if img_el else None

    # Buscar capítulos organizados por season, usando recursividad
    seasons = find_mp4s_recursive(url, download_root)

    return {
        "title": title,
        "img_url": img_url,
        "seasons": seasons
    }

# Descarga asíncrona igual que antes:
import aiohttp
import aiofiles
import asyncio

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
    if not os.path.exists(folder):
        os.makedirs(folder)
    to_download, skipped = [], []
    for ep_url in episodes:
        ep_file = clean_filename(ep_url.split('/')[-1])
        # intenta deducir season en la ruta
        m = re.search(r'Season[^\d]?(\d+)', ep_url, re.I)
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
