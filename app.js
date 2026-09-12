const state = { products: [], source: '', favorites: new Set(JSON.parse(localStorage.getItem('bhima-favorites') || '[]')), goldRate: null };
const $ = (id) => document.getElementById(id);
const money = (value) => value == null ? '--' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
const ratio = (value) => value == null ? '--' : `${(value * 100).toFixed(2)}%`;
const va = (value) => value == null ? '--' : `${((1 - value) * 100).toFixed(2)}%`;
const purityOf = (name) => (name.match(/\b(18\s*kt|22\s*kt|22\s*k|24\s*kt)\b/i) || [])[1]?.replace(/\s+/g, '').toUpperCase() || 'Other';
const categoryOf = (name) => { const terms = ['necklace','chain','bangle','ring','earring','stud','drops','mangalsutra','haar am','haaram','pendant','bracelet','coin','anklet','nosepin']; const found = terms.find((term) => name.toLowerCase().includes(term)); return found === 'haar am' ? 'Haaram' : found ? found[0].toUpperCase() + found.slice(1) : 'Other'; };
const audienceOf = (name) => { const l = name.toLowerCase(); if (l.includes('baby') || l.includes('kids') || l.includes('kid') || l.includes('child')) return 'Kids'; if (l.includes('women') || l.includes('woman')) return 'Women'; if (l.includes('unisex')) return 'Unisex'; if (l.includes(' men') || l.startsWith('men ') || l.includes('for men') || l.includes(' gents')) return 'Men'; return 'Unisex/Other'; };
const collectionOf = (p) => p.category_api || categoryOf(p.name || '');
function populateSelect(id, values) { const select = $(id); if(!select) return; const existing = new Set([...select.options].map(o=>o.value)); [...new Set(values)].sort().forEach((value) => { if(!existing.has(value)) select.insertAdjacentHTML('beforeend', `<option value="${value}">${value}</option>`); }); }
function saveFavorites() { localStorage.setItem('bhima-favorites', JSON.stringify([...state.favorites])); }
function filteredProducts() {
  const query = $('searchInput').value.trim().toLowerCase();
  const minPrice = Number($('minPrice').value) || 0;
  const maxPrice = Number($('maxPrice').value) || Infinity;
  const minWeight = Number($('minWeight')?.value) || 0;
  const maxWeight = Number($('maxWeight')?.value) || Infinity;
  const minRatio = Number($('minRatio').value) / 100;
  const purity = $('puritySelect').value;
  const category = $('categorySelect').value;
  const audience = $('audienceSelect').value;
  const collection = $('collectionSelect')?.value || '';
  const favoritesOnly = $('favoritesOnly').checked;
  const filtered = state.products.filter((product) => {
    const name = product.name || '';
    const w = product.gross_weight ?? product.metal_weight ?? product.weight_proxy_g ?? 0;
    const col = collectionOf(product);
    return product.value_ratio != null
      && (!query || name.toLowerCase().includes(query))
      && (product.grand_total || 0) >= minPrice && (product.grand_total || 0) <= maxPrice
      && w >= minWeight && w <= maxWeight
      && product.value_ratio >= minRatio
      && (!purity || (product.purity || purityOf(name)) === purity)
      && (!category || categoryOf(name) === category)
      && (!collection || col === collection)
      && (!audience || (product.audience || audienceOf(name)) === audience)
      && (!favoritesOnly || state.favorites.has(product.url));
  });
  const sort = $('sortSelect').value;
  return filtered.sort((a, b) => {
    if (sort === 'price-low') return a.grand_total - b.grand_total;
    if (sort === 'price-high') return b.grand_total - a.grand_total;
    if (sort === 'name') return a.name.localeCompare(b.name);
    if (sort === 'weight-low') return (a.weight_proxy_g||0) - (b.weight_proxy_g||0);
    if (sort === 'weight-high') return (b.weight_proxy_g||0) - (a.weight_proxy_g||0);
    if (sort === 'making-low') return (a.making_charges_proxy||0) - (b.making_charges_proxy||0);
    return b.value_ratio - a.value_ratio;
  });
}
function render() {
  const products = filteredProducts();
  $('visibleCount').textContent = products.length.toLocaleString('en-IN');
  $('bestRatio').textContent = products[0] ? ratio(products[0].value_ratio) : '--';
  $('bestVa').textContent = products[0] ? va(products[0].value_ratio) : '--';
  const grid = $('productGrid');
  if (!products.length) { grid.innerHTML = '<div class="empty">No products match these filters.</div>'; return; }
  grid.innerHTML = '';
  products.forEach((product, index) => {
    const card = $('productTemplate').content.cloneNode(true);
    card.querySelector('.rank').textContent = `#${index + 1}`;
    card.querySelector('.product-name').textContent = product.name;
    card.querySelector('.purity-chip').textContent = product.purity || purityOf(product.name);
    const catText = categoryOf(product.name);
    card.querySelector('.category-chip').textContent = catText;
    const audChip = card.querySelector('.audience-chip');
    audChip.textContent = product.audience || audienceOf(product.name);
    const colChip = card.querySelector('.collection-chip');
    const colText = collectionOf(product);
    // hide duplicate BANGLE chip (collection same as category)
    if (colText && colText.toLowerCase() === catText.toLowerCase()) {
      colChip.style.display = 'none';
    } else {
      colChip.textContent = colText;
      colChip.style.display = '';
    }
    // image
    const img = card.querySelector('.product-image');
    if (product.image) { img.src = product.image; img.style.display = 'block'; img.onerror = () => img.style.display='none'; }
    card.querySelector('.grand-total').textContent = money(product.grand_total);
    card.querySelector('.gold-value').textContent = money(product.gold_value);
    const wEl = card.querySelector('.weight');
    if (wEl) {
      const actual = product.gross_weight ?? product.metal_weight ?? product.weight_proxy_g;
      const label = product.gross_weight != null ? `${actual} g` : product.weight_proxy_g != null ? `${actual} g (proxy)` : '--';
      wEl.textContent = label;
      wEl.title = product.gross_weight ? `Actual gross: ${product.gross_weight}g` : `Proxy from gold_value / rate`;
    }
    const mEl = card.querySelector('.making');
    if (mEl) {
      const making = product.making_charges ?? product.making_charges_proxy;
      const pct = product.making_pct ?? (making && product.grand_total ? (making/product.grand_total*100).toFixed(2) : null);
      mEl.textContent = making != null ? `${money(making)}${pct ? ` (${pct}%)` : ''}` : '--';
    }
    const dimEl = card.querySelector('.dimensions');
    const rateEl = card.querySelector('.rate');
    const dims = [product.length ? `L:${product.length}` : null, product.width ? `W:${product.width}` : null, product.thickness ? `T:${product.thickness}` : null].filter(Boolean).join(' ');
    const hasDims = !!dims;
    const hasRate = product.rate != null;
    if (dimEl) {
      if (hasDims) {
        dimEl.textContent = dims;
        dimEl.title = `Length/Width/Thickness`;
      } else {
        dimEl.textContent = '—';
        dimEl.title = 'Pending full HTML crawl - auto-refresh will fill';
      }
    }
    if (rateEl) rateEl.textContent = hasRate ? `₹${product.rate}/g` : '—';
    // hide entire Dimensions/Rate row if both missing (only hotfixed #13 has both)
    if (!hasDims && !hasRate) {
      const row = dimEl?.closest('.numbers');
      if (row) row.style.display = 'none';
    }
    card.querySelector('.value-ratio').textContent = ratio(product.value_ratio);
    card.querySelector('.va-value').textContent = va(product.value_ratio);
    const link = card.querySelector('.product-link');
    link.href = product.url;
    const save = card.querySelector('.save-button');
    const saved = state.favorites.has(product.url);
    save.textContent = saved ? '★' : '☆';
    save.classList.toggle('saved', saved);
    save.addEventListener('click', () => { saved ? state.favorites.delete(product.url) : state.favorites.add(product.url); saveFavorites(); render(); });
    grid.appendChild(card);
  });
}
async function loadGoldRate() {
  try {
    const r = await fetch('/gold_rate.json?time=' + Date.now()).then(res => res.json()).catch(()=>null);
    if (r && r.inr_per_g_22k) {
      state.goldRate = r;
      $('goldRateBadge').textContent = `Gold 22K: ${money(r.inr_per_g_22k)}/g`;
      return;
    }
  } catch {}
  try {
    const r2 = await fetch('/api/gold-rate').then(res=>res.json()).catch(()=>null);
    if (r2 && r2.inr_per_g_22k) {
      state.goldRate = r2;
      $('goldRateBadge').textContent = `Gold 22K: ${money(r2.inr_per_g_22k)}/g (${r2.source})`;
    }
  } catch { $('goldRateBadge').textContent = 'Gold 22K: --'; }
}
async function load() {
  $('sourceBadge').textContent = 'Loading data';
  try {
    const response = await fetch(`/api/products?time=${Date.now()}`);
    const data = await response.json();
    state.products = data.products || [];
    state.source = data.source;
    $('totalCount').textContent = state.products.length.toLocaleString('en-IN');
    $('sourceBadge').textContent = data.source ? `Source: ${data.source}` : 'No data';
    populateSelect('puritySelect', state.products.map((p) => p.purity || purityOf(p.name)));
    populateSelect('categorySelect', state.products.map((p) => categoryOf(p.name)));
    populateSelect('audienceSelect', state.products.map((p) => p.audience || audienceOf(p.name)));
    populateSelect('collectionSelect', state.products.map((p) => collectionOf(p)));
    const invalid = state.products.filter((p) => p.value_ratio == null).length;
    const withWeight = state.products.filter(p=>p.weight_proxy_g!=null).length;
    const withMaking = state.products.filter(p=>p.making_charges_proxy!=null).length;
    $('notice').hidden = false;
    $('notice').innerHTML = `${invalid} products could not be parsed. <strong>${withWeight}</strong> with weight proxy (gold value / live 22K rate), <strong>${withMaking}</strong> with making+GST proxy (grand_total - gold_value). History: ${state.products.length} snapshot ${new Date().toLocaleDateString()}. Size not in current API - needs detail scrape.`;
    await loadGoldRate();
    render();
  } catch (error) {
    $('sourceBadge').textContent = 'Data unavailable';
    $('notice').hidden = false;
    $('notice').textContent = `Could not load ranking data: ${error.message}`;
  }
}
function exportView() {
  const products = filteredProducts();
  const headers = ['rank','name','url','gold_value','grand_total','value_ratio','va_proxy','weight_g','making_proxy','making_pct','purity','audience','category'];
  const rows = products.map((p, i) => [i+1, p.name, p.url, p.gold_value, p.grand_total, p.value_ratio, 1-p.value_ratio, p.weight_proxy_g, p.making_charges_proxy, p.making_pct, p.purity, p.audience, p.category_api]);
  const csv = [headers, ...rows].map((row) => row.map((v) => `"${String(v ?? '').replaceAll('"', '""')}"`).join(',')).join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  link.download = 'bhima-gold-filtered.csv';
  link.click();
  URL.revokeObjectURL(link.href);
}
['searchInput','minPrice','maxPrice','minWeight','maxWeight','puritySelect','categorySelect','audienceSelect','collectionSelect','favoritesOnly','sortSelect'].forEach((id) => { const el=$(id); if(el) el.addEventListener('input', render); if(el && el.tagName==='SELECT') el.addEventListener('change', render); });
$('minRatio')?.addEventListener('input', () => { $('ratioOutput').value = `${$('minRatio').value}%`; $('ratioOutput').textContent = `${$('minRatio').value}%`; render(); });
$('clearButton')?.addEventListener('click', () => { ['searchInput','minPrice','maxPrice','minWeight','maxWeight'].forEach((id) => { const e=$(id); if(e) e.value=''; }); $('minRatio').value = 0; $('ratioOutput').textContent = '0%'; ['puritySelect','categorySelect','audienceSelect','collectionSelect'].forEach(id=>{ const e=$(id); if(e) e.value=''; }); $('favoritesOnly').checked = false; render(); });
$('refreshButton')?.addEventListener('click', load);
$('exportButton')?.addEventListener('click', exportView);
load();
