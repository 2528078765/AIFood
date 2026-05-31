/* ── Auth Helper · 食光助手 ──
   Manages login flow, token persistence, and profile CRUD. */

const api = require('./api.js');

/**
 * Login: wx.login → POST /api/auth/login → store token + user
 * @returns {Promise<object>} { access_token, user }
 */
function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (!res.code) {
          reject(new Error('wx.login failed: no code returned'));
          return;
        }

        api.post('/api/auth/login', { wechat_code: res.code }, { silent: true })
          .then((data) => {
            const { access_token, user } = data;
            wx.setStorageSync('token', access_token);
            wx.setStorageSync('userInfo', user);

            const app = getApp();
            if (app && app.globalData) {
              app.globalData.token = access_token;
              app.globalData.userInfo = user;
              app.globalData.isLoggedIn = true;
            }

            resolve({ access_token, user });
          })
          .catch((err) => {
            console.error('[Auth] Login API error:', err);
            reject(err);
          });
      },
      fail(err) {
        console.error('[Auth] wx.login error:', err);
        reject(err);
      },
    });
  });
}

/**
 * Get the current user profile from the backend.
 * @returns {Promise<object>}
 */
function getProfile() {
  return api.get('/api/auth/profile', {}, { showLoading: true, loadingText: '加载中...' });
}

/**
 * Update user profile (height, weight, goal, allergies, etc.)
 * @param {object} data - Profile fields to update
 * @returns {Promise<object>}
 */
function updateProfile(data) {
  return api.put('/api/auth/profile', data, { showLoading: true, loadingText: '保存中...' });
}

/**
 * Check whether the user is currently logged in (token exists).
 * Note: does NOT validate token expiry — the API layer handles 401 auto-refresh.
 * @returns {boolean}
 */
function checkLogin() {
  const token = wx.getStorageSync('token');
  return !!token;
}

/**
 * Clear all stored credentials and reset app state.
 */
function logout() {
  wx.removeStorageSync('token');
  wx.removeStorageSync('userInfo');

  const app = getApp();
  if (app && app.globalData) {
    app.globalData.token = null;
    app.globalData.userInfo = null;
    app.globalData.isLoggedIn = false;
  }
}

module.exports = {
  login,
  getProfile,
  updateProfile,
  checkLogin,
  logout,
};
