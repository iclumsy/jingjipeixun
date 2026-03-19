# 官网首页改版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改动后端和现有路由的前提下，完成官网首页的“权威稳重 + 结构升级”改版，重点提升首屏信任感、信息层级和报名转化路径。

**Architecture:** 继续沿用现有 Flask 模板渲染方式，只修改首页模板和首页样式表。实现重点分成两层：一层是 `index.html` 的首屏与分区结构重排，另一层是 `home.css` 的视觉系统、模块层级和响应式重构；不引入新的脚本依赖，也不扩展到其他页面。

**Tech Stack:** Flask 模板、原生 HTML、原生 CSS、现有静态资源与锚点导航

---

## 文件结构与职责

### 需要修改的文件

- 修改：`/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html`
  - 首页结构文件。
  - 负责首屏 Hero、信任亮点条、局部卡片层次和底部联系收口的 HTML 结构。
- 修改：`/Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css`
  - 首页专用样式。
  - 负责颜色变量、首屏布局、卡片视觉、分区节奏、响应式规则和 CTA 样式。

### 只读参考文件

- 参考：`/Users/Ditto/Documents/jingjipeixun/docs/superpowers/specs/2026-03-19-web-homepage-redesign-design.md`
  - 已确认的中文设计说明，计划和实现都必须对齐它。
- 参考：`/Users/Ditto/Documents/jingjipeixun/training_system/app.py`
  - 本地预览入口，运行后可访问首页进行手动验证。

### 验证方式说明

当前首页是 Flask 模板 + CSS 页面，没有现成的前端自动化测试或组件测试框架。本计划采用：

1. 结构检查：确认锚点、链接、CTA 未被破坏。
2. 手动视觉检查：桌面、平板、移动宽度下验证页面层级和折叠行为。
3. 运行检查：本地启动 `training_system/app.py` 后访问 `/`。

## Task 1: 重构首页首屏与信任亮点结构

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html`
- Reference: `/Users/Ditto/Documents/jingjipeixun/docs/superpowers/specs/2026-03-19-web-homepage-redesign-design.md`

- [ ] **Step 1: 先定位当前首屏和头部结构，确认只改首页模板**

Run: `rg -n "<header class=\"site-header\"|<section class=\"hero\"|hero-highlights|hero-panel|<main>" /Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html`
Expected: 能快速定位当前头部、Hero、亮点列表和右侧面板位置。

- [ ] **Step 2: 改写 Hero 主信息区的 HTML 结构**

在 `/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html` 中，把当前首屏左侧内容调整为更直接的“机构定位 + 服务范围 + CTA + 信任短句”结构。目标结构可按下面的骨架整理：

```html
<div class="hero-copy">
  <p class="hero-kicker">阳泉本地正规特种作业培训机构</p>
  <h1>正规培训、合规考证、复审服务一站式办理</h1>
  <p class="hero-lead">面向个人及企业提供特种作业培训、考试辅导、证书复审和企业安全培训服务。</p>

  <div class="hero-actions">
    <a class="btn-primary" href="/apply">立即报名</a>
    <a class="btn-secondary" href="tel:13703531055">电话咨询</a>
  </div>

  <ul class="hero-highlights">
    <li>阳泉本地服务</li>
    <li>培训 + 考证 + 复审</li>
    <li>企业安全培训</li>
  </ul>
</div>
```

要求：

1. 保留 `/apply` 和 `tel:13703531055`。
2. 保留首屏主标题、副标题和 CTA 的语义结构。
3. 文案只能在现有事实基础上重组，不能增加未被证实的数据。

- [ ] **Step 3: 把现有右侧单一面板改成多卡片支持区**

把当前 `.hero-panel` 的单块内容重组为更清晰的支持卡区域，至少包含三类内容：

```html
<aside class="hero-panel" aria-label="首页服务概览">
  <article class="hero-panel-card">
    <p class="panel-label">机构服务</p>
    <h2>围绕培训、考证、复审和企业培训，提供规范服务支持。</h2>
  </article>

  <article class="hero-panel-card">
    <h3>报名流程</h3>
    <ol class="hero-flow-list">
      <li>咨询报名</li>
      <li>资料审核</li>
      <li>培训辅导</li>
      <li>参加考试 / 复审</li>
    </ol>
  </article>

  <article class="hero-panel-card hero-panel-card-contact">
    <h3>咨询方式</h3>
    <p>霍老师 13703531055</p>
    <a href="/apply">在线提交信息</a>
  </article>
</aside>
```

要求：

1. 保留原来的信息主题，不要新造业务内容。
2. 结构要为 CSS 提供明确钩子类名。
3. 联系方式卡要保留清晰 CTA。

- [ ] **Step 4: 在首屏后补入独立的信任亮点条**

在 Hero 结束处、`<main>` 之前或首个正文 section 之前加入独立的亮点条容器，例如：

```html
<div class="hero-trust-strip">
  <div class="site-shell hero-trust-strip-inner">
    <span>阳泉本地服务</span>
    <span>正规培训组织</span>
    <span>报名流程清晰</span>
    <span>企业培训支持</span>
  </div>
</div>
```

要求：

1. 该区域必须独立于 `hero-highlights`，承担首屏下方横向强化作用。
2. 使用简短可扫读文案。
3. 不新增锚点，不改变现有导航目标。

- [ ] **Step 5: 对正文区块做最小必要的语义增强**

在不推翻现有 section 顺序的前提下，补充少量帮助样式控制的类名，优先考虑：

1. 报考指南卡片的流程强调类。
2. 联系区收口 CTA 的辅助容器类。
3. 可能需要的 section 修饰类，例如更强的标题说明、卡片分组包裹类。

不要做大规模结构重写；这一步只做后续样式落点准备。

- [ ] **Step 6: 检查模板结构是否闭合且 CTA 未被破坏**

Run: `python3 - <<'PY'\nfrom pathlib import Path\ntext = Path('/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html').read_text()\nfor token in ['/apply', 'tel:13703531055', 'id=\"about\"', 'id=\"contact\"']:\n    print(token, token in text)\nPY`
Expected: 输出的四项都为 `True`。

- [ ] **Step 7: 提交首轮 HTML 结构改造**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html
git commit -m "feat: restructure homepage hero and trust strip"
```

## Task 2: 重建首页视觉系统与首屏层级

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css`
- Reference: `/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html`

- [ ] **Step 1: 调整全局视觉变量，建立更稳重的页面底色**

在 `:root` 与 `body` 区域更新首页视觉变量，目标是保留深蓝 + 金色，但加入更暖的浅底和更克制的阴影。例如：

```css
:root {
  --home-primary: #10283f;
  --home-primary-deep: #081a2b;
  --home-accent: #c7a86a;
  --home-sand: #f4efe6;
  --home-ivory: #fbf8f2;
  --home-border: rgba(16, 40, 63, 0.12);
  --home-shadow: 0 22px 48px rgba(8, 26, 43, 0.10);
}

body {
  background:
    radial-gradient(circle at top left, rgba(199, 168, 106, 0.10), transparent 28%),
    linear-gradient(180deg, #f2f4f7 0%, #f6f4ef 32%, #f2f5f7 100%);
}
```

要求：

1. 不把页面做成“土豪金”风格。
2. 颜色更新后仍要支持当前所有 section 和按钮。

- [ ] **Step 2: 重做 Hero 的版式、按钮和卡片层级**

围绕新 HTML 结构改写首屏相关样式，包括但不限于：

1. `.hero`
2. `.hero-grid`
3. `.hero-copy`
4. `.hero-actions`
5. `.hero-highlights`
6. `.hero-panel`
7. `.hero-panel-card`
8. `.hero-flow-list`
9. `.hero-trust-strip`

首屏目标样式特征：

1. 左侧标题更有权威感，右侧卡片更清楚地承担辅助说明。
2. CTA 更明显，但不做过度营销式高亮。
3. 信任亮点条在视觉上是首屏到正文的过渡层，而不是普通一排标签。

建议骨架：

```css
.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(320px, 0.88fr);
  gap: 34px;
}

.hero-panel {
  display: grid;
  gap: 14px;
}

.hero-panel-card {
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.55);
  box-shadow: 0 24px 48px rgba(5, 16, 27, 0.18);
}
```

- [ ] **Step 3: 拉开正文各区块层级，减少“全是同一类卡片”的感觉**

重写或细化下列区域的样式，让它们呈现更明确的节奏差异：

1. `.section`
2. `.section-muted`
3. `.section-dark`
4. `.section-contact`
5. `.section-heading`
6. `.about-copy-card`
7. `.trust-card`
8. `.program-card`
9. `.guide-card`
10. `.contact-card`

要求：

1. 关于我们与培训项目要有明显区分。
2. 报考指南要更像流程信息块。
3. 联系我们要更像页面收口。

- [ ] **Step 4: 保持桌面悬浮 CTA 和移动端 CTA 的风格统一**

更新：

1. `.floating-actions`
2. `.floating-action-primary`
3. `.floating-action-secondary`
4. `.mobile-actions`
5. `.mobile-action-primary`
6. `.mobile-action-secondary`

要求：

1. 保留现有行为和位置。
2. 视觉上与新首页体系一致。
3. 不遮挡正文内容。

- [ ] **Step 5: 做一次样式文件静态检查**

Run: `rg -n "hero-panel-card|hero-trust-strip|hero-flow-list" /Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css`
Expected: 三类新增结构都有对应样式定义。

- [ ] **Step 6: 提交视觉系统改造**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css
git commit -m "feat: refresh homepage visual hierarchy"
```

## Task 3: 完成响应式折叠与移动端首屏优化

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css`
- Reference: `/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html`

- [ ] **Step 1: 重做 Hero 在 1180px、820px、560px 断点下的折叠规则**

重点检查并更新以下媒体查询里的首屏与导航规则：

1. `.topbar-inner`
2. `.site-nav`
3. `.hero-grid`
4. `.hero-copy`
5. `.hero-panel`
6. `.hero-trust-strip-inner`

移动端目标：

1. 主文案先显示。
2. 支持卡片后显示。
3. 按钮不换成难点按的超小尺寸。
4. 首屏高度不能失控。

- [ ] **Step 2: 优化正文卡片在窄屏下的密度**

在现有媒体查询基础上细调以下内容：

1. section 上下边距
2. 卡片 padding
3. 标题字号
4. guide / program / trust / contact 的网格折叠方式

目标是移动端仍然显得正式、干净，而不是简单粗暴堆叠。

- [ ] **Step 3: 确认移动端固定 CTA 与正文不冲突**

检查并视需要调整：

1. `.site-footer` 的底部留白
2. `.mobile-actions` 的 padding
3. 联系区和页脚的底部空间

避免底部操作条覆盖“联系我们”或页脚文案。

- [ ] **Step 4: 提交响应式优化**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css
git commit -m "feat: polish homepage responsive layout"
```

## Task 4: 本地运行、手动验收与收尾

**Files:**
- Verify: `/Users/Ditto/Documents/jingjipeixun/training_system/app.py`
- Verify: `/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html`
- Verify: `/Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css`

- [ ] **Step 1: 启动本地 Flask 服务预览首页**

Run: `python3 /Users/Ditto/Documents/jingjipeixun/training_system/app.py`
Expected: 服务启动在 `http://127.0.0.1:5001` 或 `http://0.0.0.0:5001`，日志中可能有配置警告，但应用应成功启动。

- [ ] **Step 2: 访问首页做桌面端视觉验收**

检查项：

1. 首屏是否先传达“机构可信 + 服务范围 + CTA”。
2. 右侧卡片是否形成信息辅助，而不是抢主标题。
3. 信任亮点条是否起到承接作用。
4. 关于我们、培训项目、报考指南、联系我们是否有明显层级差异。

- [ ] **Step 3: 缩放到平板和移动宽度做响应式验收**

建议至少检查：

1. 1180px 左右
2. 820px 左右
3. 390px 左右

重点确认：

1. 首屏主文案先于辅助卡显示。
2. CTA 保持清晰可点。
3. 底部固定 CTA 未遮挡内容。

- [ ] **Step 4: 手动检查锚点和关键链接**

检查：

1. 顶部导航锚点跳转到正确 section。
2. `/apply` 仍然可用。
3. `tel:13703531055` 链接未丢失。

- [ ] **Step 5: 查看最终改动范围，确认只触及首页相关文件**

Run: `git diff -- /Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html /Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css`
Expected: diff 只包含首页模板和首页样式相关改动。

- [ ] **Step 6: 提交最终验收版本**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html /Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css
git commit -m "feat: redesign marketing homepage"
```

## 计划完成判定

当以下结果全部满足时，可以开始执行：

1. 执行者能清楚知道只改两个首页文件。
2. 首屏结构、信任亮点条、正文层级和响应式折叠都有明确任务归属。
3. 验证方式清晰，不依赖仓库中不存在的自动化测试框架。
4. 每个任务都能独立提交，便于回滚和 review。
