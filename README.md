# NebulaStream

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)
![HLS.js](https://img.shields.io/badge/HLS.js-latest-orange)
![License](https://img.shields.io/badge/License-GPLv3-blue.svg)

> **A self-hosted anime streaming web UI with AniList metadata, Megavid stream resolution, and a neon-infused player — all running inside Docker.**

NebulaStream provides a sleek, local web interface for browsing and streaming anime. It pulls metadata from AniList, resolves streams from Megavid, and delivers a fully featured HLS player with watch history and resume support.

---

## ✨ Features

- 🏠 Neon futuristic UI with hero carousel
- 🔍 AniList-powered search, catalog, and genres
- 🎬 Stream anime via Megavid (sub & dub)
- 🖥️ HLS player with audio track selection
- ⏱️ Watch history & resume playback
- 🧭 History-based SPA routing
- 🐳 Single-container Docker deployment

---

## 📸 Screenshots

| Home | Player | Details |
| :--- | :--- | :--- |
| ![Home](https://github.com/VirtueCore/NebulaStream/blob/177dcc0141fd1b3edd51e3b39a6a33a5e9099152/2026-08-16_15-11.png) | ![Player](https://github.com/VirtueCore/NebulaStream/blob/177dcc0141fd1b3edd51e3b39a6a33a5e9099152/2026-08-16_15-20.png) | ![Details](https://github.com/VirtueCore/NebulaStream/blob/177dcc0141fd1b3edd51e3b39a6a33a5e9099152/2026-08-16_15-05.png) |

> Create a `screenshots/` folder in the repository root and place your images there.

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone [https://github.com/YOUR_USERNAME/NebulaStream.git](https://github.com/YOUR_USERNAME/NebulaStream.git)
cd NebulaStream
```

### 2. (Optional) Create an IPv4 BuildKit builder

On hosts without working IPv6 connectivity, BuildKit may resolve Docker Hub to an IPv6 address and fail with `network is unreachable`. Running BuildKit inside a container keeps registry pulls on IPv4.

```bash
docker buildx create --name ipv4 --driver docker-container --use
```

> If you already have a working IPv6 connection, you can skip this step.

### 3. Build and start the container

```bash
docker compose up -d --build
```

The app will be available at: **http://localhost:7001**

### 4. View logs

```bash
docker compose logs -f
```

### 5. Stop the container

```bash
docker compose down
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Bind address (inside container) |
| `PORT` | `7001` | Port to listen on (inside container) |

> **Host port mapping** can be changed by creating a `.env` file with `PORT=8080` (or any other port). See `.env.example`.

---

## 🧭 Usage

Simply navigate to `http://YOUR-IP-ADDRESS:7001` in your browser.  
The UI is fully self-contained – no additional client setup is required.

### Available API Endpoints

| Endpoint | Description |
| :--- | :--- |
| `/api/home` | Home page data (hero + rows) |
| `/api/catalog` | Browse with filters/pagination |
| `/api/search` | Search anime |
| `/api/genres` | List of supported genres |
| `/api/anime/{id}` | Detailed anime information |
| `/api/episodes/{id}` | Total episode count |
| `/stream/{id}/{ep}` | Stream sources (sub/dub) |
| `/proxy/m3u8` | HLS playlist proxy |
| `/proxy/segment` | Video segment proxy |
| `/proxy/sub` | Subtitle proxy |

---

## ❓ FAQ

### Does NebulaStream host any anime content?
No. It only fetches metadata from AniList and resolves publicly available stream URLs from Megavid. Users are responsible for their own usage and compliance.

### Does this work on Linux?
Yes. Linux is the recommended deployment platform.

### Does this work on Windows/macOS?
Yes. Docker Desktop is fully supported.

### Can I run it without Docker?
Yes. See [Manual Run](#️-manual-run-without-docker) below.

### Why do I get a `network is unreachable` error during `docker compose build`?
This is often caused by BuildKit attempting to use IPv6 when the host has no IPv6 connectivity. Use the IPv4 buildx builder as shown in Quick Start.

### How do I update NebulaStream?
```bash
docker compose down
git pull
docker compose up -d --build
```

---

## 🐳 Docker Commands

| Command | Description |
| :--- | :--- |
| `docker compose build` | Build the image |
| `docker compose up -d` | Start in detached mode |
| `docker compose logs -f` | Follow logs |
| `docker compose restart` | Restart the service |
| `docker compose down` | Stop and remove the container |
| `docker compose pull` | Pull latest base images |

---

## 🛠️ Manual Run (without Docker)

```bash
cd anime-resolver
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python anime_resolver.py
```

---

## 📁 Project Structure

```text
NebulaStream/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── anime-resolver/
    ├── anime_resolver.py
    ├── Dockerfile
    ├── requirements.txt
    ├── static/
    │   ├── css/
    │   │   └── main.css
    │   └── js/
    │       ├── api.js
    │       ├── app.js
    │       ├── player.js
    │       └── storage.js
    └── templates/
        └── index.html
```

> **Note:** The `index.html` is a self-contained single page application (all CSS/JS inline).  
> The files in `static/` are placeholders for a future refactor or optional external assets.

---

## 🏗️ Architecture

```text
         Browser
            │
            ▼
   +-------------------+
   |   NebulaStream    |
   |   (FastAPI:7001)  |
   +-------------------+
      │           │
      │           ▼
      │        AniList API
      │        (Metadata)
      │
      ▼
   Megavid API
   (Stream URLs)
      │
      ▼
   HLS Proxy
   (Playlist & Segments)
```

---

## 🧠 How It Works

1. Frontend requests data from NebulaStream’s FastAPI backend.
2. Backend queries AniList for anime metadata.
3. When a user selects an episode, backend retrieves stream source from Megavid.
4. The HLS playlist is rewritten to proxy through NebulaStream.
5. Video segments are streamed through the backend to the player.
6. Watch history is stored locally in the browser’s `localStorage`.

---

## ⚡ Performance Features

- Async FastAPI with connection pooling
- In-memory caching of catalog and stream metadata
- HLS segment streaming with chunked transfer
- Lazy loading of images
- Efficient HLS.js player with audio track selection
- Single-page routing for smooth navigation

---

## 🗺️ Roadmap

- [ ] Multiple stream providers
- [ ] User authentication
- [ ] Server-side watch history
- [ ] Continue Watching row
- [ ] Docker image publishing

---

## ⚠️ Disclaimer

This project is intended for **self-hosting, development, and educational purposes**. Users are responsible for ensuring their use complies with applicable laws, regulations, and the terms of any content providers or services they access.

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.  
See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Pull requests, bug reports, and feature requests are welcome.  
If you encounter an issue:

1. Open an issue.
2. Include logs.
3. Describe how to reproduce it.
4. Include your Docker version and operating system.
