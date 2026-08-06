/* ============================================
   祭彩 Plugin Manager
   ============================================
   Usage:
     MatsuriPlugins.use(MyPlugin)   // register & install
     MatsuriPlugins.unuse('name')   // uninstall
     MatsuriPlugins.get('name')     // retrieve instance
     MatsuriPlugins.list()          // [{name, version, description}]

   Plugin shape:
     {
       name: 'my-plugin',           // required, unique
       version: '1.0.0',            // required
       description: '...',          // optional
       install(api) { ... },        // required
       uninstall() { ... },         // optional
     }

   Plugin API (passed to install):
     api.on(event, handler)
     api.off(event, handler)
     api.emit(event, data)
     api.getCart()
     api.getProducts(category?)
     api.addToCart(productId)
     api.showToast(message)
     api.openCart()
     api.closeCart()

   App events emitted:
     app:ready        { page }
     cart:add         { product, cart }
     cart:remove      { productId, cart }
     cart:update      { cart, totalItems, totalPrice }
     cart:open        {}
     cart:close       {}
     products:render  { category, products }
     filter:change    { category }
     search:query     { query, results }
     form:newsletter  { email }
     form:contact     { data }
   ============================================ */

(function (global) {
  'use strict';

  function EventBus() {
    this._h = {};
  }

  EventBus.prototype.on = function (event, handler) {
    if (typeof handler !== 'function') return;
    (this._h[event] = this._h[event] || []).push(handler);
  };

  EventBus.prototype.off = function (event, handler) {
    if (!this._h[event]) return;
    this._h[event] = this._h[event].filter(function (h) { return h !== handler; });
  };

  EventBus.prototype.emit = function (event, data) {
    (this._h[event] || []).slice().forEach(function (h) {
      try { h(data); } catch (err) {
        console.error('[MatsuriPlugins] Error in "' + event + '" handler:', err);
      }
    });
  };

  function PluginManager() {
    this._bus = new EventBus();
    this._plugins = {};
  }

  PluginManager.prototype.use = function (plugin) {
    if (!plugin || typeof plugin !== 'object') {
      throw new Error('[MatsuriPlugins] Plugin must be a plain object');
    }
    if (!plugin.name || typeof plugin.name !== 'string') {
      throw new Error('[MatsuriPlugins] Plugin must have a name string');
    }
    if (!plugin.version || typeof plugin.version !== 'string') {
      throw new Error('[MatsuriPlugins] Plugin "' + plugin.name + '" must have a version string');
    }
    if (typeof plugin.install !== 'function') {
      throw new Error('[MatsuriPlugins] Plugin "' + plugin.name + '" must export install(api)');
    }
    if (this._plugins[plugin.name]) {
      console.warn('[MatsuriPlugins] "' + plugin.name + '" is already registered — skipping');
      return this;
    }

    var bus = this._bus;
    var api = {
      on:         function (e, h)  { bus.on(e, h); },
      off:        function (e, h)  { bus.off(e, h); },
      emit:       function (e, d)  { bus.emit(e, d); },
      getCart:    function ()      { return global.MatsuriApp ? global.MatsuriApp.getCart()      : []; },
      getProducts:function (cat)   { return global.MatsuriApp ? global.MatsuriApp.getProducts(cat) : []; },
      addToCart:  function (id)    { global.MatsuriApp && global.MatsuriApp.addToCart(id); },
      showToast:  function (msg)   { global.MatsuriApp && global.MatsuriApp.showToast(msg); },
      openCart:   function ()      { global.MatsuriApp && global.MatsuriApp.openCart(); },
      closeCart:  function ()      { global.MatsuriApp && global.MatsuriApp.closeCart(); },
    };

    try {
      plugin.install(api);
      this._plugins[plugin.name] = plugin;
      console.info('[MatsuriPlugins] "' + plugin.name + '" v' + plugin.version + ' installed');
    } catch (err) {
      console.error('[MatsuriPlugins] Failed to install "' + plugin.name + '":', err);
    }
    return this;
  };

  PluginManager.prototype.unuse = function (name) {
    var plugin = this._plugins[name];
    if (!plugin) {
      console.warn('[MatsuriPlugins] "' + name + '" is not registered');
      return this;
    }
    if (typeof plugin.uninstall === 'function') {
      try { plugin.uninstall(); } catch (err) {
        console.error('[MatsuriPlugins] Error in uninstall of "' + name + '":', err);
      }
    }
    delete this._plugins[name];
    console.info('[MatsuriPlugins] "' + name + '" uninstalled');
    return this;
  };

  PluginManager.prototype.get = function (name) {
    return this._plugins[name] || null;
  };

  PluginManager.prototype.list = function () {
    return Object.keys(this._plugins).map(function (key) {
      var p = this._plugins[key];
      return { name: p.name, version: p.version, description: p.description || '' };
    }, this);
  };

  PluginManager.prototype.emit = function (event, data) {
    this._bus.emit(event, data);
  };

  global.MatsuriPlugins = new PluginManager();

}(window));
