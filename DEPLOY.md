# 🚀 云端部署指南

## 第一步：准备 GitHub 仓库

1. 注册 [GitHub](https://github.com) 账号
2. 创建一个**公开（Public）**仓库（私有仓库需要付费计划）
3. 把 `classroom_scorer` 文件夹推送到仓库：

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

⚠️ **注意：不要在仓库中包含你的 API Key！** `secrets.example.toml` 是模板可以提交，真正的 Secrets 在下一步配置。

---

## 第二步：部署到 Streamlit Cloud

1. 访问 [share.streamlit.io](https://share.streamlit.io)
2. 用 GitHub 账号登录
3. 点击右上角 **"New app"**
4. 选择你的 GitHub 仓库、`main` 分支
5. 主文件路径填：`app.py`
6. 点击 **"Deploy!"**

---

## 第三步：配置 Secrets（API Key）

1. 部署完成后，进入 App Dashboard
2. 点击右上角 **"Settings"** → **"Secrets"**
3. 添加以下内容：

```toml
API_KEY = "sk-你的DeepSeek-API-Key"
```

4. 点击保存，应用会自动重启

---

## 第四步：分享给同事

部署成功后，应用会得到一个永久链接：
```
https://你的用户名-仓库名.streamlit.app
```

把这个链接直接发给同事，打开浏览器就能用，**无需安装任何软件**。

---

## 注意事项

| 项目 | 说明 |
|------|------|
| 🎥 视频上传 | 每个视频 ≤ 800MB（通过 config.toml 配置），大视频建议用文字模式 |
| ⏱️ 处理速度 | 10分钟视频约需 5-8 分钟（云端 CPU 模式） |
| 💰 费用 | DeepSeek API 约 ¥0.002/千token，20分钟课堂录制约 0.3-0.5 元 |
| 🔒 隐私 | 视频只在你自己的应用会话中处理，不会保存到服务器 |
| 🕐 休眠 | 免费版 5 天无访问会自动休眠，访问即唤醒 |

---

## 本地开发 vs 云端部署

| 特性 | 本地（桌面快捷方式） | 云端（Streamlit Cloud） |
|------|---------------------|------------------------|
| 安装依赖 | 需要 Python + FFmpeg | 无需安装 |
| 文件大小 | 1GB | 800MB |
| 处理速度 | 取决于本机性能 | 云端 CPU |
| 数据安全 | 完全本地 | 上传到云处理 |
| 分享 | 只能自己用 | 链接分享即可 |
| 费用 | 免费 | 免费（仅 API 费用） |
