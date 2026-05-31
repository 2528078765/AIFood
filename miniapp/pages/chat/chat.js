const app = getApp();
const api = require('../../utils/api.js');

Page({
  data: {
    messages: [],
    inputText: '',
    typing: false,
    scrollToView: '',
    loading: false,
  },

  onLoad() {
    this.loadHistory();
  },

  async loadHistory() {
    try {
      const history = await api.get('/api/chat/history', {}, { silent: true });
      if (history && history.length > 0) {
        const msgs = history.map(item => ({
          role: item.role,
          content: item.message,
          time: item.created_at ? item.created_at.slice(11, 16) : '',
        }));
        this.setData({ messages: msgs }, () => this.scrollToBottom());
      }
    } catch (e) {
      console.log('[Chat] History load skipped:', e);
    }
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  sendMessage() {
    const text = this.data.inputText.trim();
    if (!text || this.data.typing) return;

    const now = new Date();
    const time = now.getHours().toString().padStart(2, '0') + ':' +
                 now.getMinutes().toString().padStart(2, '0');

    const userMsg = { role: 'user', content: text, time };
    const messages = [...this.data.messages, userMsg];
    this.setData({
      messages,
      inputText: '',
      typing: true,
    }, () => this.scrollToBottom());

    // Call streaming API for real-time response
    this.streamChat(text);
  },

  sendQuick(e) {
    const text = e.currentTarget.dataset.text;
    this.setData({ inputText: text }, () => this.sendMessage());
  },

  streamChat(message) {
    const that = this;
    const token = app.getToken();
    const baseUrl = app.globalData.baseUrl;

    // Use non-streaming endpoint for simplicity; SSE streaming requires more setup
    api.post('/api/chat', { message }, { showLoading: false })
      .then(data => {
        const reply = data.reply || '';
        const now = new Date();
        const time = now.getHours().toString().padStart(2, '0') + ':' +
                     now.getMinutes().toString().padStart(2, '0');

        const aiMsg = { role: 'assistant', content: reply, time };
        const messages = [...that.data.messages, aiMsg];
        that.setData({ messages, typing: false }, () => that.scrollToBottom());
      })
      .catch(err => {
        console.error('[Chat] Error:', err);
        that.setData({ typing: false });
      });
  },

  scrollToBottom() {
    const len = this.data.messages.length;
    this.setData({ scrollToView: len > 0 ? 'msg-bottom' : '' });
  },
});
