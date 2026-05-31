const api = require('../../utils/api.js');

Page({
  data: {
    records: [],
    startDate: '',
    endDate: '',
    loading: true,
  },

  onLoad() {
    const now = new Date();
    const weekAgo = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    this.setData({
      startDate: this.formatDate(weekAgo),
      endDate: this.formatDate(now),
    });
  },

  onShow() {
    this.loadRecords();
  },

  formatDate(d) {
    const y = d.getFullYear();
    const m = (d.getMonth() + 1).toString().padStart(2, '0');
    const day = d.getDate().toString().padStart(2, '0');
    return y + '-' + m + '-' + day;
  },

  async loadRecords() {
    this.setData({ loading: true });
    try {
      const records = await api.get('/api/fitness/records', {
        start_date: this.data.startDate,
        end_date: this.data.endDate,
      }, { silent: true });
      this.setData({ records: records || [], loading: false });
    } catch (err) {
      console.error('[FitnessLog] load error:', err);
      this.setData({ loading: false });
    }
  },

  onStartDateChange(e) {
    this.setData({ startDate: e.detail.value }, () => this.loadRecords());
  },

  onEndDateChange(e) {
    this.setData({ endDate: e.detail.value }, () => this.loadRecords());
  },
});
