const app = getApp();
const api = require('../../utils/api.js');

Page({
  data: {
    imagePath: '',
    analyzing: false,
    result: '',
  },

  takePhoto() {
    const that = this;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      success(res) {
        const filePath = res.tempFiles[0].tempFilePath;
        that.setData({ imagePath: filePath, result: '' });
      },
      fail(err) {
        console.error('[Camera] takePhoto fail:', err);
        wx.showToast({ title: '拍照失败', icon: 'none' });
      },
    });
  },

  choosePhoto() {
    const that = this;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album'],
      success(res) {
        const filePath = res.tempFiles[0].tempFilePath;
        that.setData({ imagePath: filePath, result: '' });
      },
      fail(err) {
        console.error('[Camera] choosePhoto fail:', err);
        wx.showToast({ title: '选择失败', icon: 'none' });
      },
    });
  },

  retake() {
    this.setData({ imagePath: '', result: '' });
  },

  async analyzeFood() {
    if (this.data.analyzing || !this.data.imagePath) return;
    this.setData({ analyzing: true });

    try {
      // Step 1: Upload image
      const uploadRes = await api.uploadFile(this.data.imagePath);
      const imageUrl = uploadRes.image_url;

      // Step 2: Send to agent for food recognition
      const chatRes = await api.post('/api/chat', {
        message: '请帮我识别这张食物图片，并分析热量和营养',
        image_url: imageUrl,
      }, { showLoading: false });

      this.setData({
        result: chatRes.reply || '识别完成，请点击咨询了解更多',
        analyzing: false,
      });
    } catch (err) {
      console.error('[Camera] analyzeFood error:', err);
      wx.showToast({ title: '分析失败，请重试', icon: 'none' });
      this.setData({ analyzing: false });
    }
  },

  goChat() {
    wx.navigateTo({ url: '/pages/chat/chat' });
  },
});
