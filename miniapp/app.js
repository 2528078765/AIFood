/* ── 食光助手 · App Entry (正式版 - callContainer) ── */
const ENV_ID = 'csyaifood-d0gyq6le6214959bf';
const SERVICE = 'aifood';

wx.cloud.init({ env: ENV_ID });

function _parseBody(raw) {
  if (!raw) return null;
  if (typeof raw === 'object') return raw;
  try { return JSON.parse(raw); } catch (e) { return null; }
}

App({
  globalData: {
    baseUrl: 'https://aifood-264055-6-1409000155.sh.run.tcloudbase.com',
    _envId: 'csyaifood-d0gyq6le6214959bf',
    serviceName: 'aifood',
    token: null,
    userInfo: null,
    isLoggedIn: false,
    _loginInProgress: false,
    defaultAvatar: '',
  },

  onLaunch() {
    const AVATARS = ['/images/avatar_01.png', '/images/avatar_02.png', '/images/avatar_03.png', '/images/avatar_04.png'];
    this.globalData.defaultAvatar = AVATARS[Math.floor(Math.random() * AVATARS.length)];
    this.restoreSession();
  },

  onShow() {
    const token = wx.getStorageSync('token');
    if (token && !this.globalData.isLoggedIn) {
      this.restoreSession();
    }
  },

  restoreSession() {
    try {
      const token = wx.getStorageSync('token');
      const userInfo = wx.getStorageSync('userInfo');
      if (token && userInfo) {
        this.globalData.token = token;
        this.globalData.userInfo = userInfo;
        this.globalData.isLoggedIn = true;
        this.globalData._manualLogout = false;
      } else {
        this.silentLogin().catch(function() {});
      }
    } catch (e) {
      this.silentLogin().catch(function() {});
    }
  },

  silentLogin() {
    if (this.globalData._loginInProgress) {
      return Promise.reject(new Error('Login already in progress'));
    }
    this.globalData._loginInProgress = true;
    const app = this;
    return new Promise((resolve, reject) => {
      wx.login({
        success(res) {
          if (!res.code) {
            app.globalData._loginInProgress = false;
            reject(new Error('wx.login failed: no code'));
            return;
          }
          wx.cloud.callContainer({
            config: { env: ENV_ID },
            path: '/api/auth/login',
            method: 'POST',
            header: { 'Content-Type': 'application/json', 'X-WX-SERVICE': SERVICE },
            data: { wechat_code: res.code },
            success(r) {
              app.globalData._loginInProgress = false;
              const body = _parseBody(r.data);
              if (r.statusCode === 200 && body && body.code === 0) {
                const { access_token, user } = body.data;
                app.globalData.token = access_token;
                app.globalData.userInfo = user;
                app.globalData.isLoggedIn = true;
                app.globalData._manualLogout = false;
                wx.setStorageSync('token', access_token);
                wx.setStorageSync('userInfo', user);
                resolve(user);
              } else {
                console.error('[Login] API failed, status:', r.statusCode, 'body:', JSON.stringify(body));
                reject(new Error((body && (body.message || body.detail)) || 'Login API failed status=' + r.statusCode));
              }
            },
            fail(err) {
              app.globalData._loginInProgress = false;
              reject(err);
            },
          });
        },
        fail(err) {
          app.globalData._loginInProgress = false;
          reject(err);
        },
      });
    });
  },

  autoLogin() {
    return this.silentLogin();
  },

  logout() {
    wx.removeStorageSync('token');
    wx.removeStorageSync('userInfo');
    this.globalData.token = null;
    this.globalData.userInfo = null;
    this.globalData.isLoggedIn = false;
    this.globalData._manualLogout = true;
  },

  /* ── callContainer wrapper ── */
  _callContainer(method, path, data) {
    const app = this;
    return new Promise((resolve, reject) => {
      const token = app.globalData.token || wx.getStorageSync('token');
      const header = { 'Content-Type': 'application/json', 'X-WX-SERVICE': SERVICE };
      if (token) header['Authorization'] = 'Bearer ' + token;

      wx.cloud.callContainer({
        config: { env: ENV_ID },
        path: path,
        method: method,
        header: header,
        data: data,
        success(res) {
          const body = _parseBody(res.data);
          if (res.statusCode === 200 && body && body.code === 0) {
            resolve(body.data);
          } else if (res.statusCode === 401) {
            if (app.globalData._loginInProgress) { reject(body); return; }
            const cur = app.globalData.token;
            if (cur && cur !== token) { reject(body); return; }
            wx.removeStorageSync('token');
            wx.removeStorageSync('userInfo');
            app.globalData.token = null;
            app.globalData.userInfo = null;
            app.globalData.isLoggedIn = false;
            if (!app.globalData._manualLogout) app.autoLogin();
            reject(body);
          } else {
            reject(body);
          }
        },
        fail(err) { reject(err); },
      });
    });
  },

  get(path, params)  { return this._callContainer('GET', path, params); },
  post(path, data)  { return this._callContainer('POST', path, data); },
  put(path, data)   { return this._callContainer('PUT', path, data); },
  del(path, data)   { return this._callContainer('DELETE', path, data); },

  getToken() {
    return this.globalData.token || wx.getStorageSync('token') || '';
  },

  uploadFile(filePath) {
    const app = this;
    return new Promise((resolve, reject) => {
      const token = app.getToken();
      wx.uploadFile({
        url: app.globalData.baseUrl + '/api/upload',
        filePath: filePath,
        name: 'file',
        header: { 'Authorization': token ? 'Bearer ' + token : '' },
        success(res) {
          const data = _parseBody(res.data);
          if (data && data.code === 0) resolve(data.data);
          else reject(data);
        },
        fail(err) { reject(err); },
      });
    });
  },
});
