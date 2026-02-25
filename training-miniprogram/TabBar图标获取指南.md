# TabBar 图标获取指南

## 当前状态

为了让小程序能够正常运行，我已经暂时移除了 TabBar 的图标配置，只保留文字标签。小程序现在可以正常编译和使用。

## 如何添加图标

### 方案一：使用 iconfont（推荐）

1. 访问 [iconfont.cn](https://www.iconfont.cn/)
2. 搜索以下图标：
   - "表单" 或 "edit" - 用于信息采集
   - "列表" 或 "list" - 用于我的提交
   - "审核" 或 "check" - 用于审核管理

3. 下载图标（PNG格式，建议尺寸：81x81 像素）

4. 准备两套图标：
   - 未选中状态：灰色 (#666666)
   - 选中状态：紫色 (#6366f1)

### 方案二：使用 IconPark

1. 访问 [IconPark](https://iconpark.oceanengine.com/)
2. 搜索并下载相应图标
3. 导出为 PNG 格式

### 方案三：使用微信官方图标库

1. 在微信开发者工具中
2. 点击"工具" -> "图标库"
3. 选择合适的图标并导出

## 图标规范

根据微信小程序规范：
- **格式**：PNG
- **尺寸**：81x81 像素（推荐）或 40x40 像素
- **大小**：不超过 40KB
- **颜色**：
  - 未选中：#666666（灰色）
  - 选中：#6366f1（紫色）

## 需要的图标文件

创建 `images` 目录，并放入以下6个文件：

```
training-miniprogram/
└── images/
    ├── submit.png          # 信息采集（未选中）
    ├── submit-active.png   # 信息采集（选中）
    ├── list.png            # 我的提交（未选中）
    ├── list-active.png     # 我的提交（选中）
    ├── admin.png           # 审核管理（未选中）
    └── admin-active.png    # 审核管理（选中）
```

## 添加图标后的配置

准备好图标文件后，在 `app.json` 中恢复图标配置：

```json
"tabBar": {
  "color": "#666666",
  "selectedColor": "#6366f1",
  "backgroundColor": "#ffffff",
  "borderStyle": "black",
  "list": [
    {
      "pagePath": "pages/user/submit/submit",
      "text": "信息采集",
      "iconPath": "images/submit.png",
      "selectedIconPath": "images/submit-active.png"
    },
    {
      "pagePath": "pages/user/list/list",
      "text": "我的提交",
      "iconPath": "images/list.png",
      "selectedIconPath": "images/list-active.png"
    },
    {
      "pagePath": "pages/admin/review/review",
      "text": "审核管理",
      "iconPath": "images/admin.png",
      "selectedIconPath": "images/admin-active.png"
    }
  ]
}
```

## 推荐的图标关键词

在图标网站搜索时，可以使用以下关键词：

1. **信息采集**：
   - edit / 编辑
   - form / 表单
   - write / 填写
   - document / 文档

2. **我的提交**：
   - list / 列表
   - file / 文件
   - document / 文档
   - history / 历史

3. **审核管理**：
   - check / 审核
   - verify / 验证
   - approve / 批准
   - manage / 管理

## 注意事项

1. 图标文件必须放在项目根目录的 `images` 文件夹中
2. 文件名必须与 app.json 中配置的完全一致
3. 确保图标背景透明
4. 建议使用简洁的线条图标，避免过于复杂的设计

## 当前可用性

**小程序现在已经可以正常运行了！** 只是 TabBar 暂时只显示文字，没有图标。这不影响功能使用，图标可以后续添加。
