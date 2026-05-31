// ezNews Malawi — vanilla JS, no dependencies
(function () {
  'use strict';

  const STRINGS = {
    en: {
      tagline: "News from Malawi, for everyone",
      search_placeholder: "Search news...",
      search_short: "Search",
      empty: "No articles match your search.",
      footer_about: "ezNews Malawi gives you the day's biggest stories in easy to understand writing. We always link to the original sources. We update three times a day, in the morning, at lunchtime and in the evening.",
      footer_disclaimer: "Articles are written by AI and should not be the only source you rely on.",
      sources_label: "Sources",
      read_more: "Read more",
      show_less: "Show less",
      reviewed_badge: "Chichewa checked by editor",
      needs_review_badge: "Auto-translated · awaiting review",
      topics: "Topics",
      recent_days: "Recent days",
      nav_today: "Today",
      nav_archive: "Archive",
      nav_about: "About",
      archive_title: "All articles",
      archive_intro: "Browse every story we have published.",
      about_title: "About ezNews Malawi",
      about_h_why: "Why we made this site",
      about_h_how: "How it works",
      about_h_lang: "Two languages",
      about_h_ct: "What about Chitumbuka?",
      about_h_sources: "Trust and sources",
      about_h_ai: "A note on AI",
      about_h_data: "Light on data",
      about_p_why_1: "ezNews Malawi was made for one simple reason: news from Malawi should be for everyone in Malawi.",
      about_p_why_2: "Most news in our country is published in English. But fluent English is shared by only a small part of the population. Many Malawians have learned some English at school, and they understand more when the words are simple. According to UNESCO and World Bank data, only about 22% of young people in Malawi finish lower secondary school, and primary completion is around one in three. This means many people stop their school journey early — through no fault of their own.",
      about_p_why_3: "Chichewa is a different story. Around 65% of the country can read or speak Chichewa, and it is the language of teaching in many primary schools. So many people who do not feel at home in long English articles can read clear Chichewa with confidence.",
      about_p_why_4: "We believe every Malawian has the right to know what is happening in their country — what their government is doing, what is changing in the economy, what affects their families. ezNews Malawi exists to help make that possible. We take the day's biggest news and write it in a way that is easier to read, in both simple English and Chichewa. We are not a replacement for the original news outlets. We send our readers back to them whenever they want the full story.",
      about_p1: "ezNews Malawi makes Malawi's news easier to read for everyone. We collect the day's biggest stories from trusted Malawi news websites and rewrite them in simple English and Chichewa.",
      about_p2: "Twice a day, our system checks news from many Malawi news outlets. When we see that the same story is being reported by more than one outlet, we know it is important. We pick the day's top stories and rewrite them so anyone can understand them.",
      about_p3: "Every story is written in two languages. The English uses very simple words (CEFR A1 level). The Chichewa is at a friendly everyday level (A2). You can switch between them with the EN/CC button at the top of the page.",
      about_p_ct: "We know that Chitumbuka is the first language for many people in the northern region of Malawi, and that other languages like Chiyao, Lomwe and Sena are also spoken across the country. We would like ezNews Malawi to include these languages too. For now, we have only started with Chichewa because that is what we can do well today, and we want every translation we publish to be of good quality. We are working on adding Chitumbuka next, and we will add it as soon as we are confident it will read naturally for our readers in the north. Thank you for your patience.",
      about_p4: "We always show the news websites we used at the bottom of every story. Click any source name to read the original article. We do not copy stories — we read several and write our own short summary.",
      about_p5: "Our English articles are written by an AI assistant. The Chichewa version is translated by Google Cloud Translation, then checked by a human editor. AI and translation systems can make mistakes, so please use ezNews Malawi together with other news sources, not as your only source. When you see a green ✓ \"Chichewa checked by editor\" badge, a Chichewa speaker has read and approved the article. When you see a yellow ⚠ \"Auto-translated, awaiting review\" badge, the article has been translated but may have small errors until a human checks it.",
      about_p6: "We made this website very small so it works on slow internet and uses very little data. Each page is under 50 KB.",
      all: "All",
      politics: "Politics",
      economy: "Economy",
      health: "Health",
      sport: "Sport",
      society: "Society",
      international: "International",
      ago_minutes: "min ago",
      ago_hours: "h ago",
      ago_yesterday: "Yesterday",
      ago_days: "days ago"
    },
    ny: {
      tagline: "Nkhani za Malawi, kwa aliyense",
      search_placeholder: "Pezani nkhani...",
      search_short: "Pezani",
      empty: "Palibe nkhani zogwirizana ndi zomwe mukufunafuna.",
      footer_about: "ezNews Malawi ikupatsirani nkhani zazikuluzikulu zatsikulo zolembedwa zosavuta kumva. Nthawi zonse timagwirizanitsa ndi magwero oyambirira. Timasintha katatu patsiku, m'mawa, masana ndi madzulo.",
      footer_disclaimer: "Zolemba zimalembedwa ndi AI ndipo siziyenera kukhala gwero lokhalo lomwe mumadalira.",
      sources_label: "Magwero",
      read_more: "Werengani zambiri",
      show_less: "Bisani",
      reviewed_badge: "Chichewa chayang'aniridwa ndi mkonzi",
      needs_review_badge: "Zomasulira zokha · zikudikirira kuunikanso",
      topics: "Mitu",
      recent_days: "Masiku apitawa",
      nav_today: "Lero",
      nav_archive: "Nkhokwe",
      nav_about: "Zaife",
      archive_title: "Nkhani zonse",
      archive_intro: "Werengani nkhani zonse zomwe tafalitsa.",
      about_title: "Za ezNews Malawi",
      about_h_why: "Chifukwa chiyani tinapanga tsamba ili",
      about_h_how: "Momwe zimagwirira ntchito",
      about_h_lang: "Zilankhulo ziwiri",
      about_h_ct: "Nanga Chitumbuka?",
      about_h_sources: "Kudalira ndi magwero",
      about_h_ai: "Chidziwitso pa AI",
      about_h_data: "Data pang'ono",
      about_p_why_1: "ezNews Malawi inapangidwa pa chifukwa chimodzi chophweka: nkhani zochokera ku Malawi zikhale za aliyense m'Malawi.",
      about_p_why_2: "Nkhani zambiri m'dziko lathu zimasindikizidwa mu Chingerezi. Koma Chingelezi cholankhula bwino chimagawidwa ndi anthu ochepa chabe. Amalawi ambiri aphunzira Chingelezi kusukulu, ndipo amamvetsetsa bwino mawu akakhala osavuta. Malinga ndi deta ya UNESCO ndi World Bank, pafupifupi 22 peresenti ya achinyamata m'Malawi muno amamaliza sukulu za sekondale zotsika, ndipo pulaimale ndi pafupifupi mmodzi mwa atatu alionse. Izi zikutanthauza kuti anthu ambiri amaimitsa ulendo wawo wa kusukulu msanga - popanda chifukwa chawo.",
      about_p_why_3: "Chichewa ndi nkhani ina. Pafupifupi 65% ya dziko lino amatha kuwerenga kapena kulankhula Chichewa, ndipo ndi chilankhulo chophunzitsira m'masukulu ambiri apulaimale. Choncho anthu ambiri amene samasuka m'nkhani zazitali zachingelezi amatha kuwerenga Chichewa momveka bwino molimba mtima.",
      about_p_why_4: "Tikukhulupirira kuti Mmalawi aliyense ali ndi ufulu wodziwa zomwe zikuchitika m'dziko lawo — zomwe boma lawo likuchita, zomwe zikusintha pa chuma, zomwe zimakhudza mabanja awo. ezNews Malawi ilipo kuti izi zitheke. Timatenga nkhani zazikulu kwambiri za tsikulo ndikuzilemba m'njira yosavuta kuwerenga, m'Chingerezi ndi Chichewa chosavuta. Sitingalowe m'malo mwazotulutsa nkhani zoyambilira. Timatumiza owerenga athu kwa iwo nthawi iliyonse akafuna nkhani yonse.",
      about_p1: "ezNews Malawi imapangitsa kuti nkhani za Malawi zikhale zosavuta kuwerenga kwa aliyense. Timasonkhanitsa nkhani zazikuluzikulu zatsiku lino kuchokera kumawebusayiti odalirika a Malawi ndi kuzilembanso m'Chingerezi ndi Chichewa chosavuta.",
      about_p2: "Katatu pa tsiku, makina athu amafufuza nkhani m'manyuzipepala ambiri a ku Malawi. Tikawona kuti nkhani imodzimodziyo ikufotokozedwa ndi malo angapo, timadziwa kuti ndi yofunika. Timasankha nkhani zapamwamba zatsikulo ndikuzilembanso kuti aliyense azimvetsetsa.",
      about_p3: "Nkhani iliyonse imalembedwa m'zinenero ziwiri. Chingerezi chimagwiritsa ntchito mawu osavuta (CEFR A1 level). Chichewa chili pamlingo waubwenzi watsiku ndi tsiku (A2). Mutha kusinthana pakati pawo ndi batani la EN/CC pamwamba pa tsamba.",
      about_p_ct: "Tikudziwa kuti Chitumbuka ndi chilankhulo choyambirira kwa anthu ambiri m'chigawo chakumpoto kwa dziko la Malawi, komanso zilankhulo zina monga Chiyao, Lomwe ndi Sena zimalankhulidwanso m'dziko lonselo. Tikufuna ezNews Malawi iphatikizanso zilankhulo izi. Pakadali pano, tangoyamba ndi Chichewa chifukwa ndizomwe titha kuchita bwino lero, ndipo tikufuna kuti zomasulira zonse zomwe timasindikiza zikhale zabwino. Tikukonzekera kuwonjezera Chitumbuka, ndipo tiwonjezera tikangokhulupirira kuti chiwerengedwe mwachibadwa kwa owerenga athu kumpoto. Zikomo chifukwa cha kudekha kwanu.",
      about_p4: "Nthawi zonse timawonetsa mawebusayiti omwe timagwiritsa ntchito m'munsi mwa nkhani iliyonse. Dinani dzina lililonse kuti muwerenge nkhani yoyambirira. Sitikopera nkhani - timawerenga zingapo ndikulemba chidule chathu chachifupi.",
      about_p5: "Zolemba zathu za Chingerezi zimalembedwa ndi wothandizira wa AI. Baibulo la Chichewa lamasuliridwa ndi Google Cloud Translation, kenako ndi kufufuzidwa ndi mkonzi waumunthu. AI ndi makina omasulira amatha kulakwitsa, choncho chonde gwiritsani ntchito ezNews Malawi pamodzi ndi zofalitsa zina, osati monga gwero lanu lokhalo. Mukawona chobiriwira ✓ \"Chichewa chayang'aniridwa ndi mkonzi\", wokamba Chichewa wawerenga ndikuvomereza nkhaniyo. Mukawona baji yachikasu ⚠ \"Zomasulira zokha, zomwe zikudikirira kuunikanso\", nkhaniyo yamasuliridwa koma ikhoza kukhala ndi zolakwika zazing'ono mpaka munthu wayiyang'ana.",
      about_p6: "Tidapanga tsamba ili kukhala laling'ono kwambiri kotero limagwira ntchito pa intaneti pang'onopang'ono ndipo limagwiritsa ntchito data yochepa kwambiri. Tsamba lililonse lili pansi pa 50 KB.",
      all: "Zonse",
      politics: "Ndale",
      economy: "Chuma",
      health: "Umoyo",
      sport: "Masewera",
      society: "Anthu",
      international: "Kunja",
      ago_minutes: "mphindi zapitazo",
      ago_hours: "maola apitawa",
      ago_yesterday: "Dzulo",
      ago_days: "masiku apitawa"
    }
  };

  const TAGS = ['all', 'politics', 'economy', 'health', 'sport', 'society', 'international'];

  let state = {
    lang: localStorage.getItem('eznews_lang') || 'en',
    tag: 'all',
    search: '',
    archiveSearch: '',
    articles: [],
    expanded: new Set(),
    view: 'today'
  };

  function t(key) {
    return STRINGS[state.lang][key] || key;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function escapeAttr(s) { return escapeHtml(s); }

  function paragraphsToHtml(text) {
    if (!text) return '';
    return text
      .split(/\n\s*\n/)
      .map(p => p.trim())
      .filter(p => p.length > 0)
      .map(p => '<p>' + escapeHtml(p) + '</p>')
      .join('');
  }

  function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now - d;
    const diffMin = Math.floor(diffMs / 60000);
    const diffH = Math.floor(diffMs / 3600000);
    const diffD = Math.floor(diffMs / 86400000);
    if (diffMin < 60) return Math.max(1, diffMin) + ' ' + t('ago_minutes');
    if (diffH < 24) return diffH + ' ' + t('ago_hours');
    if (diffD === 1) return t('ago_yesterday');
    if (diffD < 7) return diffD + ' ' + t('ago_days');
    return d.toLocaleDateString(state.lang === 'ny' ? 'en-MW' : 'en-GB',
      { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function shortDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString(state.lang === 'ny' ? 'en-MW' : 'en-GB',
      { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function renderTodayDate() {
    const el = document.getElementById('dateLabel');
    if (!el) return;
    const today = new Date();
    el.textContent = today.toLocaleDateString(state.lang === 'ny' ? 'en-MW' : 'en-GB',
      { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }

  function applyI18n() {
    document.documentElement.lang = state.lang === 'ny' ? 'ny' : 'en';
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
    });
    renderTodayDate();
  }

  function renderFilters() {
    ['filterRowMobile', 'filterRowDesktop', 'archiveFilterRow'].forEach(id => {
      const row = document.getElementById(id);
      if (!row) return;
      row.innerHTML = '';
      TAGS.forEach(tag => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chip' + (state.tag === tag ? ' active' : '');
        btn.textContent = t(tag);
        btn.addEventListener('click', () => {
          state.tag = tag;
          renderFilters();
          renderList();
          renderArchiveFull();
        });
        row.appendChild(btn);
      });
    });
  }

  function setView(view) {
    state.view = view;
    document.querySelectorAll('.nav-link').forEach(b => {
      b.classList.toggle('active', b.dataset.view === view);
    });
    // Only switch page sections — exclude the nav buttons themselves,
    // which also carry data-view to declare which view they activate.
    document.querySelectorAll('[data-view]:not(.nav-link)').forEach(el => {
      const matches = el.dataset.view === view;
      el.classList.toggle('hidden', !matches);
    });
    // Hide the desktop sidebar on About view (no need for filters there)
    const sidebar = document.querySelector('.page-side');
    if (sidebar) sidebar.style.display = (view === 'about') ? 'none' : '';
    if (view === 'archive') renderArchiveFull();
    if (view === 'today') renderList();
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function renderArchive() {
    const list = document.getElementById('archiveList');
    if (!list) return;
    list.innerHTML = '';
    const recent = state.articles.slice(0, 6);
    recent.forEach(a => {
      const c = a[state.lang] || a.en;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'archive-item';
      btn.innerHTML =
        '<span class="archive-title">' + escapeHtml(c.title) + '</span>' +
        '<span class="archive-date">' + escapeHtml(shortDate(a.published)) + '</span>';
      btn.addEventListener('click', () => {
        const target = document.getElementById('article-' + a.id);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          target.style.outline = '2px solid var(--brand)';
          setTimeout(() => { target.style.outline = ''; }, 1500);
        }
      });
      list.appendChild(btn);
    });
  }

  function renderArticleCard(a) {
    const c = a[state.lang] || a.en;
    const card = document.createElement('article');
    card.className = 'card';
    card.id = 'article-' + a.id;

    const hasMore = !!(c.body_more && c.body_more.trim());
    const isOpen = state.expanded.has(a.id);

    const sourcesHtml = (a.sources || []).map(s => {
      const name = (typeof s === 'string') ? s : s.name;
      const url = (typeof s === 'object') ? s.url : null;
      if (url) {
        return '<a class="src-link" href="' + escapeAttr(url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(name) + '</a>';
      }
      return '<span class="src-link">' + escapeHtml(name) + '</span>';
    }).join('');

    const moreHtml = hasMore
      ? '<div class="card-extended' + (isOpen ? ' open' : '') + '" id="ext-' + escapeAttr(a.id) + '">' + paragraphsToHtml(c.body_more) + '</div>' +
        '<button type="button" class="read-more' + (isOpen ? ' open' : '') + '" data-article-id="' + escapeAttr(a.id) + '" aria-expanded="' + isOpen + '">' +
          '<span class="rm-label">' + escapeHtml(isOpen ? t('show_less') : t('read_more')) + '</span>' +
          '<span class="chev" aria-hidden="true">▾</span>' +
        '</button>'
      : '';

    let langBadge = '';
    if (state.lang === 'ny') {
      if (a.ny_reviewed) {
        langBadge = '<span class="reviewed-badge" title="' + escapeAttr(t('reviewed_badge')) + '"><span aria-hidden="true">✓</span> ' + escapeHtml(t('reviewed_badge')) + '</span>';
      } else if (a.ny_needs_review) {
        langBadge = '<span class="needs-review-badge" title="' + escapeAttr(t('needs_review_badge')) + '"><span aria-hidden="true">⚠</span> ' + escapeHtml(t('needs_review_badge')) + '</span>';
      }
    }

    card.innerHTML =
      '<div class="card-meta">' +
        '<span class="tag tag-' + escapeAttr(a.tag) + '">' + escapeHtml(t(a.tag)) + '</span>' +
        '<span class="card-time">' + escapeHtml(formatDate(a.published)) + '</span>' +
        langBadge +
      '</div>' +
      '<h2>' + escapeHtml(c.title) + '</h2>' +
      '<p>' + escapeHtml(c.body) + '</p>' +
      moreHtml +
      '<div class="sources"><strong>' + escapeHtml(t('sources_label')) + ':</strong>' + sourcesHtml + '</div>';

    return card;
  }

  function attachReadMoreHandlers(container) {
    container.querySelectorAll('.read-more').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-article-id');
        const ext = document.getElementById('ext-' + id);
        if (!ext) return;
        const willOpen = !ext.classList.contains('open');
        ext.classList.toggle('open', willOpen);
        btn.classList.toggle('open', willOpen);
        btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
        btn.querySelector('.rm-label').textContent = willOpen ? t('show_less') : t('read_more');
        if (willOpen) state.expanded.add(id); else state.expanded.delete(id);
      });
    });
  }

  const TODAY_LIMIT = 5;  // Today view shows only the most recent N articles

  function renderList() {
    const list = document.getElementById('newsList');
    const empty = document.getElementById('emptyState');
    list.innerHTML = '';
    const q = state.search.trim().toLowerCase();
    let filtered = state.articles.filter(a => {
      if (state.tag !== 'all' && a.tag !== state.tag) return false;
      if (!q) return true;
      const c = a[state.lang] || a.en;
      const haystack = (c.title + ' ' + c.body + ' ' + (c.body_more || '')).toLowerCase();
      return haystack.includes(q);
    });
    // articles are already sorted newest first in loadArticles()
    filtered = filtered.slice(0, TODAY_LIMIT);

    if (filtered.length === 0) {
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');

    filtered.forEach(a => list.appendChild(renderArticleCard(a)));
    attachReadMoreHandlers(list);
  }

  function renderArchiveFull() {
    const list = document.getElementById('archiveFullList');
    const empty = document.getElementById('archiveEmpty');
    if (!list) return;
    list.innerHTML = '';
    const q = state.archiveSearch.trim().toLowerCase();
    const filtered = state.articles.filter(a => {
      if (state.tag !== 'all' && a.tag !== state.tag) return false;
      if (!q) return true;
      const c = a[state.lang] || a.en;
      const haystack = (c.title + ' ' + c.body + ' ' + (c.body_more || '')).toLowerCase();
      return haystack.includes(q);
    });

    if (filtered.length === 0) {
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');

    filtered.forEach(a => list.appendChild(renderArticleCard(a)));
    attachReadMoreHandlers(list);
  }

  function setLang(lang) {
    state.lang = lang;
    localStorage.setItem('eznews_lang', lang);
    document.querySelectorAll('.lang-btn').forEach(b => {
      const active = b.dataset.lang === lang;
      b.classList.toggle('active', active);
      b.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    applyI18n();
    renderFilters();
    renderArchive();
    renderList();
    renderArchiveFull();
  }

  function syncSearch(value) {
    state.search = value;
    const a = document.getElementById('searchInput');
    const b = document.getElementById('headerSearch');
    if (a && a.value !== value) a.value = value;
    if (b && b.value !== value) b.value = value;
    renderList();
  }

  async function loadArticles() {
    try {
      const res = await fetch('data/articles.json', { cache: 'no-cache' });
      const data = await res.json();
      state.articles = (data.articles || [])
        .sort((a, b) => new Date(b.published) - new Date(a.published));
    } catch (e) {
      console.error('Failed to load articles', e);
      state.articles = [];
    }
    renderArchive();
    renderList();
    renderArchiveFull();
  }

  function init() {
    document.getElementById('year').textContent = new Date().getFullYear();
    document.querySelectorAll('.lang-btn').forEach(b => {
      b.addEventListener('click', () => setLang(b.dataset.lang));
    });
    document.querySelectorAll('.nav-link').forEach(b => {
      b.addEventListener('click', () => setView(b.dataset.view));
    });
    const mobileSearch = document.getElementById('searchInput');
    const headerSearch = document.getElementById('headerSearch');
    const archiveSearchInput = document.getElementById('archiveSearch');
    if (mobileSearch) mobileSearch.addEventListener('input', e => syncSearch(e.target.value));
    if (headerSearch) headerSearch.addEventListener('input', e => syncSearch(e.target.value));
    if (archiveSearchInput) archiveSearchInput.addEventListener('input', e => {
      state.archiveSearch = e.target.value;
      renderArchiveFull();
    });
    setLang(state.lang);
    setView('today');
    loadArticles();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
