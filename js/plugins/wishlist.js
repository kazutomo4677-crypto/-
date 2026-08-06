/* ============================================
   Wishlist Plugin for 祭彩
   Adds heart buttons to product cards and a
   wishlist modal accessible from the header.
   ============================================ */

var WishlistPlugin = {
  name: 'matsuri-wishlist',
  version: '1.0.0',
  description: 'Save products to a wishlist and manage them from the header',

  _api: null,
  _ids: [],   // wishlisted product IDs

  install: function (api) {
    var self = this;
    self._api = api;
    self._load();
    self._injectStyles();
    self._injectHeaderButton();
    self._injectModal();

    api.on('products:render', function () {
      // DOM needs one tick to settle after innerHTML swap
      setTimeout(function () { self._attachHeartButtons(); }, 50);
    });

    api.on('app:ready', function () {
      setTimeout(function () { self._attachHeartButtons(); }, 100);
    });

    // Public surface — useful for product detail page or other plugins
    window.MatsuriWishlist = {
      toggle:       function (id) { return self.toggle(id); },
      isWishlisted: function (id) { return self.isWishlisted(id); },
      getAll:       function ()   { return self._ids.slice(); },
    };
  },

  // ---- state ----

  _load: function () {
    try {
      var raw = localStorage.getItem('matsuri-wishlist');
      this._ids = raw ? JSON.parse(raw) : [];
    } catch (e) { this._ids = []; }
  },

  _save: function () {
    localStorage.setItem('matsuri-wishlist', JSON.stringify(this._ids));
  },

  toggle: function (productId) {
    var idx = this._ids.indexOf(productId);
    if (idx >= 0) {
      this._ids.splice(idx, 1);
    } else {
      this._ids.push(productId);
    }
    this._save();
    this._syncHeartButtons();
    this._syncBadge();

    var product = this._api.getProducts().find(function (p) { return p.id === productId; });
    if (product) {
      var removed = idx >= 0;
      this._api.showToast(removed
        ? product.name + ' をウィッシュリストから削除しました'
        : product.name + ' をウィッシュリストに追加しました');
    }
    this._api.emit('wishlist:change', { wishlist: this._ids.slice() });
  },

  isWishlisted: function (id) {
    return this._ids.indexOf(id) >= 0;
  },

  // ---- DOM injection ----

  _injectStyles: function () {
    var css = [
      /* heart button on product card */
      '.wl-btn{position:absolute;top:10px;left:10px;width:32px;height:32px;border-radius:50%;border:none;',
      'background:rgba(255,255,255,.92);cursor:pointer;display:flex;align-items:center;justify-content:center;',
      'transition:transform .2s,background .2s;z-index:2;box-shadow:0 2px 8px rgba(0,0,0,.15);}',
      '.wl-btn:hover{transform:scale(1.13);background:#fff;}',
      '.wl-btn.active{background:#e8443a;}',
      '.wl-btn.active svg{stroke:#fff;fill:#fff;}',
      /* header button & badge */
      '.wl-nav-btn{position:relative;}',
      '.wl-badge{position:absolute;top:-6px;right:-6px;background:#e8443a;color:#fff;font-size:10px;',
      'font-weight:700;min-width:18px;height:18px;border-radius:9px;display:none;align-items:center;',
      'justify-content:center;padding:0 3px;pointer-events:none;}',
      '.wl-badge.show{display:flex;}',
      /* modal overlay */
      '.wl-modal{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:2000;display:none;',
      'align-items:center;justify-content:center;padding:20px;}',
      '.wl-modal.active{display:flex;}',
      /* modal box */
      '.wl-box{background:#fef7ed;border-radius:16px;padding:32px;max-width:500px;width:100%;',
      'max-height:80vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.2);}',
      '.wl-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;}',
      '.wl-title{font-size:1.15rem;font-weight:700;}',
      '.wl-close-btn{background:none;border:none;font-size:1.6rem;cursor:pointer;color:#6b7280;line-height:1;}',
      /* list items */
      '.wl-item{display:flex;gap:14px;align-items:center;padding:12px 0;border-bottom:1px solid rgba(0,0,0,.07);}',
      '.wl-item:last-child{border-bottom:none;}',
      '.wl-thumb{width:52px;height:52px;border-radius:10px;flex-shrink:0;}',
      '.wl-info{flex:1;min-width:0;}',
      '.wl-name{font-size:.875rem;font-weight:600;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}',
      '.wl-price{font-size:.8rem;color:#e8443a;font-weight:700;}',
      '.wl-actions{display:flex;gap:8px;flex-shrink:0;}',
      '.wl-add-btn{font-size:.75rem;padding:5px 12px;border-radius:8px;border:none;background:#e8443a;',
      'color:#fff;cursor:pointer;white-space:nowrap;font-weight:600;}',
      '.wl-add-btn:hover{background:#c0392b;}',
      '.wl-rm-btn{font-size:.75rem;padding:5px 10px;border-radius:8px;border:1px solid #d1d5db;',
      'background:none;cursor:pointer;color:#6b7280;}',
      '.wl-rm-btn:hover{background:#f3f4f6;}',
      '.wl-empty{text-align:center;color:#9ca3af;padding:40px 0;font-size:.95rem;line-height:1.8;}',
    ].join('');
    var el = document.createElement('style');
    el.textContent = css;
    document.head.appendChild(el);
  },

  _injectHeaderButton: function () {
    var actions = document.querySelector('.header-actions');
    if (!actions) return;

    var btn = document.createElement('button');
    btn.className = 'icon-btn wl-nav-btn';
    btn.id = 'wl-header-btn';
    btn.setAttribute('aria-label', 'ウィッシュリスト');
    btn.innerHTML = [
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">',
      '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78',
      'l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
      '</svg>',
      '<span class="wl-badge" id="wl-badge"></span>',
    ].join('');

    var hamburger = actions.querySelector('.hamburger');
    actions.insertBefore(btn, hamburger || null);

    var self = this;
    btn.addEventListener('click', function () { self._openModal(); });
    this._syncBadge();
  },

  _injectModal: function () {
    var modal = document.createElement('div');
    modal.className = 'wl-modal';
    modal.id = 'wl-modal';
    modal.innerHTML = [
      '<div class="wl-box">',
      '<div class="wl-head">',
      '<span class="wl-title">&#10084; ウィッシュリスト</span>',
      '<button class="wl-close-btn" id="wl-close">&times;</button>',
      '</div>',
      '<div id="wl-items"></div>',
      '</div>',
    ].join('');
    document.body.appendChild(modal);

    var self = this;
    document.getElementById('wl-close').addEventListener('click', function () { self._closeModal(); });
    modal.addEventListener('click', function (e) { if (e.target === modal) self._closeModal(); });
  },

  // ---- heart buttons ----

  _attachHeartButtons: function () {
    var self = this;
    document.querySelectorAll('.product-card[data-id]').forEach(function (card) {
      var id = parseInt(card.dataset.id, 10);
      if (!id || card.querySelector('.wl-btn')) return;

      var btn = document.createElement('button');
      btn.className = 'wl-btn' + (self.isWishlisted(id) ? ' active' : '');
      btn.dataset.wlId = id;
      btn.title = 'ウィッシュリストに追加';
      btn.innerHTML = [
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">',
        '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78',
        'l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
        '</svg>',
      ].join('');
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        self.toggle(id);
      });

      var imgArea = card.querySelector('.product-card-img');
      if (imgArea) imgArea.appendChild(btn);
    });
  },

  _syncHeartButtons: function () {
    var self = this;
    document.querySelectorAll('.wl-btn[data-wl-id]').forEach(function (btn) {
      var id = parseInt(btn.dataset.wlId, 10);
      btn.classList.toggle('active', self.isWishlisted(id));
    });
  },

  _syncBadge: function () {
    var badge = document.getElementById('wl-badge');
    if (!badge) return;
    var count = this._ids.length;
    badge.textContent = count > 0 ? String(count) : '';
    badge.classList.toggle('show', count > 0);
  },

  // ---- modal ----

  _openModal: function () {
    var self = this;
    var modal   = document.getElementById('wl-modal');
    var itemsEl = document.getElementById('wl-items');
    if (!modal || !itemsEl) return;

    var products = this._api.getProducts();
    var items = this._ids
      .map(function (id) { return products.find(function (p) { return p.id === id; }); })
      .filter(Boolean);

    if (items.length === 0) {
      itemsEl.innerHTML = '<p class="wl-empty">ウィッシュリストは空です<br><small>商品カードの ♡ で追加できます</small></p>';
    } else {
      itemsEl.innerHTML = items.map(function (p) {
        var grad = p.colors.length === 1 ? p.colors[0] : 'linear-gradient(135deg,' + p.colors.join(',') + ')';
        return [
          '<div class="wl-item">',
          '<div class="wl-thumb" style="background:' + grad + '"></div>',
          '<div class="wl-info">',
          '<p class="wl-name">' + p.name + '</p>',
          '<p class="wl-price">&yen;' + p.price.toLocaleString() + '</p>',
          '</div>',
          '<div class="wl-actions">',
          '<button class="wl-add-btn" onclick="MatsuriPlugins.get(\'matsuri-wishlist\')._modalAddToCart(' + p.id + ')">カートへ</button>',
          '<button class="wl-rm-btn"  onclick="MatsuriPlugins.get(\'matsuri-wishlist\')._modalRemove(' + p.id + ')">削除</button>',
          '</div>',
          '</div>',
        ].join('');
      }).join('');
    }

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  },

  _modalAddToCart: function (id) {
    this._api.addToCart(id);
  },

  _modalRemove: function (id) {
    this.toggle(id);
    this._openModal();   // re-render in place
  },

  _closeModal: function () {
    var modal = document.getElementById('wl-modal');
    if (modal) modal.classList.remove('active');
    document.body.style.overflow = '';
  },
};

if (window.MatsuriPlugins) {
  MatsuriPlugins.use(WishlistPlugin);
}
