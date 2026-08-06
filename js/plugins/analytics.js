/* ============================================
   Analytics Plugin for 祭彩
   Tracks page views, cart events, and interactions.
   Results are accessible via window.MatsuriAnalytics.
   ============================================ */

var AnalyticsPlugin = {
  name: 'matsuri-analytics',
  version: '1.0.0',
  description: 'Tracks page views, cart events, searches, and form submissions',

  _events: [],
  _sessionStart: null,

  install: function (api) {
    var self = this;
    self._sessionStart = Date.now();

    api.on('app:ready',        function (d) { self._track('page_view',            { page: location.pathname, title: d && d.page || document.title }); });
    api.on('cart:add',         function (d) { self._track('add_to_cart',          { id: d.product.id, name: d.product.name, price: d.product.price }); });
    api.on('cart:remove',      function (d) { self._track('remove_from_cart',     { id: d.productId }); });
    api.on('cart:update',      function (d) { self._track('cart_update',          { totalItems: d.totalItems, totalPrice: d.totalPrice }); });
    api.on('cart:open',        function ()  { self._track('cart_open',            {}); });
    api.on('search:query',     function (d) { if (d.query) self._track('search',  { query: d.query, hits: d.results.length }); });
    api.on('filter:change',    function (d) { self._track('filter_change',        { category: d.category }); });
    api.on('products:render',  function (d) { self._track('products_view',        { category: d.category, count: d.products.length }); });
    api.on('form:newsletter',  function ()  { self._track('newsletter_signup',    {}); });
    api.on('form:contact',     function (d) { self._track('contact_submit',       { subject: d.data.subject }); });
    api.on('wishlist:change',  function (d) { self._track('wishlist_change',      { count: d.wishlist.length }); });

    window.MatsuriAnalytics = {
      getEvents:          function () { return self._events.slice(); },
      getSummary:         function () { return self._getSummary(); },
      getSessionDuration: function () { return ((Date.now() - self._sessionStart) / 1000).toFixed(1) + 's'; },
      printReport:        function () { self._printReport(); },
    };
  },

  _track: function (type, payload) {
    var entry = { type: type, payload: payload, t: new Date().toISOString() };
    this._events.push(entry);
    console.log('[MatsuriAnalytics]', type, payload);
  },

  _getSummary: function () {
    var counts = {};
    this._events.forEach(function (e) { counts[e.type] = (counts[e.type] || 0) + 1; });
    return counts;
  },

  _printReport: function () {
    console.group('[MatsuriAnalytics] Session Report');
    console.log('Duration :', window.MatsuriAnalytics.getSessionDuration());
    console.log('Events   :', this._events.length);
    console.table(this._getSummary());
    console.groupEnd();
  },
};

if (window.MatsuriPlugins) {
  MatsuriPlugins.use(AnalyticsPlugin);
}
