const app = getApp();
const api = require('../../utils/api.js');

Page({
  data: {
    recipeId: '',
    recipe: null,
    nutrition: null,
    loading: true,
  },

  onLoad(options) {
    if (options.id && app.globalData._recipeDetail) {
      const cached = app.globalData._recipeDetail;
      if (cached.id === options.id) {
        this.setData({
          recipe: cached,
          nutrition: cached.nutrition_per_serving || null,
          loading: false,
        });
        app.globalData._recipeDetail = null;
        return;
      }
    }
    if (options.id) {
      this.setData({ recipeId: options.id });
      this.loadDetail();
    }
  },

  async loadDetail() {
    const id = this.data.recipeId;
    if (!id) return;

    this.setData({ loading: true });
    try {
      const recipe = await api.get('/api/recipe/' + id, {}, { silent: true });
      this.setData({
        recipe: recipe,
        nutrition: recipe.nutrition_per_serving || null,
        loading: false,
      });
    } catch (err) {
      console.error('[RecipeDetail] load error:', err);
      this.setData({ loading: false });
    }
  },
});
