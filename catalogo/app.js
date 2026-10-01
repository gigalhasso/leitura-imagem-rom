(() => {
  const catalog = window.CATALOG_DATA;
  const types = ["Dragon", "Spellcaster", "Zombie", "Warrior", "BeastWarrior", "Beast", "WingedBeast", "Fiend", "Fairy", "Insect", "Dinosaur", "Reptile", "Fish", "SeaSerpent", "Machine", "Thunder", "Aqua", "Pyro", "Rock", "Plant", "Magic", "Trap", "Ritual", "Equip"];
  const attributes = ["Light", "Dark", "Earth", "Water", "Fire", "Wind", "Magic", "Trap"];
  const guardianStars = [null, "Mars", "Jupiter", "Saturn", "Uranus", "Pluto", "Neptune", "Moon", "Venus", "Mercury", "Sun"];
  const app = document.querySelector("#app");
  const datasetSelect = document.querySelector("#dataset-select");
  const footer = document.querySelector("#catalog-footer");
  let activeDatasetKey, datasetMeta, cards, byId, fusions, drops, decks, opponents, pools, equipment;
  const tableRowsDefault = 20;
  const escape = value => String(value).replace(/[&<>"']/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[char]);
  const typeName = card => types[card.type] ?? `Type ${card.type}`;
  const attributeName = card => attributes[card.attribute] ?? `Attribute ${card.attribute}`;
  const guardianStarName = star => guardianStars[star] ?? `#${star}`;
  const cardImageUrl = (id, kind = "full") => `images/${encodeURIComponent(activeDatasetKey)}/card_${String(id).padStart(3, "0")}_${kind}.png`;
  const opponentImageUrl = id => `images/${encodeURIComponent(activeDatasetKey)}/opponents/opponent_${String(id).padStart(2, "0")}.png?v=20260718-9`;
  const opponentImage = (opponent, className, lazy = true) => `<img class="${className}" src="${opponentImageUrl(opponent.id)}" alt="Retrato de ${escape(opponent.name)}"${lazy ? ' loading="lazy"' : ""} decoding="async">`;
  const opponentLink = (opponent, id) => `<a class="opponent-link" href="#/opponent/${id}"><img class="table-opponent-thumb" src="${opponentImageUrl(id)}" alt="" loading="lazy" decoding="async"><span>${escape(opponent?.name ?? `Oponente ${id}`)}</span></a>`;
  const cardLink = id => { const card = byId.get(+id); return card ? `<a class="card-link card-link-with-image" href="#/card/${card.id}"><img class="table-card-thumb" src="${cardImageUrl(card.id, "mini")}" alt="" loading="lazy" decoding="async"><span>#${card.id} ${escape(card.name)}</span></a>` : `#${id}`; };
  const cardLinkWithStats = id => { const card = byId.get(+id); return card ? `${cardLink(id)} <span class="inline-stats">(${card.attack}/${card.defense})</span>` : cardLink(id); };
  const cardArt = (card, className, lazy = true) => `<img class="${className}" src="${cardImageUrl(card.id)}" alt="Arte de ${escape(card.name)}"${lazy ? ' loading="lazy"' : ""} decoding="async">`;
  const stats = card => `<span class="stat-label">ATK/DEF</span><br>${card.attack}/${card.defense}`;
  const percentage = (weight, denominator = 2048) => `${(weight / denominator * 100).toFixed(3)}%`;
  const nav = route => document.querySelectorAll("[data-nav]").forEach(node => node.classList.toggle("active", node.dataset.nav === route));

  function updateTableViewport(wrap) {
    const scroll = wrap.querySelector(":scope > .table-scroll");
    const table = scroll?.querySelector("table");
    const rows = table?.tBodies[0] ? [...table.tBodies[0].rows] : [];
    const limitInput = wrap.previousElementSibling?.querySelector(".table-limit");
    const limit = Math.max(1, Math.floor(Number(limitInput?.value) || tableRowsDefault));
    if (limitInput) limitInput.value = limit;
    if (!scroll || !table) return;
    if (rows.length <= limit) {
      scroll.style.removeProperty("--table-visible-height");
      wrap.classList.remove("has-more-content");
      return;
    }

    const headerHeight = table.tHead?.getBoundingClientRect().height ?? 0;
    const visibleRowsHeight = rows.slice(0, limit)
      .reduce((height, row) => height + row.getBoundingClientRect().height, 0);
    scroll.style.setProperty("--table-visible-height", `${Math.ceil(headerHeight + visibleRowsHeight)}px`);
    updateTableScrollHint(wrap);
  }

  function updateTableScrollHint(wrap) {
    const scroll = wrap.querySelector(":scope > .table-scroll");
    if (!scroll) return;
    wrap.classList.toggle("has-more-content", scroll.scrollTop + scroll.clientHeight < scroll.scrollHeight - 1);
  }

  function decorateTables(root = app) {
    const wraps = root.matches?.(".table-wrap") ? [root] : [...root.querySelectorAll(".table-wrap")];
    wraps.filter(wrap => !wrap.dataset.scrollLimited).forEach(wrap => {
      const table = wrap.querySelector(":scope > table");
      if (!table) return;

      wrap.dataset.scrollLimited = "true";
      wrap.insertAdjacentHTML("beforebegin", `<div class="table-controls"><label>Linhas visíveis <input class="table-limit" type="number" min="1" value="${tableRowsDefault}" inputmode="numeric" aria-label="Linhas visíveis na tabela"></label></div>`);
      const scroll = document.createElement("div");
      scroll.className = "table-scroll";
      scroll.setAttribute("aria-label", `Tabela rolável; mostra até ${tableRowsDefault} linhas por vez`);
      table.before(scroll);
      scroll.append(table);
      wrap.insertAdjacentHTML("beforeend", '<div class="table-scroll-hint" aria-hidden="true"></div>');
      scroll.addEventListener("scroll", () => updateTableScrollHint(wrap), { passive: true });
      requestAnimationFrame(() => updateTableViewport(wrap));
    });
  }
  const notFound = () => `<div class="hero"><p class="eyebrow">CATÁLOGO</p><h1>Registro não encontrado</h1><a class="button" href="#/cards">Voltar às cartas</a></div>`;

  function cardGrid(list) {
    return `<div class="card-grid">${list.map(card => `<a class="card-row" href="#/card/${card.id}">${cardArt(card, "card-grid-image")}<div><div class="card-name">${escape(card.name)}</div><div class="card-id">ID ${card.id}</div><div class="card-type">${escape(typeName(card))}</div></div><div class="stats">${stats(card)}</div></a>`).join("")}</div>`;
  }

  function renderCards() {
    nav("cards");
    app.innerHTML = `<section class="hero"><p class="eyebrow">YU-GI-OH! FORBIDDEN MEMORIES · ${escape(datasetMeta.shortLabel)}</p><h1>${escape(datasetMeta.title)}</h1><p class="subtle">${escape(datasetMeta.description)}</p><form class="search-row" id="card-search"><input id="query" type="search" autocomplete="off" placeholder="Pesquise pelo nome, ID, tipo ou ATK"><button>Buscar</button></form></section><div class="filter-row"><select id="type-filter"><option value="">Todos os tipos</option>${types.map((type, index) => `<option value="${index}">${type}</option>`).join("")}</select><span class="count" id="card-count"></span></div><div id="card-results"></div>`;
    const query = document.querySelector("#query"), filter = document.querySelector("#type-filter"), results = document.querySelector("#card-results"), count = document.querySelector("#card-count");
    const update = () => {
      const text = query.value.trim().toLowerCase(); const selected = filter.value;
      const matches = cards.filter(card => (selected === "" || card.type === +selected) && (!text || `${card.id} ${card.name} ${typeName(card)} ${card.attack} ${card.defense}`.toLowerCase().includes(text)));
      count.textContent = `${matches.length} de ${cards.length} cartas`;
      results.innerHTML = matches.length ? cardGrid(matches) : `<div class="empty">Nenhuma carta corresponde à busca.</div>`;
    };
    document.querySelector("#card-search").addEventListener("submit", event => { event.preventDefault(); update(); });
    query.addEventListener("input", update); filter.addEventListener("change", update); update();
  }

  function fusionTable(rows, direction, card) {
    if (!rows.length) return `<div class="empty">Nenhuma fusão registrada nesta direção.</div>`;
    const resultCell = id => cardLinkWithStats(id);
    const cells = rows.map(row => {
      const partner = byId.get(direction === "material" ? (row.a === card.id ? row.b : row.a) : row.a);
      if (direction === "material") return `<tr><td>${cardLink(card.id)}</td><td>${cardLink(partner.id)}</td><td>${resultCell(row.result)}</td></tr>`;
      return `<tr><td>${cardLink(row.a)}</td><td>${cardLink(row.b)}</td><td>${resultCell(card.id)}</td></tr>`;
    }).join("");
    return `<div class="table-wrap"><table><thead><tr><th>Material A</th><th>Material B</th><th>Resultado</th></tr></thead><tbody>${cells}</tbody></table></div>`;
  }

  function rateTable(rows, mode) {
    if (!rows.length) return `<div class="empty">Nenhum registro de ${mode === "drop" ? "drop" : "deck"}.</div>`;
    return `<div class="table-wrap"><table><thead><tr><th>Carta</th><th>Peso</th><th>Probabilidade</th><th>1 em</th></tr></thead><tbody>${rows.sort((a, b) => b.weight - a.weight || a.card - b.card).map(row => `<tr><td>${cardLinkWithStats(row.card)}</td><td class="prob">${row.weight}/${row.denominator}</td><td class="prob">${percentage(row.weight, row.denominator)}</td><td class="prob">${(row.denominator / row.weight).toFixed(1)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function cardSources(card) {
    const dropRows = drops.filter(row => row.card === card.id);
    const deckRows = decks.filter(row => row.card === card.id);
    const dropBody = dropRows.length ? `<div class="table-wrap"><table><thead><tr><th>Oponente</th><th>Pool</th><th>Peso</th><th>Probabilidade</th></tr></thead><tbody>${dropRows.map(row => { const opponent = opponents.find(item => item.id === row.opponent); const pool = pools.find(item => item.opponent === row.opponent && item.code === row.pool); return `<tr><td>${opponentLink(opponent, row.opponent)}</td><td>${escape(pool?.poolName ?? row.pool)}</td><td class="prob">${row.weight}/${row.denominator}</td><td class="prob">${percentage(row.weight, row.denominator)}</td></tr>`; }).join("")}</tbody></table></div>` : `<div class="empty">Não aparece em drops extraídos.</div>`;
    const deckBody = deckRows.length ? `<div class="table-wrap"><table><thead><tr><th>Oponente</th><th>Peso no deck</th><th>Probabilidade</th></tr></thead><tbody>${deckRows.map(row => { const opponent = opponents.find(item => item.id === row.opponent); return `<tr><td>${opponentLink(opponent, row.opponent)}</td><td class="prob">${row.weight}/${row.denominator}</td><td class="prob">${percentage(row.weight, row.denominator)}</td></tr>`; }).join("")}</tbody></table></div>` : `<div class="empty">Não aparece em decks extraídos.</div>`;
    return `<section class="section"><div class="section-head"><h2>Onde encontrar</h2><span class="badge">${dropRows.length} registros</span></div>${dropBody}</section><section class="section"><div class="section-head"><h2>Decks de oponentes</h2><span class="badge">${deckRows.length} registros</span></div>${deckBody}</section>`;
  }

  function acceptedEquipmentTable(card) {
    const rows = equipment.filter(row => row.card === card.id);
    if (!rows.length) return `<div class="empty">Esta carta não aceita equipamentos.</div>`;
    return `<div class="table-wrap"><table><thead><tr><th>Equipamento</th></tr></thead><tbody>${rows.map(row => `<tr><td>${cardLink(row.equip)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function equipmentSection(card) {
    if (card.type < 20) {
      const count = equipment.filter(row => row.card === card.id).length;
      return `<section class="section"><div class="section-head"><h2>Equipamentos aceitos</h2><span class="badge">${count} equipamentos</span></div>${acceptedEquipmentTable(card)}</section>`;
    }
    if (card.type === 23) {
      const rows = equipment
        .filter(row => row.equip === card.id)
        .sort((a, b) => {
          const cardA = byId.get(a.card), cardB = byId.get(b.card);
          return cardB.attack - cardA.attack || cardB.defense - cardA.defense || cardA.id - cardB.id;
        });
      const body = rows.length
        ? `<div class="table-wrap"><table><thead><tr><th>Carta equipada</th></tr></thead><tbody>${rows.map(row => `<tr><td>${cardLinkWithStats(row.card)}</td></tr>`).join("")}</tbody></table></div>`
        : `<div class="empty">Este equipamento não equipa nenhuma carta.</div>`;
      return `<section class="section"><div class="section-head"><h2>Cartas que este equipamento equipa</h2><span class="badge">${rows.length} cartas</span></div>${body}</section>`;
    }
    return "";
  }

  function renderCard(id) {
    const card = byId.get(+id); if (!card) { nav("cards"); app.innerHTML = notFound(); return; }
    nav("cards");
    const asMaterial = fusions.filter(row => row.a === card.id || row.b === card.id);
    const asResult = fusions.filter(row => row.result === card.id);
    app.innerHTML = `<div class="crumbs"><a href="#/cards">Cartas</a> / #${card.id}</div><article class="card-detail">${cardArt(card, "card-art-main", false)}<div><p class="eyebrow">ID ${card.id} · ${escape(typeName(card))}</p><h1>${escape(card.name)}</h1><p class="subtle">Dados e imagem extraídos da ROM modificada.</p><div class="card-meta"><div><span class="stat-label">ATK</span><strong>${card.attack}</strong></div><div><span class="stat-label">DEF</span><strong>${card.defense}</strong></div><div><span class="stat-label">Atributo</span><strong>${escape(attributeName(card))}</strong></div><div><span class="stat-label">Nível</span><strong>${card.level}</strong></div><div><span class="stat-label">Guardian Stars</span><strong>${guardianStarName(card.gs1)} / ${guardianStarName(card.gs2)}</strong></div><div><span class="stat-label">Imagem</span><strong>102 × 96</strong></div></div></div></article><section class="section"><div class="section-head"><h2>Fusões como material</h2><span class="badge">${asMaterial.length} combinações</span></div>${fusionTable(asMaterial, "material", card)}</section><section class="section"><div class="section-head"><h2>Fusões como resultado</h2><span class="badge">${asResult.length} combinações</span></div>${fusionTable(asResult, "result", card)}</section>${cardSources(card)}${equipmentSection(card)}`;
  }

  function renderOpponents() {
    nav("opponents");
    app.innerHTML = `<section class="hero"><p class="eyebrow">DUELOS E RECOMPENSAS</p><h1>Oponentes</h1><p class="subtle">Consulte os pools de drop e a composição probabilística de cada deck.</p></section><section class="section"><div class="opponent-list">${opponents.map(opponent => `<a class="opponent" href="#/opponent/${opponent.id}">${opponentImage(opponent, "opponent-list-image")}<span><strong>${escape(opponent.name)}</strong><small>${opponent.possible} cartas no deck · peso total ${opponent.total}</small></span></a>`).join("")}</div></section>`;
  }

  function renderOpponent(id) {
    const opponent = opponents.find(item => item.id === +id); if (!opponent) { nav("opponents"); app.innerHTML = notFound(); return; }
    nav("opponents");
    const opponentPools = pools.filter(pool => pool.opponent === opponent.id);
    const deckRows = decks.filter(row => row.opponent === opponent.id);
    app.innerHTML = `<div class="crumbs"><a href="#/opponents">Oponentes</a> / ${escape(opponent.name)}</div><section class="hero opponent-hero">${opponentImage(opponent, "opponent-main-image", false)}<div><p class="eyebrow">OPONENTE ${opponent.id}</p><h1>${escape(opponent.name)}</h1><p class="subtle">Deck: ${opponent.possible} cartas possíveis · distribuição total ${opponent.total}/2048.</p></div></section><section class="section"><div class="section-head"><h2>Cartas e drop rate</h2><span class="badge">Deck e 3 pools por método de vitória</span></div><div class="pool-tabs"><button data-view="deck" class="active">Deck</button>${opponentPools.map(pool => `<button data-view="${escape(pool.code)}">${escape(pool.poolName)}</button>`).join("")}</div><div id="pool-content"></div></section>`;
    const holder = document.querySelector("#pool-content");
    const showView = code => {
      if (code === "deck") { holder.innerHTML = `<p class="subtle">Probabilidade de cada carta entrar na mão desse oponente.</p>${rateTable(deckRows, "deck")}`; return; }
      const pool = opponentPools.find(item => item.code === code);
      holder.innerHTML = `<p class="subtle">${escape(pool?.ranks ?? "")}</p>${rateTable(drops.filter(row => row.opponent === opponent.id && row.pool === code), "drop")}`;
    };
    document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => { document.querySelectorAll("[data-view]").forEach(item => item.classList.toggle("active", item === button)); showView(button.dataset.view); }));
    showView("deck");
  }

  function render() {
    const route = location.hash.replace(/^#\/?/, "") || "cards";
    const [, kind, id] = route.match(/^(card|opponent)\/(\d+)$/) || [];
    if (kind === "card") renderCard(id); else if (kind === "opponent") renderOpponent(id); else if (route === "opponents") renderOpponents(); else renderCards();
  }
  function loadDataset(key) {
    const data = catalog.datasets[key];
    activeDatasetKey = key;
    datasetMeta = data.meta;
    cards = data.cards.map(([id, name, attack, defense, gs1, gs2, type, level, attribute]) => ({ id:+id, name, attack:+attack, defense:+defense, gs1:+gs1, gs2:+gs2, type:+type, level:+level, attribute:+attribute }));
    byId = new Map(cards.map(card => [card.id, card]));
    fusions = data.fusions.map(([a, b, result, origin]) => ({ a:+a, b:+b, result:+result, origin }));
    drops = data.drops.map(([opponent, pool, card, weight, denominator]) => ({ opponent:+opponent, pool, card:+card, weight:+weight, denominator:+denominator }));
    decks = data.decks.map(([opponent, card, weight, denominator]) => ({ opponent:+opponent, card:+card, weight:+weight, denominator:+denominator }));
    opponents = data.opponents.map(([id, name, possible, total, highest]) => ({ id:+id, name, possible:+possible, total:+total, highest:+highest }));
    pools = data.pools.map(([opponent, name, code, poolName, ranks, possible, total]) => ({ opponent:+opponent, name, code, poolName, ranks, possible:+possible, total:+total }));
    equipment = data.equipment.map(([card, equip]) => ({ card:+card, equip:+equip }));
    datasetSelect.value = key;
    footer.textContent = datasetMeta.footer;
    document.title = `${datasetMeta.shortLabel} · FM Mod Database`;
  }

  datasetSelect.innerHTML = Object.entries(catalog.datasets).map(([key, data]) => `<option value="${escape(key)}">${escape(data.meta.label)}</option>`).join("");
  datasetSelect.addEventListener("change", () => {
    loadDataset(datasetSelect.value);
    try { localStorage.setItem("fm-catalog-dataset", datasetSelect.value); } catch {}
    render();
  });
  let savedDataset;
  try { savedDataset = localStorage.getItem("fm-catalog-dataset"); } catch {}
  const requestedDataset = new URLSearchParams(location.search).get("mod");
  const initialDataset = catalog.datasets[requestedDataset]
    ? requestedDataset
    : (catalog.datasets[savedDataset] ? savedDataset : catalog.defaultDataset);
  loadDataset(initialDataset);
  app.addEventListener("input", event => {
    if (!event.target.matches(".table-limit")) return;
    updateTableViewport(event.target.closest(".table-controls").nextElementSibling);
  });
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === Node.ELEMENT_NODE) decorateTables(node);
  }))).observe(app, { childList: true, subtree: true });
  window.addEventListener("resize", () => document.querySelectorAll(".table-wrap[data-scroll-limited]").forEach(updateTableViewport));
  window.addEventListener("hashchange", render); render();
})();
