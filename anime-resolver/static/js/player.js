let hls = null;
let currentLang = 'sub';
let currentAnimeId = null;

function openPlayer(anilistId, title) {
    currentAnimeId = anilistId;
    document.getElementById('player-title').innerText = title;
    document.getElementById('player-overlay').classList.add('active');
    API.getEpisodes(anilistId).then(data => {
        const total = data.total || 0;
        const container = document.getElementById('episode-list');
        container.innerHTML = '';
        for (let i = 1; i <= total; i++) {
            const btn = document.createElement('button');
            btn.className = 'ep-btn';
            btn.innerText = i;
            btn.onclick = () => loadStream(anilistId, i);
            container.appendChild(btn);
        }
        if (total > 0) loadStream(anilistId, 1);
    });
    // Language buttons
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.lang === currentLang);
        btn.onclick = () => {
            currentLang = btn.dataset.lang;
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const activeEp = document.querySelector('.ep-btn.active');
            if (activeEp) loadStream(anilistId, parseInt(activeEp.innerText));
        };
    });
}

function loadStream(anilistId, episode) {
    API.getStream(anilistId, episode).then(data => {
        const stream = data.streams?.find(s => s.name.toLowerCase().includes(currentLang === 'sub' ? 'japanese' : 'english'));
        if (!stream) { alert('No stream'); return; }
        const video = document.getElementById('video-player');
        if (hls) hls.destroy();
        if (Hls.isSupported()) {
            hls = new Hls();
            hls.loadSource(stream.url);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, () => {
                const saved = Storage.getProgress(anilistId);
                if (saved && saved.episode == episode) video.currentTime = saved.currentTime;
                video.play().catch(()=>{});
            });
            video.addEventListener('timeupdate', () => {
                if (video.duration) {
                    Storage.saveProgress(anilistId, episode, video.currentTime, video.duration);
                }
            });
        } else {
            video.src = stream.url;
            video.play();
        }
        // Skip buttons
        if (stream.behaviorHints) {
            document.getElementById('skip-intro').style.display = stream.behaviorHints.skipIntroTimestamps ? 'inline' : 'none';
            document.getElementById('skip-outro').style.display = stream.behaviorHints.skipOutroTimestamps ? 'inline' : 'none';
            document.getElementById('skip-intro').onclick = () => video.currentTime = stream.behaviorHints.skipIntroTimestamps[1];
            document.getElementById('skip-outro').onclick = () => video.currentTime = stream.behaviorHints.skipOutroTimestamps[1];
        }
    });
}

document.getElementById('close-player').addEventListener('click', () => {
    document.getElementById('player-overlay').classList.remove('active');
    if (hls) { hls.destroy(); hls = null; }
});
