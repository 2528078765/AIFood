# TabBar Icons

This directory needs 8 PNG icon files (81x81px each):

| File | Purpose | Suggested Icon |
|------|---------|---------------|
| home.png | 首页 (inactive) | House outline |
| home-active.png | 首页 (active) | House filled, green |
| recipe.png | 食谱 (inactive) | Recipe/book outline |
| recipe-active.png | 食谱 (active) | Recipe/book filled, green |
| fitness.png | 健身 (inactive) | Dumbbell/running outline |
| fitness-active.png | 健身 (active) | Dumbbell/running filled, green |
| profile.png | 我的 (inactive) | Person outline |
| profile-active.png | 我的 (active) | Person filled, green |

## How to get icons

Option 1: Use WeChat DevTools
- Open the project in WeChat DevTools
- Right-click the images/tabbar folder
- Upload your own icon assets

Option 2: Download from iconfont.cn
- Search for "home", "food", "fitness", "user" icons
- Download as 81x81px PNG
- Color: #999999 for inactive, #07C160 for active (WeChat green)

Option 3: Use placeholder generation
- WeChat Mini Program will show broken-image placeholders until proper icons are added
- The app is fully functional without custom icons

## Temporary workaround
If you need to test the app immediately, you can use any 81x81 PNG images
as the tab bar will display them scaled down. The active/inactive distinction
is handled by WeChat's tabBar engine itself.
