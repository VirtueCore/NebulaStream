const Storage = {
    getHistory() {
        return JSON.parse(localStorage.getItem('watchHistory') || '{}');
    },
    saveProgress(animeId, episode, currentTime, duration) {
        const history = this.getHistory();
        history[animeId] = { episode, currentTime, duration, updatedAt: Date.now() };
        localStorage.setItem('watchHistory', JSON.stringify(history));
    },
    getProgress(animeId) {
        const history = this.getHistory();
        return history[animeId] || null;
    },
    getContinueWatching() {
        const history = this.getHistory();
        return Object.entries(history)
            .filter(([_, data]) => data.currentTime > 60 && data.currentTime < data.duration * 0.9)
            .map(([animeId, data]) => ({ animeId, ...data }));
    }
};
