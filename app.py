from flask import Flask, render_template, request, jsonify
from scraping.scraper import scrape_anime_data, download_selected_episodes_with_status
import os
import threading

app = Flask(__name__)

# Variable global para tracking de descargas en progreso
download_status = {
    "active": False,
    "queue": [],
    "downloading": [],
    "completed": [],
    "errors": []
}
download_lock = threading.Lock()

DOWNLOAD_ROOT_DEFAULT = os.getenv("DOWNLOAD_FOLDER", "/downloads")
PARALLEL_DEFAULT = int(os.getenv("PARALLEL_DOWNLOADS", 2))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/", methods=["POST"])
def process():
    try:
        url = request.form.get("url")
        dest = request.form.get("dest", DOWNLOAD_ROOT_DEFAULT)
        parallel = int(request.form.get("parallel", PARALLEL_DEFAULT))
        
        serie_data = scrape_anime_data(url, dest)
        
        return render_template("results.html", 
                             serie=serie_data, 
                             url=url, 
                             folder=dest,
                             parallel=parallel)
    except Exception as e:
        return f"Error processing: {str(e)}", 500

@app.route("/download", methods=["POST"])
def download():
    try:
        data = request.json
        url = data.get("url")
        folder = data.get("folder")
        episodes = data.get("episodes", [])
        parallel = data.get("parallel", PARALLEL_DEFAULT)
        
        # Inicializa el status
        with download_lock:
            download_status["active"] = True
            download_status["queue"] = [ep.split('/')[-1] for ep in episodes]
            download_status["downloading"] = []
            download_status["completed"] = []
            download_status["errors"] = []
        
        # Ejecuta descarga en thread separado
        def download_thread():
            try:
                result = download_selected_episodes_with_status(
                    url, folder, episodes, parallel, 
                    download_status, download_lock
                )
                with download_lock:
                    download_status["active"] = False
                    download_status["completed"] = [f.split('/')[-1] for f in result.get("downloaded", [])]
                    download_status["errors"] = result.get("errors", [])
            except Exception as e:
                print(f"Error in download thread: {str(e)}")
                with download_lock:
                    download_status["active"] = False
                    download_status["errors"].append(("general", str(e)))
        
        threading.Thread(target=download_thread, daemon=True).start()
        
        return jsonify({"status": "started", "episodes": len(episodes)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download/status", methods=["GET"])
def download_status_endpoint():
    """Endpoint para polling del estado de descargas"""
    with download_lock:
        return jsonify(download_status.copy())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
