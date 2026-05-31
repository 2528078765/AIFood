const api = require('../../utils/api.js');

Page({
  data: {
    keys: null,
    providers: [],
    token: { has_personal_keys: false, free_tokens_remaining: 0, free_tokens_total: 1000000, free_tokens_used: 0 },
    tokenRemainingDisplay: '100 万',
    tokenTotalDisplay: 100,
    showTutorial: false,
    formData: {},
    showKey: {},
    saving: false,
    testingProvider: '',
    testResults: {},
  },

  onShow: function () {
    this.loadData();
  },

  loadData: async function () {
    const that = this;
    that.setData({ loading: true });
    try {
      const data = await api.get('/api/settings/apikeys', {}, { silent: true });
      const t = data.token || { has_personal_keys: false, free_tokens_remaining: 0, free_tokens_total: 1000000 };
      const rem = t.free_tokens_remaining;
      const totalWan = Math.round(t.free_tokens_total / 10000);
      const remDisplay = rem >= 10000 ? (rem / 10000).toFixed(1) + ' 万' : String(rem);

      that.setData({
        loading: false,
        keys: data.keys || {},
        providers: data.providers || [],
        token: t,
        tokenRemainingDisplay: remDisplay,
        tokenTotalDisplay: totalWan,
      });
    } catch (err) {
      that.setData({ loading: false });
      console.error('Load settings error:', err);
    }
  },

  toggleTutorial: function () {
    this.setData({ showTutorial: !this.data.showTutorial });
  },

  openUrl: function (e) {
    const url = e.currentTarget.dataset.url;
    wx.setClipboardData({ data: url });
    wx.showToast({ title: '链接已复制，请到浏览器打开', icon: 'none', duration: 2000 });
  },

  onKeyInput: function (e) {
    const provider = e.currentTarget.dataset.provider;
    const key = provider + '_api_key';
    const formData = this.data.formData || {};
    formData[key] = e.detail.value;
    this.setData({ formData: formData });
  },

  onBaseUrlInput: function (e) {
    const provider = e.currentTarget.dataset.provider;
    const key = provider + '_base_url';
    const formData = this.data.formData || {};
    formData[key] = e.detail.value;
    this.setData({ formData: formData });
  },

  toggleKeyVis: function (e) {
    const provider = e.currentTarget.dataset.provider;
    const showKey = this.data.showKey || {};
    showKey[provider] = !showKey[provider];
    this.setData({ showKey: showKey });
  },

  testConnection: async function (e) {
    const that = this;
    const provider = e.currentTarget.dataset.provider;
    that.setData({ testingProvider: provider });
    let testResults = that.data.testResults || {};

    try {
      const result = await api.post(
        '/api/settings/test-connection',
        {},
        {
          silent: true,
          _query: { provider: provider }  // will be ignored by POST, use GET instead
        }
      );
      // Actually use GET
      const resp = await api.get('/api/settings/test-connection', { provider: provider }, { silent: true });
      testResults[provider] = {
        connected: resp.connected,
        error: resp.error || null,
      };
      that.setData({ testingProvider: '', testResults: testResults });

      if (resp.connected) {
        wx.showToast({ title: provider + ' 连接成功', icon: 'success' });
      } else {
        wx.showToast({ title: resp.error || '连接失败', icon: 'none' });
      }
    } catch (err) {
      testResults[provider] = { connected: false, error: err.message || '连接测试失败' };
      that.setData({ testingProvider: '', testResults: testResults });
    }
  },

  saveAllKeys: async function () {
    const that = this;
    if (that.data.saving) return;

    const payload = {};
    const fd = that.data.formData || {};

    if (fd.deepseek_api_key && fd.deepseek_api_key.trim()) payload.deepseek_api_key = fd.deepseek_api_key.trim();
    if (fd.deepseek_base_url && fd.deepseek_base_url.trim()) payload.deepseek_base_url = fd.deepseek_base_url.trim();
    if (fd.qwen_api_key && fd.qwen_api_key.trim()) payload.qwen_api_key = fd.qwen_api_key.trim();
    if (fd.qwen_base_url && fd.qwen_base_url.trim()) payload.qwen_base_url = fd.qwen_base_url.trim();
    if (fd.tavily_api_key && fd.tavily_api_key.trim()) payload.tavily_api_key = fd.tavily_api_key.trim();

    if (Object.keys(payload).length === 0) {
      wx.showToast({ title: '请至少配置一个 API Key', icon: 'none' });
      return;
    }

    that.setData({ saving: true });
    try {
      const result = await api.put('/api/settings/apikeys', payload);
      wx.showToast({ title: '保存成功', icon: 'success' });
      that.setData({
        saving: false,
        keys: result || {},
        formData: {},
        showKey: {},
      });
      that.loadData(); // reload to get fresh trial status
    } catch (err) {
      that.setData({ saving: false });
      wx.showToast({ title: err.message || '保存失败', icon: 'none' });
    }
  },

  deleteKey: function (e) {
    const that = this;
    const provider = e.currentTarget.dataset.provider;

    wx.showModal({
      title: '确认删除',
      content: '确定要删除 ' + provider + ' 的密钥吗？',
      success: async function (res) {
        if (res.confirm) {
          try {
            await api.del('/api/settings/apikeys?provider=' + encodeURIComponent(provider), {}, { silent: true });
            wx.showToast({ title: '已删除', icon: 'success' });
            that.loadData();
          } catch (err) {
            wx.showToast({ title: '删除失败', icon: 'none' });
          }
        }
      },
    });
  },

  onRetry: function () {
    this.loadData();
  },

  onPullDownRefresh: async function () {
    await this.loadData();
    wx.stopPullDownRefresh();
  },
});
