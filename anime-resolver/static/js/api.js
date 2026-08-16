const API = {
    async fetchHome() {
        const res = await fetch('/api/home');
        return res.json();
    },
    async search(query) {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        return res.json();
    },
    async getEpisodes(anilistId) {
        const res = await fetch(`/api/episodes/${anilistId}`);
        return res.json();
    },
    async getStream(anilistId, episode) {
        const res = await fetch(`/stream/${anilistId}/${episode}`);
        return res.json();
    },
    async getAnimeDetails(anilistId) {
        const res = await fetch(`/api/anime/${anilistId}`);
        return res.json();
    }
};
