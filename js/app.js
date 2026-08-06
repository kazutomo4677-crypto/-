/* ============================================
   祭彩 -MATSURI SAI- EC Site JavaScript
   ============================================ */

// --- Product Data ---
const products = [
  {
    id: 1,
    name: '祝彩キャンバスプリント A2',
    category: 'print',
    price: 12800,
    originalPrice: null,
    badge: 'new',
    colors: ['#e8443a', '#d4a017', '#0d9488'],
    description: '春の祭りをテーマにした鮮やかなキャンバスプリント。A2サイズ。'
  },
  {
    id: 2,
    name: '祭彩オーバーサイズTシャツ',
    category: 'apparel',
    price: 6980,
    originalPrice: null,
    badge: null,
    colors: ['#1a1a2e', '#e8443a', '#d4a017'],
    description: '祭彩アートをあしらったオーバーサイズTシャツ。'
  },
  {
    id: 3,
    name: '花吹雪アクリルスタンド',
    category: 'accessory',
    price: 3280,
    originalPrice: null,
    badge: 'new',
    colors: ['#ff6b6b', '#f5d76e', '#5eead4'],
    description: '華やかな花吹雪をモチーフにしたアクリルスタンド。'
  },
  {
    id: 4,
    name: '紅彩イラストレーション 原画',
    category: 'illustration',
    price: 88000,
    originalPrice: null,
    badge: 'limited',
    colors: ['#e8443a', '#5b21b6', '#d4a017'],
    description: '深紅をベースにした一点物のオリジナルイラストレーション。'
  },
  {
    id: 5,
    name: '金箔アートポスター B3',
    category: 'print',
    price: 4980,
    originalPrice: 6500,
    badge: 'sale',
    colors: ['#d4a017', '#f5d76e', '#e8443a'],
    description: '金箔加工を施した高品質アートポスター。'
  },
  {
    id: 6,
    name: '翠風パーカー',
    category: 'apparel',
    price: 9800,
    originalPrice: null,
    badge: null,
    colors: ['#0d9488', '#5eead4', '#1a1a2e'],
    description: 'ティールグリーンを基調としたアートパーカー。'
  },
  {
    id: 7,
    name: 'カーニバルピンバッジセット',
    category: 'accessory',
    price: 2480,
    originalPrice: null,
    badge: 'new',
    colors: ['#e8443a', '#d4a017', '#0d9488', '#5b21b6'],
    description: '4種セットのカラフルなピンバッジ。'
  },
  {
    id: 8,
    name: '彩雲デジタルイラスト',
    category: 'illustration',
    price: 45000,
    originalPrice: null,
    badge: null,
    colors: ['#a78bfa', '#ff6b6b', '#5eead4'],
    description: '彩雲をテーマにしたデジタルイラスト作品。'
  },
  {
    id: 9,
    name: '祭彩トートバッグ',
    category: 'apparel',
    price: 3980,
    originalPrice: 4980,
    badge: 'sale',
    colors: ['#fef7ed', '#e8443a', '#d4a017'],
    description: '大容量のキャンバストートバッグ。'
  },
  {
    id: 10,
    name: '紙吹雪キーホルダー',
    category: 'accessory',
    price: 1580,
    originalPrice: null,
    badge: null,
    colors: ['#ff6b6b', '#f5d76e', '#5eead4', '#a78bfa'],
    description: 'コンフェッティモチーフのレジンキーホルダー。'
  },
  {
    id: 11,
    name: '黎明 -REIMEI- プリント A3',
    category: 'print',
    price: 7800,
    originalPrice: null,
    badge: null,
    colors: ['#5b21b6', '#e8443a', '#d4a017'],
    description: '夜明けの祭りをテーマにしたA3プリント。'
  },
  {
    id: 12,
    name: '祭彩スマホケース',
    category: 'accessory',
    price: 3480,
    originalPrice: null,
    badge: 'new',
    colors: ['#e8443a', '#d4a017', '#0d9488'],
    description: '祭彩アートのスマートフォンケース。対応機種多数。'
  }
];

// --- Cart State ---
let cart = [];

// --- DOM Elements ---
const header = document.getElementById('header');
const hamburger = document.getElementById('hamburger');
const nav = document.getElementById('nav');
const searchBtn = document.getElementById('search-btn');
const searchModal = document.getElementById('search-modal');
const searchInput = document.getElementById('search-input');
const searchClose = document.getElementById('search-close');
const searchResults = document.getElementById('search-results');
const cartBtn = document.getElementById('cart-btn');
const cartCount = document.getElementById('cart-count');
const cartSidebar = document.getElementById('cart-sidebar');
const cartOverlay = document.getElementById('cart-overlay');
const cartClose = document.getElementById('cart-close');
const cartItems = document.getElementById('cart-items');
const cartEmpty = document.getElementById('cart-empty');
const cartFooter = document.getElementById('cart-footer');
const cartTotalPrice = document.getElementById('cart-total-price');
const productsGrid = document.getElementById('products-grid');
const filterBtns = document.querySelectorAll('.filter-btn');

// --- Plugin event helper ---
function emitPluginEvent(event, data) {
  if (window.MatsuriPlugins) window.MatsuriPlugins.emit(event, data);
}

// --- Helper: Format price ---
function formatPrice(price) {
  return '¥' + price.toLocaleString();
}

// --- Helper: Create gradient from colors ---
function createGradient(colors) {
  if (colors.length === 1) return colors[0];
  return `linear-gradient(135deg, ${colors.join(', ')})`;
}

// --- Render Products ---
function renderProducts(category = 'all') {
  if (!productsGrid) return;

  const filtered = category === 'all'
    ? products
    : products.filter(p => p.category === category);

  productsGrid.innerHTML = filtered.map((product, i) => {
    const badgeHtml = product.badge
      ? `<span class="product-card-badge ${product.badge}">${
          product.badge === 'new' ? 'NEW' :
          product.badge === 'limited' ? 'LIMITED' :
          product.badge === 'sale' ? 'SALE' : ''
        }</span>`
      : '';

    const priceHtml = product.originalPrice
      ? `${formatPrice(product.price)}<span class="original">${formatPrice(product.originalPrice)}</span>`
      : formatPrice(product.price);

    const categoryLabel = {
      illustration: 'ILLUSTRATION',
      apparel: 'APPAREL',
      accessory: 'ACCESSORY',
      print: 'PRINT'
    }[product.category];

    return `
      <div class="product-card" data-id="${product.id}" style="animation-delay: ${i * 0.08}s">
        <div class="product-card-img">
          <div class="product-card-img-inner" style="background: ${createGradient(product.colors)}"></div>
          ${badgeHtml}
          <button class="product-card-quick" onclick="addToCart(${product.id})" title="カートに追加">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 5v14M5 12h14"/>
            </svg>
          </button>
        </div>
        <div class="product-card-body">
          <p class="product-card-category">${categoryLabel}</p>
          <h3 class="product-card-name">${product.name}</h3>
          <p class="product-card-price">${priceHtml}</p>
        </div>
      </div>
    `;
  }).join('');

  // Add click handlers for navigation to product detail
  document.querySelectorAll('.product-card').forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('.product-card-quick')) return;
      const id = card.dataset.id;
      window.location.href = `product.html?id=${id}`;
    });
  });

  emitPluginEvent('products:render', { category, products: filtered });
}

// --- Filter ---
filterBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    filterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const category = btn.dataset.category;
    renderProducts(category);
    emitPluginEvent('filter:change', { category });
  });
});

// --- Cart Functions ---
function addToCart(productId) {
  const product = products.find(p => p.id === productId);
  if (!product) return;

  const existing = cart.find(item => item.id === productId);
  if (existing) {
    existing.qty += 1;
  } else {
    cart.push({ ...product, qty: 1 });
  }

  updateCart();
  showToast(`${product.name} をカートに追加しました`);
  createConfetti(8);
  emitPluginEvent('cart:add', { product, cart: cart.slice() });
}

function removeFromCart(productId) {
  cart = cart.filter(item => item.id !== productId);
  updateCart();
  emitPluginEvent('cart:remove', { productId, cart: cart.slice() });
}

function updateQty(productId, delta) {
  const item = cart.find(i => i.id === productId);
  if (!item) return;
  item.qty += delta;
  if (item.qty <= 0) {
    removeFromCart(productId);
    return;
  }
  updateCart();
}

function updateCart() {
  const totalItems = cart.reduce((sum, item) => sum + item.qty, 0);
  const totalPrice = cart.reduce((sum, item) => sum + item.price * item.qty, 0);

  // Update count badge
  cartCount.textContent = totalItems;
  if (totalItems > 0) {
    cartCount.classList.add('show');
  } else {
    cartCount.classList.remove('show');
  }

  // Update cart sidebar
  if (cart.length === 0) {
    cartEmpty.style.display = 'flex';
    cartFooter.style.display = 'none';
    // Remove only cart-item elements, keep cart-empty
    cartItems.querySelectorAll('.cart-item').forEach(el => el.remove());
  } else {
    cartEmpty.style.display = 'none';
    cartFooter.style.display = 'block';

    // Remove existing cart-item elements
    cartItems.querySelectorAll('.cart-item').forEach(el => el.remove());

    cart.forEach(item => {
      const el = document.createElement('div');
      el.className = 'cart-item';
      el.innerHTML = `
        <div class="cart-item-img" style="background: ${createGradient(item.colors)}"></div>
        <div class="cart-item-info">
          <p class="cart-item-name">${item.name}</p>
          <p class="cart-item-price">${formatPrice(item.price)}</p>
          <div class="cart-item-qty">
            <button class="qty-btn" onclick="updateQty(${item.id}, -1)">−</button>
            <span>${item.qty}</span>
            <button class="qty-btn" onclick="updateQty(${item.id}, 1)">+</button>
          </div>
        </div>
        <button class="cart-item-remove" onclick="removeFromCart(${item.id})">&times;</button>
      `;
      cartItems.appendChild(el);
    });

    cartTotalPrice.textContent = formatPrice(totalPrice);
  }

  // Save to localStorage
  localStorage.setItem('matsuri-cart', JSON.stringify(cart));
  emitPluginEvent('cart:update', { cart: cart.slice(), totalItems, totalPrice });
}

// Load cart from localStorage
function loadCart() {
  const saved = localStorage.getItem('matsuri-cart');
  if (saved) {
    try {
      cart = JSON.parse(saved);
      updateCart();
    } catch (e) {
      cart = [];
    }
  }
}

// --- Cart Sidebar Toggle ---
function openCart() {
  cartSidebar.classList.add('active');
  cartOverlay.classList.add('active');
  document.body.style.overflow = 'hidden';
  emitPluginEvent('cart:open', {});
}

function closeCart() {
  cartSidebar.classList.remove('active');
  cartOverlay.classList.remove('active');
  document.body.style.overflow = '';
  emitPluginEvent('cart:close', {});
}

cartBtn.addEventListener('click', openCart);
cartClose.addEventListener('click', closeCart);
cartOverlay.addEventListener('click', closeCart);

// --- Search ---
searchBtn.addEventListener('click', () => {
  searchModal.classList.add('active');
  setTimeout(() => searchInput.focus(), 300);
});

searchClose.addEventListener('click', () => {
  searchModal.classList.remove('active');
  searchInput.value = '';
  searchResults.innerHTML = '';
});

searchInput.addEventListener('input', (e) => {
  const query = e.target.value.toLowerCase().trim();
  if (!query) {
    searchResults.innerHTML = '';
    return;
  }

  const results = products.filter(p =>
    p.name.toLowerCase().includes(query) ||
    p.description.toLowerCase().includes(query) ||
    p.category.toLowerCase().includes(query)
  );

  searchResults.innerHTML = results.map(p => `
    <div class="search-result-item" onclick="window.location.href='product.html?id=${p.id}'">
      <div class="search-result-thumb" style="background: ${createGradient(p.colors)}"></div>
      <div class="search-result-info">
        <h4>${p.name}</h4>
        <p>${formatPrice(p.price)}</p>
      </div>
    </div>
  `).join('');

  if (results.length === 0) {
    searchResults.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:24px;">検索結果が見つかりません</p>';
  }

  emitPluginEvent('search:query', { query, results });
});

// --- Hamburger Menu ---
hamburger.addEventListener('click', () => {
  hamburger.classList.toggle('active');
  nav.classList.toggle('active');
});

// Close mobile menu on link click
nav.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', () => {
    hamburger.classList.remove('active');
    nav.classList.remove('active');
  });
});

// --- Header Scroll ---
let lastScroll = 0;
window.addEventListener('scroll', () => {
  const scrollY = window.scrollY;

  if (scrollY > 50) {
    header.classList.add('scrolled');
  } else {
    header.classList.remove('scrolled');
  }

  lastScroll = scrollY;
});

// --- Active nav link on scroll ---
const sections = document.querySelectorAll('section[id]');
window.addEventListener('scroll', () => {
  const scrollY = window.scrollY + 200;
  sections.forEach(section => {
    const top = section.offsetTop;
    const height = section.offsetHeight;
    const id = section.getAttribute('id');
    const link = document.querySelector(`.nav-link[href="#${id}"]`);
    if (link) {
      if (scrollY >= top && scrollY < top + height) {
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
      }
    }
  });
});

// --- Scroll Animations (Intersection Observer) ---
const observerOptions = {
  threshold: 0.1,
  rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
}, observerOptions);

document.querySelectorAll('.about-card').forEach(card => {
  observer.observe(card);
});

// --- Confetti ---
function createConfetti(count) {
  const container = document.getElementById('confetti-container');
  const colors = ['#e8443a', '#d4a017', '#0d9488', '#5b21b6', '#ff6b6b', '#f5d76e', '#5eead4', '#a78bfa'];
  const shapes = ['square', 'circle'];

  for (let i = 0; i < count; i++) {
    const confetti = document.createElement('div');
    confetti.className = 'confetti';
    const color = colors[Math.floor(Math.random() * colors.length)];
    const shape = shapes[Math.floor(Math.random() * shapes.length)];

    confetti.style.left = Math.random() * 100 + '%';
    confetti.style.top = '-10px';
    confetti.style.background = color;
    confetti.style.borderRadius = shape === 'circle' ? '50%' : '2px';
    confetti.style.width = (Math.random() * 8 + 6) + 'px';
    confetti.style.height = (Math.random() * 8 + 6) + 'px';
    confetti.style.animationDuration = (Math.random() * 2 + 2) + 's';
    confetti.style.animationDelay = (Math.random() * 0.5) + 's';

    container.appendChild(confetti);

    setTimeout(() => confetti.remove(), 4000);
  }
}

// --- Toast Notification ---
let toastTimeout;
function showToast(message) {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    document.body.appendChild(toast);
  }

  toast.innerHTML = `<span class="toast-icon">&#127881;</span>${message}`;

  clearTimeout(toastTimeout);
  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  toastTimeout = setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

// --- Newsletter Form ---
const newsletterForm = document.getElementById('newsletter-form');
if (newsletterForm) {
  newsletterForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const email = newsletterForm.querySelector('input[type="email"]').value;
    showToast('ご登録ありがとうございます！');
    e.target.reset();
    createConfetti(15);
    emitPluginEvent('form:newsletter', { email });
  });
}

// --- Contact Form ---
const contactForm = document.getElementById('contact-form');
if (contactForm) {
  contactForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const data = {
      name:    document.getElementById('name').value,
      email:   document.getElementById('email').value,
      subject: document.getElementById('subject').value,
      message: document.getElementById('message').value,
    };
    showToast('お問い合わせを送信しました');
    e.target.reset();
    emitPluginEvent('form:contact', { data });
  });
}

// --- Smooth scroll for anchor links ---
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', (e) => {
    e.preventDefault();
    const target = document.querySelector(anchor.getAttribute('href'));
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// --- Initial confetti burst on page load ---
window.addEventListener('load', () => {
  setTimeout(() => createConfetti(20), 500);
});

// --- Initialize ---
document.addEventListener('DOMContentLoaded', () => {
  renderProducts();
  loadCart();
  emitPluginEvent('app:ready', { page: document.title });
});

// --- Public API for plugins ---
window.MatsuriApp = {
  getCart:    () => cart.slice(),
  getProducts:(category) => {
    if (!category || category === 'all') return products.slice();
    return products.filter(p => p.category === category);
  },
  addToCart,
  openCart,
  closeCart,
  showToast,
};
