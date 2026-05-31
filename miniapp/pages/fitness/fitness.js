const api = require('../../utils/api.js');

/* ── MET values for calorie calculation ── */
const CATEGORY_MET = {
  weightlifting: 6, running: 8, yoga: 3, hiit: 12,
  swimming: 8, cycling: 7, jump_rope: 10, other: 5,
};

const EXERCISE_CATEGORIES = [
  { key: 'weightlifting', label: '力量训练' },
  { key: 'running', label: '有氧运动' },
  { key: 'yoga', label: '瑜伽/柔韧' },
  { key: 'hiit', label: 'HIIT' },
  { key: 'swimming', label: '游泳' },
  { key: 'cycling', label: '骑行' },
  { key: 'jump_rope', label: '跳绳' },
  { key: 'other', label: '其他' },
];

function mapCategoryToBackendType(categoryKey) {
  const map = { weightlifting: 'weightlifting', running: 'running', yoga: 'yoga',
    hiit: 'hiit', swimming: 'swimming', cycling: 'cycling', jump_rope: 'other', other: 'other' };
  return map[categoryKey] || 'other';
}

Page({
  data: {
    // Calendar
    currentYear: new Date().getFullYear(),
    currentMonth: new Date().getMonth() + 1,
    weekdays: ['日', '一', '二', '三', '四', '五', '六'],
    calendarDays: [],
    checkedDates: {},
    isCurrentMonth: true,

    // Stats
    period: 'month',
    stats: {},
    streakDays: 0,
    monthCheckinDays: 0,
    monthTotalMinutes: 0,

    // Checkin form
    selectedDate: '',
    selectedDateLabel: '今天',
    isBackfill: false,
    detailedMode: true,
    selectedCategory: '',

    // Basic mode
    duration: '',
    intensity: 5,
    notes: '',

    // Detailed mode — free-form exercises
    exercises: [],
    exerciseCategories: EXERCISE_CATEGORIES,

    // Calculated
    caloriesBurned: 0,
    totalDuration: 0,
    userWeight: 70,
    submitting: false,
  },

  onLoad() {
    const today = new Date();
    this.setData({ selectedDate: this.formatDateStr(today), selectedDateLabel: '今天' });
    this.generateCalendar(this.data.currentYear, this.data.currentMonth);
  },

  onShow() {
    this.loadUserProfile();
    this.loadStats();
    this.loadCheckinDates(this.data.currentYear, this.data.currentMonth);
  },

  /* ═══════════ Calendar ═══════════ */

  formatDateStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  },

  generateCalendar(year, month) {
    const today = new Date();
    const todayStr = this.formatDateStr(today);
    const firstDay = new Date(year, month - 1, 1);
    const lastDay = new Date(year, month, 0);
    const startWeekday = firstDay.getDay();
    const totalDays = lastDay.getDate();
    const days = [];

    for (let i = 0; i < startWeekday; i++) {
      days.push({ day: '', isEmpty: true });
    }
    for (let d = 1; d <= totalDays; d++) {
      const dateStr = year + '-' + String(month).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      const isToday = dateStr === todayStr;
      const isFuture = dateStr > todayStr;
      const isChecked = this.data.checkedDates[dateStr] === true;
      const isPastNoCheckin = !isToday && !isFuture && !isChecked;
      const isSelected = dateStr === this.data.selectedDate;
      days.push({ day: d, date: dateStr, isToday, isChecked, isFuture, isPastNoCheckin, isSelected });
    }

    this.setData({
      calendarDays: days, currentYear: year, currentMonth: month,
      isCurrentMonth: (year === today.getFullYear() && month === today.getMonth() + 1),
    });
  },

  prevMonth() {
    let y = this.data.currentYear, m = this.data.currentMonth - 1;
    if (m < 1) { m = 12; y -= 1; }
    this.generateCalendar(y, m);
    this.loadCheckinDates(y, m);
  },

  nextMonth() {
    const today = new Date();
    let y = this.data.currentYear, m = this.data.currentMonth + 1;
    if (m > 12) { m = 1; y += 1; }
    if (y > today.getFullYear() || (y === today.getFullYear() && m > today.getMonth() + 1)) return;
    this.generateCalendar(y, m);
    this.loadCheckinDates(y, m);
  },

  onDayTap(e) {
    const dateStr = e.currentTarget.dataset.date;
    if (!dateStr || e.currentTarget.dataset.future) return;
    const todayStr = this.formatDateStr(new Date());
    const isBackfill = dateStr < todayStr;
    const label = isBackfill ? dateStr + ' (补卡)' : (dateStr === todayStr ? '今天' : dateStr);
    this.setData({ selectedDate: dateStr, selectedDateLabel: label, isBackfill });
    this.generateCalendar(this.data.currentYear, this.data.currentMonth);
  },

  /* ═══════════ Data Loading ═══════════ */

  async loadUserProfile() {
    try {
      const app = getApp();
      if (app && app.globalData && app.globalData.userInfo && app.globalData.userInfo.weight_kg) {
        this.setData({ userWeight: app.globalData.userInfo.weight_kg });
        return;
      }
      const profile = await api.get('/api/auth/profile', {}, { silent: true });
      if (profile && profile.weight_kg) this.setData({ userWeight: profile.weight_kg });
    } catch (err) { /* silent */ }
  },

  async loadStats() {
    var self = this;
    var stats = null;
    var streak = null;
    try {
      stats = await api.get('/api/fitness/stats', { period: this.data.period }, { silent: true }).catch(function() { return null; });
    } catch (e) { /* silent */ }
    try {
      streak = await api.get('/api/fitness/streak', {}, { silent: true }).catch(function() { return null; });
    } catch (e) { /* silent */ }
    this.setData({
      stats: stats || {}, streakDays: (streak && streak.streak_days) || 0,
      monthCheckinDays: (stats && stats.total_days) || 0,
      monthTotalMinutes: (stats && stats.total_minutes) || 0,
    });
  },

  async loadCheckinDates(year, month) {
    try {
      const mStr = String(month).padStart(2, '0');
      const startDate = year + '-' + mStr + '-01';
      const endDate = year + '-' + mStr + '-' + String(new Date(year, month, 0).getDate()).padStart(2, '0');
      const records = await api.get('/api/fitness/records', { start_date: startDate, end_date: endDate }, { silent: true });
      const checkedDates = {};
      if (records && Array.isArray(records)) {
        records.forEach(r => { if (r.checkin_date) checkedDates[r.checkin_date] = true; });
      }
      this.setData({ checkedDates });
      this.generateCalendar(year, month);
      this.loadStats();
    } catch (err) { /* silent */ }
  },

  switchPeriod() {
    const next = this.data.period === 'week' ? 'month' : 'week';
    this.setData({ period: next }, () => this.loadStats());
  },

  /* ═══════════ Category Selection ═══════════ */

  onCategoryTap(e) {
    const key = e.currentTarget.dataset.key;
    if (key === this.data.selectedCategory) {
      this.setData({ selectedCategory: '' });
      return;
    }
    this.setData({ selectedCategory: key });
    this.calculateCalories();
  },

  onToggleDetailed(e) {
    this.setData({ detailedMode: e.detail.value, exercises: [], selectedCategory: '' });
    this.calculateCalories();
  },

  /* ═══════════ Basic Mode ═══════════ */

  onDurationInput(e) { this.setData({ duration: e.detail.value }, () => this.calculateCalories()); },
  onIntensityChange(e) { this.setData({ intensity: e.detail.value }); },
  onNotesInput(e) { this.setData({ notes: e.detail.value }); },

  /* ═══════════ Detailed Mode — Free-form exercises ═══════════ */

  addExercise() {
    const exercises = this.data.exercises.concat([{ name: '', sets: '', reps: '', weight: '', duration: '' }]);
    this.setData({ exercises });
  },

  removeExercise(e) {
    const idx = e.currentTarget.dataset.index;
    const exercises = this.data.exercises.filter(function(_, i) { return i !== idx; });
    this.setData({ exercises }, () => this.calculateCalories());
  },

  onExNameInput(e) {
    const idx = e.currentTarget.dataset.index;
    this.data.exercises[idx].name = e.detail.value;
    this.setData({ exercises: this.data.exercises });
  },
  onExSetsInput(e) {
    const idx = e.currentTarget.dataset.index;
    this.data.exercises[idx].sets = e.detail.value;
    this.setData({ exercises: this.data.exercises }, () => this.calculateCalories());
  },
  onExRepsInput(e) {
    const idx = e.currentTarget.dataset.index;
    this.data.exercises[idx].reps = e.detail.value;
    this.setData({ exercises: this.data.exercises });
  },
  onExWeightInput(e) {
    const idx = e.currentTarget.dataset.index;
    this.data.exercises[idx].weight = e.detail.value;
    this.setData({ exercises: this.data.exercises });
  },
  onExDurationInput(e) {
    const idx = e.currentTarget.dataset.index;
    this.data.exercises[idx].duration = e.detail.value;
    this.setData({ exercises: this.data.exercises }, () => this.calculateCalories());
  },

  /* ═══════════ Calorie Calculation ═══════════ */

  calculateCalories() {
    const weight = this.data.userWeight || 70;
    let totalCalories = 0, totalDuration = 0;

    if (this.data.detailedMode && this.data.exercises.length > 0) {
      for (const ex of this.data.exercises) {
        const dur = parseInt(ex.duration) || 0;
        const met = (this.data.selectedCategory && CATEGORY_MET[this.data.selectedCategory]) || 5;
        totalCalories += met * weight * (dur / 60);
        totalDuration += dur;
      }
    } else {
      const duration = parseInt(this.data.duration) || 0;
      if (duration > 0 && this.data.selectedCategory) {
        const met = CATEGORY_MET[this.data.selectedCategory] || 5;
        totalCalories = met * weight * (duration / 60);
      }
      totalDuration = duration;
    }

    this.setData({ caloriesBurned: Math.round(totalCalories), totalDuration: Math.round(totalDuration) });
  },

  /* ═══════════ Submit ═══════════ */

  buildNotesForDetailed() {
    const lines = [];
    for (const ex of this.data.exercises) {
      if (!ex.name) continue;
      let line = ex.name;
      if (ex.sets) line += ' ' + ex.sets + '组';
      if (ex.reps) line += '×' + ex.reps + '次';
      if (ex.weight && parseFloat(ex.weight) > 0) line += ' ' + ex.weight + 'kg';
      if (ex.duration) line += ' | ' + ex.duration + '分钟';
      lines.push(line);
    }
    lines.push('总消耗: ' + this.data.caloriesBurned + 'kcal');
    return lines.join('; ');
  },

  async submitCheckin() {
    const hasCategory = !!this.data.selectedCategory;
    const basicDur = parseInt(this.data.duration) || 0;
    const detailDur = (this.data.detailedMode && this.data.exercises.length > 0) ? this.data.totalDuration : 0;
    const duration = detailDur || basicDur;

    if (!hasCategory || duration <= 0) {
      wx.showToast({ title: '请选择运动类型并输入时长', icon: 'none' });
      return;
    }

    this.setData({ submitting: true });
    try {
      const exerciseType = mapCategoryToBackendType(this.data.selectedCategory);
      const notes = (this.data.detailedMode && this.data.exercises.length > 0)
        ? this.buildNotesForDetailed()
        : (this.data.notes || undefined);

      await api.post('/api/fitness/checkin', {
        exercise_type: exerciseType,
        duration_min: duration,
        calories_burned: this.data.caloriesBurned || undefined,
        notes: notes,
        checkin_date: this.data.isBackfill ? this.data.selectedDate : undefined,
      }, { showLoading: false });

      wx.showToast({ title: this.data.isBackfill ? '补卡成功！' : '打卡成功！', icon: 'success' });
      this.setData({
        duration: '', notes: '', selectedCategory: '',
        exercises: [], caloriesBurned: 0, totalDuration: 0,
        submitting: false,
      });
      this.loadCheckinDates(this.data.currentYear, this.data.currentMonth);
      this.loadStats();
    } catch (err) {
      console.error('[Fitness] submit error:', err);
      this.setData({ submitting: false });
    }
  },

  goLogs() { wx.navigateTo({ url: '/pages/fitness-log/fitness-log' }); },
});
