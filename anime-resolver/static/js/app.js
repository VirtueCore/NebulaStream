document.addEventListener('DOMContentLoaded', () => {
    if (window.initialData) {
        renderHome(window.initialData);
    }
});

function renderHome(homeData) {
    if (!homeData) return;

    // 1. Render Hero Section
    renderHero(homeData.hero);

    // 2. Render Section Rows
    const rowOrder = ['trending', 'popular_season', 'recent', 'coming_soon'];
    const rowTitles = {
        trending: 'Trending Now',
        popular_season: 'Popular This Season',
        recent: 'Recently Added',
        coming_soon: 'Coming Soon'
    };

    const rowsContainer = document.getElementById('home-rows');
    if (!rowsContainer) return;

    rowsContainer.innerHTML = '';

    rowOrder.forEach(key => {
        const list = homeData[key];
        if (list && list.length > 0) {
            const section = document.createElement('section');
            section.className = 'row-section';

            section.innerHTML = `
                <div class="row-header">
                    <h2>${rowTitles[key]}</h2>
                </div>
                <div class="row-wrapper">
                    <button class="row-nav-btn prev-btn" aria-label="Scroll left">&#10094;</button>
                    <div class="scroll-row" id="row-${key}"></div>
                    <button class="row-nav-btn next-btn" aria-label="Scroll right">&#10095;</button>
                </div>
            `;

            rowsContainer.appendChild(section);

            const rowElement = section.querySelector(`#row-${key}`);
            const prevBtn = section.querySelector('.prev-btn');
            const nextBtn = section.querySelector('.next-btn');

            // Populate Row Cards
            list.forEach(item => {
                rowElement.appendChild(createCard(item));
            });

            // Smooth Scroll Step Distance
            const scrollDistance = () => rowElement.clientWidth * 0.75;

            prevBtn.addEventListener('click', (e) => {
                e.preventDefault();
                rowElement.scrollBy({ left: -scrollDistance(), behavior: 'smooth' });
            });

            nextBtn.addEventListener('click', (e) => {
                e.preventDefault();
                rowElement.scrollBy({ left: scrollDistance(), behavior: 'smooth' });
            });

            // Monitor Scroll Position & Toggle Button Visibility
            const updateNavVisibility = () => {
                const scrollLeft = rowElement.scrollLeft;
                const maxScrollLeft = rowElement.scrollWidth - rowElement.clientWidth;

                // Threshold tolerance (5px) for browser zoom/sub-pixel rounding
                if (scrollLeft <= 5) {
                    prevBtn.classList.add('is-hidden');
                } else {
                    prevBtn.classList.remove('is-hidden');
                }

                if (scrollLeft >= maxScrollLeft - 5) {
                    nextBtn.classList.add('is-hidden');
                } else {
                    nextBtn.classList.remove('is-hidden');
                }
            };

            // Event Listeners for Dynamic Visibility Updates
            rowElement.addEventListener('scroll', updateNavVisibility, { passive: true });
            window.addEventListener('resize', updateNavVisibility, { passive: true });

            // Initial visibility state check on load
            requestAnimationFrame(updateNavVisibility);
        }
    });
}

function renderHero(hero) {
    if (!hero) return;

    const heroBg = document.getElementById('hero-bg');
    const heroTitle = document.getElementById('hero-title');
    const heroMeta = document.getElementById('hero-meta');
    const heroDesc = document.getElementById('hero-desc');
    const heroEl = document.getElementById('hero');

    if (heroBg) heroBg.style.backgroundImage = `url(${hero.banner || hero.poster})`;
    if (heroTitle) heroTitle.innerText = hero.title || '';
    if (heroMeta) {
        heroMeta.innerHTML = `
            ${hero.score ? `<span class="rating">★ ${(hero.score / 10).toFixed(1)}</span>` : ''}
            ${hero.format ? `<span>${hero.format}</span>` : ''}
            ${hero.episodes ? `<span>${hero.episodes} Episodes</span>` : ''}
            ${hero.year ? `<span>${hero.year}</span>` : ''}
        `;
    }
    if (heroDesc) {
        const plainDesc = hero.description ? hero.description.replace(/<[^>]*>/g, '') : '';
        heroDesc.innerText = plainDesc;
    }
    if (heroEl) heroEl.dataset.anilistId = hero.id || '';

    // Bind Play Button Handler
    const playBtn = document.getElementById('hero-play');
    if (playBtn) {
        const cleanPlayBtn = playBtn.cloneNode(true);
        playBtn.parentNode.replaceChild(cleanPlayBtn, playBtn);

        cleanPlayBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const currentHero = document.getElementById('hero');
            const id = currentHero ? currentHero.dataset.anilistId : null;
            if (id && typeof openPlayer === 'function') {
                openPlayer(id, heroTitle ? heroTitle.innerText : '');
            }
        });
    }
}

function createCard(item) {
    const card = document.createElement('div');
    card.className = 'card';
    card.dataset.id = item.id;

    card.innerHTML = `
        <div class="card-img-wrapper">
            <img src="${item.poster || item.banner || ''}" alt="${item.title || 'Poster'}" loading="lazy" />
        </div>
        <div class="card-title">${item.title || 'Untitled'}</div>
    `;

    card.addEventListener('click', () => {
        if (typeof openPlayer === 'function') {
            openPlayer(item.id, item.title);
        }
    });

    return card;
}
