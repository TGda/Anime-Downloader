from flask import Flask, request, render_template, jsonify
import os
from scraping.scraper import scrape_anime_data, download_selected_episodes

app = Flask(__name__)

DOWNLOAD_ROOT_DEFAULT = "/downloads"
PARALLEL_DEFAULT = 2

# Home page for URL input
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form["url"]
        folder = request.form.get("dest", DOWNLOAD_ROOT_DEFAULT)
        parallel = int(request.form.get("parallel", PARALLEL_DEFAULT))

        # Scrape serie info (title, image, episodes/seasons)
        serie_data = scrape_anime_data(url)

        return render_template(
            "results.html",
            url=url,
            folder=folder,
            parallel=parallel,
            serie=serie_data
        )
    return render_template("index.html")

# Endpoint to process selected downloads
@app.route("/download", methods=["POST"])
def download():
    data = request.json
    url = data["url"]
    folder = data.get("folder", DOWNLOAD_ROOT_DEFAULT)
    parallel = int(data.get("parallel", PARALLEL_DEFAULT))
    selected_eps = data["episodes"]  # episode links or IDs

    # Pass list of selected episodes
    download_result = download_selected_episodes(url, folder, selected_eps, parallel)
    return jsonify(download_result)

if __name__ == "__main__":
    os.makedirs(DOWNLOAD_ROOT_DEFAULT, exist_ok=True)
    app.run(port=5000, host="0.0.0.0")
