# 照片背景替换功能修复说明

## 问题描述
重构后生成的体检表中，照片底色没有被替换为白色，日志显示警告：
```
WARNING: rembg or cv2 not available, skipping background removal
```

## 问题原因
`rembg` 库依赖 `onnxruntime`，但该依赖包没有安装在虚拟环境中。虽然 `rembg` 本身已安装，但由于缺少其核心依赖，导致导入失败。

## 解决方案
1. 安装缺失的依赖：
```bash
source .venv/bin/activate
pip install onnxruntime
```

2. 更新 `requirements.txt`，添加 `onnxruntime>=1.24.0`

## 验证
运行以下命令验证功能正常：
```bash
source .venv/bin/activate
python -c "from rembg import remove, new_session; print('✓ rembg works')"
```

## 注意事项
- 确保在虚拟环境中运行应用
- 首次使用 `rembg` 时会自动下载 AI 模型（约 170MB）
- 背景替换功能需要一定的处理时间

## 功能说明
照片背景替换功能会：
1. 使用 AI 模型识别人像
2. 移除原始背景
3. 替换为白色背景
4. 优化边缘以避免衣服区域缺失

如果处理失败，系统会自动使用原始照片，不会影响文档生成。
