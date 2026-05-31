/* ── API Wrapper · 食光助手 (正式版 - callContainer) ── */
const ENV_ID = 'csyaifood-d0gyq6le6214959bf';
const SERVICE = 'aifood';
const app = getApp();

function _parseBody(raw) {
  if (!raw) return null;
  if (typeof raw === 'object') return raw;
  try { return JSON.parse(raw); } catch (e) { return null; }
}

function request(method, path, data = {}, options = {}) {
  const { showLoading = false, loadingText = '加载中...', silent = false,
          isUpload = false, filePath = '' } = options;

  if (showLoading) wx.showLoading({ title: loadingText, mask: true });

  return new Promise((resolve, reject) => {
    const token = (app && app.getToken()) || wx.getStorageSync('token') || '';
    const header = { 'X-WX-SERVICE': SERVICE };
    if (!isUpload) header['Content-Type'] = 'application/json';
    if (token) header['Authorization'] = 'Bearer ' + token;

    const baseOptions = {
      config: { env: ENV_ID },
      path: path,
      method: method,
      header: header,
      success(res) {
        if (showLoading) wx.hideLoading();
        const body = _parseBody(res.data);
        if (res.statusCode === 200 && body && body.code === 0) {
          resolve(body.data);
        } else if (res.statusCode === 401) {
          if (app && app.globalData._loginInProgress) { reject(body); return; }
          const cur = app && app.globalData && app.globalData.token;
          if (cur && cur !== token) { reject(body); return; }
          wx.removeStorageSync('token'); wx.removeStorageSync('userInfo');
          if (app && app.globalData) {
            app.globalData.token = null; app.globalData.userInfo = null;
            app.globalData.isLoggedIn = false;
            if (!app.globalData._manualLogout) app.autoLogin();
          }
          reject(body);
        } else {
          const msg = (body && body.message) || '请求失败';
          if (!silent) wx.showToast({ title: msg, icon: 'none' });
          reject(body);
        }
      },
      fail(err) {
        if (showLoading) wx.hideLoading();
        if (!silent) wx.showToast({ title: '网络错误', icon: 'none' });
        reject(err);
      },
    };

    if (isUpload) {
      const baseUrl = (app && app.globalData && app.globalData.baseUrl) || '';
      wx.uploadFile({
        url: baseUrl + path,
        filePath: filePath,
        name: 'file',
        header: header,
        success(res) {
          if (showLoading) wx.hideLoading();
          const body = _parseBody(res.data);
          if (res.statusCode === 200 && body && body.code === 0) {
            resolve(body.data);
          } else {
            const msg = (body && body.message) || '上传失败';
            if (!silent) wx.showToast({ title: msg, icon: 'none' });
            reject(body);
          }
        },
        fail(err) {
          if (showLoading) wx.hideLoading();
          if (!silent) wx.showToast({ title: '网络错误', icon: 'none' });
          reject(err);
        },
      });
    } else if (method === 'GET') {
      var keys = Object.keys(data);
      if (keys.length > 0) {
        var qs = keys.map(function(k) {
          return encodeURIComponent(k) + '=' + encodeURIComponent(data[k]);
        }).join('&');
        baseOptions.path = baseOptions.path + '?' + qs;
      }
      wx.cloud.callContainer(baseOptions);
    } else {
      baseOptions.data = data;
      wx.cloud.callContainer(baseOptions);
    }
  });
}

function get(path, params = {}, options = {}) { return request('GET', path, params, options); }
function post(path, data = {}, options = {}) { return request('POST', path, data, options); }
function put(path, data = {}, options = {}) { return request('PUT', path, data, options); }
function del(path, data = {}, options = {}) { return request('DELETE', path, data, options); }

function uploadFile(filePath, options = {}) {
  return request('POST', '/api/upload', {}, { ...options, isUpload: true, filePath });
}

// SSE streaming — callContainer doesn't support chunked, fallback to wx.request
function postStream(path, data = {}) {
  return new Promise((resolve, reject) => {
    const token = (app && app.getToken()) || wx.getStorageSync('token') || '';
    const baseUrl = (app && app.globalData && app.globalData.baseUrl) || '';
    const task = wx.request({
      url: baseUrl + path,
      method: 'POST',
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? 'Bearer ' + token : ''
      },
      data: data,
      timeout: 120000,
      enableChunked: true,
      responseType: 'text',
      success() {},
      fail(err) { reject(err); },
    });
    resolve(task);
  });
}

module.exports = { get, post, put, del, uploadFile, request, postStream };
