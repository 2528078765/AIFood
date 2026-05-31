const app = getApp();
const api = require('../../utils/api.js');

Page({
  data: {
    currentMeal: 'all',
    dailyMeals: [],
    singleMeal: null,
    loading: false,
    generating: false,
    bodyFatInfo: null,
    warning: '',
  },

  onShow() {
    this.loadRecipes();
  },

  onPullDownRefresh() {
    this.loadRecipes().then(function() { wx.stopPullDownRefresh(); });
  },

  _buildParams() {
    var params = {};
    var ui = app.globalData.userInfo;
    if (ui && ui.exercise_details) {
      params.exercise_details = ui.exercise_details;
    }
    return params;
  },

  async loadRecipes() {
    this.setData({ loading: true });
    try {
      var meals = ['breakfast', 'lunch', 'dinner'];
      var params = this._buildParams();
      var results = await Promise.all(
        meals.map(function(m) {
          return api.get('/api/recipe/generate', Object.assign({ meal: m }, params), { silent: true }).catch(function() { return null; });
        })
      );
      var self = this;
      var dailyMeals = meals.map(function(m, i) {
        return {
          meal_type: m,
          recipes: (results[i] && results[i].recipes) || [],
          total_calories: self._sumCalories((results[i] && results[i].recipes) || []),
          meal_budget: (results[i] && results[i].meal_budget) || 0,
        };
      });
      var bodyFatInfo = this.data.bodyFatInfo;
      var warning = '';
      for (var j = 0; j < results.length; j++) {
        var r = results[j];
        if (r && r.body_fat && r.body_fat.body_fat_pct) {
          bodyFatInfo = r.body_fat;
        }
        if (r && r.warning && !warning) {
          warning = r.warning;
        }
      }
      this.setData({ dailyMeals: dailyMeals, loading: false, bodyFatInfo: bodyFatInfo, warning: warning });
    } catch (err) {
      console.error('[Recipe] load error:', err);
      this.setData({ loading: false });
    }
  },

  _sumCalories(recipes) {
    if (!recipes || !recipes.length) return 0;
    return recipes.reduce(function(sum, r) {
      return sum + ((r.nutrition_per_serving && r.nutrition_per_serving.calories) || 0);
    }, 0);
  },

  switchMeal(e) {
    var meal = e.currentTarget.dataset.meal;
    this.setData({ currentMeal: meal, singleMeal: null });
    if (meal !== 'all') {
      this.loadSingleMeal(meal);
    }
  },

  async loadSingleMeal(mealType) {
    this.setData({ generating: true });
    try {
      var params = this._buildParams();
      var data = await api.get('/api/recipe/generate', Object.assign({ meal: mealType }, params), { silent: true }).catch(function() { return null; });
      data = data || {};
      var warning = (data && data.warning) || '';
      if (data && data.body_fat && data.body_fat.body_fat_pct) {
        this.setData({ bodyFatInfo: data.body_fat });
      }
      this.setData({ singleMeal: data, generating: false, warning: warning });
    } catch (err) {
      console.error('[Recipe] single meal error:', err);
      this.setData({ generating: false });
    }
  },

  async refreshRecommend() {
    wx.showLoading({ title: 'AI 重新生成中...' });
    this.setData({ singleMeal: null });
    try {
      await this.loadRecipes();
      if (this.data.currentMeal !== 'all') {
        await this.loadSingleMeal(this.data.currentMeal);
      }
    } finally {
      wx.hideLoading();
    }
    wx.showToast({ title: '已刷新', icon: 'success' });
  },

  viewDetail(e) {
    var id = e.currentTarget.dataset.id;
    if (!id) return;
    var allRecipes;
    if (this.data.currentMeal === 'all') {
      allRecipes = [];
      (this.data.dailyMeals || []).forEach(function(m) {
        (m.recipes || []).forEach(function(r) { allRecipes.push(r); });
      });
    } else {
      allRecipes = (this.data.singleMeal && this.data.singleMeal.recipes) || [];
    }
    var recipe = allRecipes.find(function(r) { return r.id === id; });
    if (recipe) {
      app.globalData._recipeDetail = recipe;
    }
    wx.navigateTo({ url: '/pages/recipe-detail/recipe-detail?id=' + id });
  },
});
