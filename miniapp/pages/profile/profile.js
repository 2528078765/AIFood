const app = getApp();
const api = require('../../utils/api.js');

const ALLERGY_OPTIONS = ['花生', '牛奶', '海鲜', '鸡蛋', '麸质', '大豆', '坚果', '芝麻'];
const RESTRICTION_OPTIONS = [
  { key: 'no_pork', label: '不吃猪肉' },
  { key: 'no_beef', label: '不吃牛肉' },
  { key: 'no_lamb', label: '不吃羊肉' },
  { key: 'no_cilantro', label: '不吃香菜' },
  { key: 'no_spicy', label: '不吃辣' },
  { key: 'no_garlic', label: '不吃葱蒜' },
  { key: 'no_organ', label: '不吃内脏' },
  { key: 'vegetarian', label: '素食' },
  { key: 'vegan', label: '纯素' },
];

Page({
  data: {
    userInfo: {},
    defaultAvatar: '',
    displayName: '食光用户',
    editMode: false,
    apiKeyStatus: '',
    bodyFatPct: null,
    bodyFatHasData: false,
    genderOptions: ['未设置', '男', '女'],
    goalOptions: ['未设置', '减脂', '增肌', '维持'],
    allergyOptions: ALLERGY_OPTIONS,
    restrictionOptions: RESTRICTION_OPTIONS,
    editForm: {
      genderIndex: 0,
      birthday: '',
      height_cm: '',
      weight_kg: '',
      exercise_details: '',
      goalIndex: 0,
      allergies: [],
      restrictions: [],
    },
  },

  onShow() {
    if (!this.data.defaultAvatar || this.data.defaultAvatar === '') {
      this.setData({ defaultAvatar: app.globalData.defaultAvatar || '/images/avatar_01.png' });
    }
    if (app.globalData._manualLogout || !app.globalData.isLoggedIn) {
      this.setData({ userInfo: {}, apiKeyStatus: '' });
      return;
    }
    this.loadProfile();
    this.checkApiKeys();
  },

  async loadProfile() {
    try {
      const profile = await api.get('/api/auth/profile', {}, { silent: true });
      const REST_MAP = { no_pork: '不吃猪肉', no_beef: '不吃牛肉', no_lamb: '不吃羊肉', no_cilantro: '不吃香菜', no_spicy: '不吃辣', no_garlic: '不吃葱蒜', no_organ: '不吃内脏', vegetarian: '素食', vegan: '纯素' };
      if (profile && profile.dietary_restrictions) {
        profile.dietary_restrictions_display = profile.dietary_restrictions.map(function(k) { return REST_MAP[k] || k; }).join('、');
      }
      if (profile && profile.allergies) {
        profile.allergies_display = profile.allergies.join('、');
      }
      var hasData = !!(profile && profile.height_cm && profile.weight_kg && profile.exercise_details);
      var bf = (profile && profile.body_fat && profile.body_fat.body_fat_pct != null) ? profile.body_fat.body_fat_pct : null;
      // Preserve body_fat from save if GET didn't return it
      if (!bf && app.globalData._savedBodyFat != null) {
        bf = app.globalData._savedBodyFat;
      }
      const displayName = (profile && profile.nickname) || 'aifood_user_' + ((profile && profile.id) || '').substring(0, 5);
      this.setData({ userInfo: profile || {}, displayName: displayName, bodyFatPct: bf, bodyFatHasData: hasData });
      app.globalData.userInfo = profile;
      if (bf != null) app.globalData.userInfo.body_fat_pct = bf;
      wx.setStorageSync('userInfo', profile);
    } catch (err) {
      this.setData({ userInfo: {} });
    }
  },

  async checkApiKeys() {
    try {
      const keys = await api.get('/api/settings/apikeys', {}, { silent: true });
      if (keys) {
        const configured = [];
        if (keys.deepseek && keys.deepseek.configured) configured.push('DeepSeek');
        if (keys.qwen && keys.qwen.configured) configured.push('Qwen');
        if (keys.tavily && keys.tavily.configured) configured.push('Tavily');
        this.setData({
          apiKeyStatus: configured.length > 0 ? configured.length + ' 个已配置' : '未设置',
        });
      }
    } catch (e) {
      /* ignore silently */
    }
  },

  toggleEdit() {
    const ui = this.data.userInfo;
    const goalMap = { '': 0, 'lose_fat': 1, 'build_muscle': 2, 'maintain': 3 };
    const selAllergies = ui.allergies || [];
    const selRestrictions = ui.dietary_restrictions || [];

    const allergyTags = ALLERGY_OPTIONS.map(function(name) {
      return { name: name, selected: selAllergies.indexOf(name) >= 0 };
    });
    const restrictionTags = RESTRICTION_OPTIONS.map(function(item) {
      return { key: item.key, label: item.label, selected: selRestrictions.indexOf(item.key) >= 0 };
    });

    this.setData({
      editMode: !this.data.editMode,
      allergyTags: allergyTags,
      restrictionTags: restrictionTags,
      editAvatarUrl: '',
      editNickname: '',
      editForm: {
        genderIndex: ui.gender === 'male' ? 1 : ui.gender === 'female' ? 2 : 0,
        birthday: ui.birthday || '',
        height_cm: ui.height_cm ? String(ui.height_cm) : '',
        weight_kg: ui.weight_kg ? String(ui.weight_kg) : '',
        exercise_details: ui.exercise_details || '',
        goalIndex: goalMap[ui.fitness_goal || ''] || 0,
        allergies: selAllergies,
        restrictions: selRestrictions,
      },
    });
  },

  onGenderChange(e) { this.setData({ 'editForm.genderIndex': parseInt(e.detail.value) }); },
  onBirthdayChange(e) { this.setData({ 'editForm.birthday': e.detail.value }); },
  onGoalChange(e) { this.setData({ 'editForm.goalIndex': parseInt(e.detail.value) }); },
  onFieldChange(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ ['editForm.' + field]: e.detail.value });
  },

  onExerciseDetailInput(e) {
    this.setData({ 'editForm.exercise_details': e.detail.value });
  },

  onAllergyToggle(e) {
    const name = e.currentTarget.dataset.name;
    const allergies = [...this.data.editForm.allergies];
    const idx = allergies.indexOf(name);
    if (idx >= 0) { allergies.splice(idx, 1); }
    else { allergies.push(name); }
    const allergyTags = this.data.allergyTags.map(function(t) {
      return { name: t.name, selected: allergies.indexOf(t.name) >= 0 };
    });
    this.setData({ 'editForm.allergies': allergies, allergyTags: allergyTags });
  },

  onRestrictionToggle(e) {
    const key = e.currentTarget.dataset.key;
    const restrictions = [...this.data.editForm.restrictions];
    const idx = restrictions.indexOf(key);
    if (idx >= 0) { restrictions.splice(idx, 1); }
    else { restrictions.push(key); }
    const restrictionTags = this.data.restrictionTags.map(function(t) {
      return { key: t.key, label: t.label, selected: restrictions.indexOf(t.key) >= 0 };
    });
    this.setData({ 'editForm.restrictions': restrictions, restrictionTags: restrictionTags });
  },

  async saveProfile() {
    const f = this.data.editForm;
    const genderArr = ['', 'male', 'female'];
    const goalArr = ['', 'lose_fat', 'build_muscle', 'maintain'];

    const payload = {};
    if (f.genderIndex > 0) payload.gender = genderArr[f.genderIndex];
    if (f.birthday) payload.birthday = f.birthday;
    if (f.height_cm) payload.height_cm = parseFloat(f.height_cm);
    if (f.weight_kg) payload.weight_kg = parseFloat(f.weight_kg);
    if (f.exercise_details !== undefined) payload.exercise_details = f.exercise_details || '';
    if (f.goalIndex > 0) payload.fitness_goal = goalArr[f.goalIndex];
    payload.allergies = f.allergies || [];
    payload.dietary_restrictions = f.restrictions || [];

    try {
      // Avatar
      if (this.data.editAvatarUrl) {
        const token = app.globalData.token || wx.getStorageSync('token');
        await new Promise((resolve) => {
          wx.uploadFile({
            url: app.globalData.baseUrl + '/api/upload',
            filePath: this.data.editAvatarUrl,
            name: 'file',
            header: { 'Authorization': 'Bearer ' + token },
            success(res) {
              const d = JSON.parse(res.data);
              if (d.code === 0) { payload.avatar_url = d.data.image_url; }
              resolve();
            },
            fail() { resolve(); },
          });
        });
      }
      // Nickname
      if (this.data.editNickname) { payload.nickname = this.data.editNickname; }

      var result = await api.put('/api/auth/profile', payload);
      // Update body fat from save response (only calculated on save)
      if (result && result.body_fat) {
        var hasData = !!(result.height_cm && result.weight_kg && result.exercise_details);
        var bf = result.body_fat.body_fat_pct != null ? result.body_fat.body_fat_pct : null;
        this.setData({ bodyFatPct: bf, bodyFatHasData: hasData });
        app.globalData._savedBodyFat = bf;
        if (!app.globalData.userInfo) app.globalData.userInfo = {};
        app.globalData.userInfo.body_fat_pct = bf;
      }
      wx.showToast({ title: '保存成功', icon: 'success' });
      this.setData({ editMode: false });
      this.loadProfile();
    } catch (err) {
      console.error('[Profile] save error:', err);
    }
  },

  onBodyFatInfo() {
    wx.showModal({
      title: '体脂率计算方式',
      content: '基于 Deurenberg 公式（BMI + 年龄 + 性别）估算基础体脂率，再根据你填写的运动详情（卧推/深蹲/硬拉等力量数据）计算力量体重比进行调整。\n\n需要同时填写身高、体重和运动详情才能估算。\n\n数值仅供参考，精确测量请使用专业设备。',
      showCancel: false,
      confirmText: '知道了',
    });
  },

  goSettings() {
    wx.navigateTo({ url: '/pages/settings/settings' });
  },

  onChooseAvatar(e) {
    this.setData({ editAvatarUrl: e.detail.avatarUrl });
  },

  onEditNickname(e) {
    this.setData({ editNickname: e.detail.value });
  },

  async doLogin() {
    app.globalData._manualLogout = false;
    wx.showLoading({ title: '正在登录...', mask: true });
    try {
      await app.silentLogin();
      wx.hideLoading();
      if (app.globalData.isLoggedIn) {
        wx.showToast({ title: '登录成功', icon: 'success' });
        this.onShow();
      } else {
        wx.showToast({ title: '登录失败，请重试', icon: 'none' });
      }
    } catch (e) {
      wx.hideLoading();
      console.error('[Profile] login error:', e);
      wx.showToast({ title: '登录失败，请检查网络', icon: 'none' });
    }
  },

  doLogout() {
    wx.showModal({
      title: '确认退出',
      content: '退出后需要重新登录',
      success(res) {
        if (res.confirm) {
          app.logout();
          wx.showToast({ title: '已退出', icon: 'success' });
          wx.reLaunch({ url: '/pages/index/index' });
        }
      },
    });
  },
});
