const app = getApp();
const api = require('../../utils/api.js');

Page({
  data: {
    userInfo: null,
    greeting: '早安',
    todayCalories: 0,
    calorieTarget: 2000,
    caloriePercent: 0,
    todayProtein: 0,
    todayFat: 0,
    todayCarbs: 0,
    streakDays: 0,
    weekWorkouts: 0,
    weekMinutes: 0,
    weekCalories: 0,
    bodyFatPct: null,
    bodyFatHasData: false,
    foodRecords: [],
    defaultAvatar: '',
    loading: true,
  },

  onLoad() {
    this.setData({ userInfo: app.globalData.userInfo, defaultAvatar: app.globalData.defaultAvatar || '/images/avatar_01.png' });
    this.updateGreeting();
  },

  updateGreeting() {
    const h = new Date().getHours();
    let g = '早安';
    if (h >= 6 && h < 9) g = '早安';
    else if (h >= 9 && h < 12) g = '上午好';
    else if (h >= 12 && h < 14) g = '中午好';
    else if (h >= 14 && h < 18) g = '下午好';
    else if (h >= 18 && h < 22) g = '晚上好';
    else g = '夜深了';
    this.setData({ greeting: g });
  },

  onShow() {
    var ui = app.globalData.userInfo || this.data.userInfo;
    this.setData({ userInfo: ui });
    this._updateBodyFat(ui);
    if (app.globalData._manualLogout) {
      this.setData({ loading: false });
      return;
    }
    if (app.globalData.isLoggedIn) {
      this.loadDashboard();
    } else {
      this.setData({ loading: false });
    }
  },

  onPullDownRefresh() {
    this.loadDashboard().then(() => wx.stopPullDownRefresh());
  },

  async loadDashboard() {
    this.setData({ loading: true });
    try {
      const foodRecords = await api.get('/api/food/records', {}, { silent: true });
      this.calculateNutrition(foodRecords || []);

      try {
        const streakData = await api.get('/api/fitness/streak', {}, { silent: true });
        this.setData({ streakDays: streakData.streak_days || 0 });
      } catch (e) { /* ignore */ }

      try {
        const weekStats = await api.get('/api/fitness/stats', { period: 'week' }, { silent: true });
        this.setData({
          weekWorkouts: (weekStats && weekStats.total_days) || 0,
          weekMinutes: (weekStats && weekStats.total_minutes) || 0,
          weekCalories: (weekStats && weekStats.total_calories) || 0,
        });
      } catch (e) { /* ignore */ }

      const ui = app.globalData.userInfo;
      if (ui && ui.daily_calorie_target) {
        this.setData({ calorieTarget: ui.daily_calorie_target });
      }
    } catch (err) {
      console.error('[Index] loadDashboard error:', err);
    } finally {
      this.setData({ loading: false });
    }
  },

  calculateNutrition(records) {
    let cal = 0, protein = 0, fat = 0, carbs = 0;
    for (const r of records) {
      cal += r.total_calories || 0;
      protein += r.total_protein_g || 0;
      fat += r.total_fat_g || 0;
      carbs += r.total_carbs_g || 0;
    }
    const pct = this.data.calorieTarget > 0
      ? Math.min(Math.round((cal / this.data.calorieTarget) * 100), 100) : 0;

    this.setData({
      foodRecords: records,
      todayCalories: cal,
      todayProtein: Math.round(protein),
      todayFat: Math.round(fat),
      todayCarbs: Math.round(carbs),
      caloriePercent: pct,
    });
  },

  _updateBodyFat(ui) {
    var hasData = !!(ui && ui.height_cm && ui.weight_kg && ui.exercise_details);
    var bf = (ui && ui.body_fat_pct != null) ? ui.body_fat_pct : null;
    this.setData({ bodyFatPct: bf, bodyFatHasData: hasData });
  },

  onBodyFatInfo() {
    wx.showModal({
      title: '体脂率计算方式',
      content: '基于 Deurenberg 公式（BMI + 年龄 + 性别）估算基础体脂率，再根据你填写的运动详情（卧推/深蹲/硬拉等力量数据）计算力量体重比进行调整。\n\n需要同时填写身高、体重和运动详情才能估算。\n\n数值仅供参考，精确测量请使用专业设备。',
      showCancel: false,
      confirmText: '知道了',
    });
  },

  goChat()    { wx.navigateTo({ url: '/pages/chat/chat' }); },
  goCamera()  { wx.navigateTo({ url: '/pages/camera/camera' }); },
  goRecipe()  { wx.switchTab({ url: '/pages/recipe/recipe' }); },
  goFitness() { wx.switchTab({ url: '/pages/fitness/fitness' }); },
  goProfile() { wx.switchTab({ url: '/pages/profile/profile' }); },
});
