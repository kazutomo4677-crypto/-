/* ============================================
   Product Detail Page JavaScript
   ============================================ */

(function() {
  // Get product ID from URL
  const params = new URLSearchParams(window.location.search);
  const productId = parseInt(params.get('id')) || 1;

  // Find the product
  const product = products.find(p => p.id === productId) || products[0];

  // Category labels
  const categoryLabels = {
    illustration: 'ILLUSTRATION',
    apparel: 'APPAREL',
    accessory: 'ACCESSORY',
    print: 'PRINT'
  };

  // Extended descriptions
  const extendedDescriptions = {
    illustration: 'アーティストが一点一点丁寧に制作したオリジナルイラストレーション。鮮やかな色彩と繊細なディテールが融合し、空間を華やかに彩ります。額装してお届けするので、届いたその日からお楽しみいただけます。',
    apparel: '祭彩の世界観をまとえるアパレルアイテム。厳選された素材に、高品質なプリント技術でアートを再現。日常に彩りを添える特別な一着です。',
    accessory: '日々の生活に祭彩のエッセンスを。ハンドメイドで丁寧に仕上げたアクセサリー・雑貨は、プレゼントにも最適です。',
    print: '高精細なジークレープリントで再現されたアートワーク。発色の美しさと耐久性を両立した特別仕様。お部屋のインテリアに華を添えます。'
  };

  const description = product.description + ' ' + (extendedDescriptions[product.category] || '');

  // Populate page
  document.title = `${product.name} | 祭彩 -MATSURI SAI-`;
  document.getElementById('breadcrumb-name').textContent = product.name;
  document.getElementById('product-category').textContent = categoryLabels[product.category] || '';
  document.getElementById('product-title').textContent = product.name;
  document.getElementById('product-price').textContent = formatPrice(product.price);
  document.getElementById('product-description').textContent = description;

  if (product.originalPrice) {
    document.getElementById('product-original-price').textContent = formatPrice(product.originalPrice);
  }

  // Main image with gradient
  const mainImg = document.getElementById('product-main-img');
  mainImg.style.background = createGradient(product.colors);

  // Generate thumbnail color variations
  const thumbs = document.getElementById('product-thumbs');
  const variations = [
    product.colors,
    [...product.colors].reverse(),
    product.colors.map((c, i) => product.colors[(i + 1) % product.colors.length]),
    [product.colors[0], '#1a1a2e', product.colors[product.colors.length - 1]]
  ];

  variations.forEach((colors, i) => {
    const thumb = document.createElement('div');
    thumb.className = `product-thumb ${i === 0 ? 'active' : ''}`;
    thumb.style.background = createGradient(colors);
    thumb.addEventListener('click', () => {
      mainImg.style.background = createGradient(colors);
      document.querySelectorAll('.product-thumb').forEach(t => t.classList.remove('active'));
      thumb.classList.add('active');
    });
    thumbs.appendChild(thumb);
  });

  // Quantity selector
  let qty = 1;
  const qtyValue = document.getElementById('qty-value');
  document.getElementById('qty-minus').addEventListener('click', () => {
    if (qty > 1) {
      qty--;
      qtyValue.textContent = qty;
    }
  });
  document.getElementById('qty-plus').addEventListener('click', () => {
    if (qty < 10) {
      qty++;
      qtyValue.textContent = qty;
    }
  });

  // Add to cart
  document.getElementById('add-to-cart-btn').addEventListener('click', () => {
    for (let i = 0; i < qty; i++) {
      addToCart(product.id);
    }
  });

  // Related products (same category, different ID)
  const related = products
    .filter(p => p.category === product.category && p.id !== product.id)
    .slice(0, 4);

  // If not enough from same category, fill from other categories
  if (related.length < 4) {
    const others = products
      .filter(p => p.id !== product.id && !related.includes(p))
      .slice(0, 4 - related.length);
    related.push(...others);
  }

  const relatedGrid = document.getElementById('related-grid');
  relatedGrid.innerHTML = related.map((p, i) => {
    const badgeHtml = p.badge
      ? `<span class="product-card-badge ${p.badge}">${
          p.badge === 'new' ? 'NEW' :
          p.badge === 'limited' ? 'LIMITED' :
          p.badge === 'sale' ? 'SALE' : ''
        }</span>`
      : '';

    const priceHtml = p.originalPrice
      ? `${formatPrice(p.price)}<span class="original">${formatPrice(p.originalPrice)}</span>`
      : formatPrice(p.price);

    return `
      <div class="product-card" style="animation-delay: ${i * 0.1}s; cursor:pointer;" onclick="window.location.href='product.html?id=${p.id}'">
        <div class="product-card-img">
          <div class="product-card-img-inner" style="background: ${createGradient(p.colors)}"></div>
          ${badgeHtml}
        </div>
        <div class="product-card-body">
          <p class="product-card-category">${categoryLabels[p.category]}</p>
          <h3 class="product-card-name">${p.name}</h3>
          <p class="product-card-price">${priceHtml}</p>
        </div>
      </div>
    `;
  }).join('');

  // Cart sidebar handlers (reuse from app.js)
  const cartBtnEl = document.getElementById('cart-btn');
  const cartCloseEl = document.getElementById('cart-close');
  const cartOverlayEl = document.getElementById('cart-overlay');
  const cartSidebarEl = document.getElementById('cart-sidebar');

  if (cartBtnEl) {
    cartBtnEl.addEventListener('click', () => {
      cartSidebarEl.classList.add('active');
      cartOverlayEl.classList.add('active');
      document.body.style.overflow = 'hidden';
    });
  }

  if (cartCloseEl) {
    cartCloseEl.addEventListener('click', () => {
      cartSidebarEl.classList.remove('active');
      cartOverlayEl.classList.remove('active');
      document.body.style.overflow = '';
    });
  }

  if (cartOverlayEl) {
    cartOverlayEl.addEventListener('click', () => {
      cartSidebarEl.classList.remove('active');
      cartOverlayEl.classList.remove('active');
      document.body.style.overflow = '';
    });
  }

  // Hamburger
  const hamburgerEl = document.getElementById('hamburger');
  const navEl = document.getElementById('nav');
  if (hamburgerEl) {
    hamburgerEl.addEventListener('click', () => {
      hamburgerEl.classList.toggle('active');
      navEl.classList.toggle('active');
    });
  }
})();
