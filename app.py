# app.py - 课堂实录评分工具 Streamlit 主界面

import streamlit as st
import os
import sys
import json
import time
import tempfile
import shutil
from pathlib import Path
import threading

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rubric import RUBRIC, get_grade, get_grade_color

# ─────────────────────────────────────────────
# 云端部署：从 Streamlit Secrets 读取默认配置
# ─────────────────────────────────────────────
def is_running_on_cloud():
    """检测是否运行在 Streamlit Cloud 上"""
    return os.path.exists("/mount/src")

def get_default_api_key():
    """优先返回用户在界面输入的 key，其次从 secrets 读取默认值"""
    try:
        return st.secrets.get("API_KEY", "")
    except Exception:
        return ""

def get_default_base_url():
    try:
        return st.secrets.get("BASE_URL", "")
    except Exception:
        return ""

def get_default_model():
    try:
        return st.secrets.get("MODEL", "deepseek-chat")
    except Exception:
        return "deepseek-chat"

# ─────────────────────────────────────────────
# 页面配置
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="课堂实录评分工具",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# 自定义样式
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 主标题 */
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.3rem;
    }
    .sub-title {
        font-size: 1rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    
    /* 评分卡片 */
    .score-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
        border-left: 5px solid #4a90e2;
    }
    .score-card-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    
    /* 档次徽章 */
    .badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        color: white;
    }
    .badge-优秀 { background: #1a7f37; }
    .badge-良好 { background: #0550ae; }
    .badge-合格 { background: #9a6700; }
    .badge-不达标 { background: #cf222e; }
    
    /* 总分展示 */
    .total-score {
        font-size: 3.5rem;
        font-weight: 800;
        text-align: center;
    }
    
    /* 进度状态 */
    .status-box {
        background: #f0f7ff;
        border: 1px solid #c8e1ff;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        color: #0550ae;
    }
    
    /* 文件列表 */
    .file-item {
        display: flex;
        align-items: center;
        padding: 0.4rem 0;
        border-bottom: 1px solid #eee;
    }
    
    /* 引用框 */
    .quote-box {
        background: #fff8e1;
        border-left: 4px solid #f9a825;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        color: #4a3800;
    }
    
    /* 建议框 */
    .suggest-box {
        background: #f0fdf4;
        border-left: 4px solid #16a34a;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        color: #14532d;
    }
    
    /* 错误框 */
    .error-box {
        background: #fff0f0;
        border: 1px solid #fca5a5;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        color: #991b1b;
    }
    
    /* 强制侧边栏始终可见 */
    section[data-testid="stSidebar"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        transform: none !important;
        width: 300px !important;
        min-width: 300px !important;
    }
    section[data-testid="stSidebar"] > div {
        display: flex !important;
    }
    /* 展开侧边栏的按钮也强制可见（确保兜底） */
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        position: fixed !important;
        left: 0px !important;
        top: 50% !important;
        width: 36px !important;
        height: 72px !important;
        background: #4a90e2 !important;
        border-radius: 0 12px 12px 0 !important;
        z-index: 99999 !important;
        cursor: pointer !important;
    }
    [data-testid="collapsedControl"] svg {
        color: white !important;
    }
    
    /* 隐藏 Streamlit 默认元素 */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 预设接口配置
# ─────────────────────────────────────────────
PRESET_CONFIGS = {
    "🐋 DeepSeek（推荐）": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "key_placeholder": "sk-...",
        "note": "性价比极高，中文理解好，推荐首选",
        "need_key": True,
    },
    "🤖 Ollama（本地，免费）": {
        "base_url": "http://localhost:11434/v1",
        "models": ["qwen2.5:7b", "qwen2.5:14b", "deepseek-r1:8b", "llama3.2:3b", "自定义"],
        "default_model": "qwen2.5:7b",
        "key_placeholder": "ollama（无需填写）",
        "note": "💡 完全本地运行，无需 API Key，数据不出本机！",
        "need_key": False,
    },
    "🔮 OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "default_model": "gpt-4o",
        "key_placeholder": "sk-...",
        "note": "效果最强，但费用较高",
        "need_key": True,
    },
    "🧠 智谱 GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "models": ["glm-4-flash", "glm-4-air", "glm-4"],
        "default_model": "glm-4-flash",
        "key_placeholder": "填入智谱 API Key",
        "note": "国内访问稳定，glm-4-flash 免费可用",
        "need_key": True,
    },
    "🌙 阿里通义": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max"],
        "default_model": "qwen-plus",
        "key_placeholder": "填入阿里云 API Key",
        "note": "中文理解好，国内访问稳定",
        "need_key": True,
    },
    "⚙️ 自定义": {
        "base_url": "",
        "models": ["自定义"],
        "default_model": "自定义",
        "key_placeholder": "填入对应 API Key",
        "note": "手动填写任意 OpenAI 兼容接口",
        "need_key": True,
    },
}

# ─────────────────────────────────────────────
# 侧边栏：配置
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# 侧边栏：配置
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ 配置")
    
    st.markdown("### 🔑 API 设置")
    
    # 接口预设选择（云端自动隐藏 Ollama）
    on_cloud = is_running_on_cloud()
    preset_options = list(PRESET_CONFIGS.keys())
    if on_cloud:
        preset_options = [k for k in preset_options if "Ollama" not in k]
    preset_name = st.selectbox(
        "选择接口",
        options=preset_options,
        index=0,  # 默认 DeepSeek
        key="preset_name_select",
        help="选择 Ollama 可完全本地运行，无需任何 API Key" if not on_cloud else "云端部署仅展示在线 API 接口"
    )
    preset = PRESET_CONFIGS[preset_name]
    st.caption(f"ℹ️ {preset['note']}")
    
    # Ollama 本地模式特殊提示
    if "Ollama" in preset_name:
        st.info("🖥️ **本地模式**：无需 API Key，需先安装 Ollama 并下载模型。见下方「使用指南」。")
    
    # API Key（本地模式不需要）
    if preset["need_key"]:
        default_key = get_default_api_key() if preset_name == "🐋 DeepSeek（推荐）" else ""
        api_key = st.text_input(
            "API Key",
            type="password",
            value=default_key,
            placeholder=preset["key_placeholder"],
            help="填入对应服务的 API Key（已预填默认值，可修改）"
        )
    else:
        api_key = "ollama"  # Ollama 不验证 Key，填任意值即可
        st.caption("✅ 本地模式无需 API Key")
    
    # Base URL
    default_base = get_default_base_url() if preset_name == "🐋 DeepSeek（推荐）" else preset["base_url"]
    if preset_name == "⚙️ 自定义":
        base_url = st.text_input(
            "API Base URL",
            value=default_base or "",
            placeholder="https://your-api.com/v1",
            help="OpenAI 兼容接口地址"
        )
    else:
        base_url = st.text_input(
            "API Base URL",
            value=default_base or preset["base_url"],
            key=f"base_url_{preset_name}",
            help="OpenAI 兼容接口地址"
        )
    
    # 模型选择（用 preset_name 作为 key，确保切换接口时下拉列表刷新）
    model_options = preset["models"]
    default_model = get_default_model() if preset_name == "🐋 DeepSeek（推荐）" else preset["default_model"]
    try:
        default_index = model_options.index(default_model)
    except ValueError:
        default_index = 0
    model_select = st.selectbox(
        "AI 模型",
        options=model_options,
        index=default_index,
        key=f"model_select_{preset_name}",   # ← 关键：key 随接口变化，强制刷新
        help="选择评分使用的 AI 模型"
    )
    if model_select == "自定义":
        model = st.text_input("自定义模型名称", placeholder="model-name",
                              key=f"custom_model_{preset_name}")
    else:
        model = model_select
    
    # 代理设置（国内访问国外API可能需要）
    st.markdown("### 🌐 网络代理（可选）")
    proxy_url = st.text_input(
        "代理地址",
        value="",
        placeholder="如：http://127.0.0.1:7890",
        help="国内访问 DeepSeek/OpenAI 超时时，可填入本地代理地址（Clash/V2Ray 等）"
    )
    if proxy_url:
        st.caption(f"✅ 已配置代理：{proxy_url}")
    else:
        st.caption("留空则不使用代理")
    
    st.divider()
    
    st.markdown("### 🎙️ 语音转录设置")
    whisper_model = st.selectbox(
        "Whisper 模型",
        options=["tiny", "base", "small", "medium", "large"],
        index=1,
        help="模型越大精度越高，但速度越慢。推荐 base（平衡） 或 small（更准）"
    )
    
    st.caption("💡 模型自动从国内镜像下载，无需翻墙")
    
    whisper_model_info = {
        "tiny": "⚡ 最快（精度较低，约39M）",
        "base": "✅ 推荐（速度/精度平衡，约74M）",
        "small": "🎯 较准（慢2倍，约244M）",
        "medium": "💎 精准（慢6倍，约769M）",
        "large": "🏆 最准（慢10倍，约1550M）",
    }
    st.caption(whisper_model_info.get(whisper_model, ""))
    
    st.divider()
    
    # 评分标准说明
    st.markdown("### 📋 评分标准说明")
    st.markdown("""
**教学方法（30分）**  
含3个维度，各10分：

| 维度 | 说明 |
|------|------|
| 启发引导式教学 | 开放性提问与思维引导 |
| 教学逻辑 | 思维方法与解题拆解 |
| 效果外化 | 知识整理与迁移应用 |

**档次划分：**
- 🏆 优秀：27-30分
- 🔵 良好：21-27分  
- 🟡 合格：15-21分
- 🔴 不达标：<15分
""")
    
    st.divider()
    st.caption("💡 支持上传最多 10 个视频，每个不超过 800MB")


# ─────────────────────────────────────────────
# 主界面
# ─────────────────────────────────────────────
st.markdown('<div class="main-title">🎓 课堂实录评分工具</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">基于《不同班型教师画像+评分标准（L7-L9）》 · 支持批量视频上传</div>', unsafe_allow_html=True)

# 侧边栏未展开时显示提示
st.markdown("""
<div style="background: linear-gradient(135deg, #e8f0fe, #d4e4ff); border: 1px solid #a8c8f0; 
border-radius: 12px; padding: 10px 16px; margin: 8px 0; display: flex; align-items: center; gap: 10px;">
    <span style="font-size: 22px;">⚙️</span>
    <span style="color: #1a5fb4; font-size: 0.9rem;">
        <strong>配置面板</strong> 在页面左侧。如被收起，点击此按钮展开 →
    </span>
    <button onclick="
        (function(){
            var doc = document;
            var btn = doc.querySelector('[data-testid=collapsedControl]');
            if(btn){ btn.click(); return; }
            var sidebar = doc.querySelector('section[data-testid=stSidebar]');
            if(sidebar){sidebar.style.display='flex';sidebar.style.visibility='visible';sidebar.style.opacity='1';sidebar.style.width='300px';sidebar.style.minWidth='300px';}
            // also try parent
            try{
                var pbtn = parent.document.querySelector('[data-testid=collapsedControl]');
                if(pbtn) pbtn.click();
                var psb = parent.document.querySelector('section[data-testid=stSidebar]');
                if(psb){psb.style.display='flex';psb.style.visibility='visible';psb.style.opacity='1';}
            }catch(e){}
        })();
    " style="
        background:#4a90e2; color:white; border:none; border-radius:8px; 
        padding:8px 16px; cursor:pointer; font-size:0.9rem; font-weight:bold;
        box-shadow: 0 2px 8px rgba(74,144,226,0.4);
    ">🔓 展开配置面板</button>
</div>
<script>
(function forceSidebar(){
    function show(){
        var sel = 'section[data-testid="stSidebar"]';
        var sidebar = document.querySelector(sel) || (function(){try{return parent.document.querySelector(sel);}catch(e){return null;}})();
        if(sidebar){ sidebar.style.display='flex'; sidebar.style.visibility='visible'; sidebar.style.opacity='1'; sidebar.style.width='300px'; sidebar.style.minWidth='300px'; }
        var btn = document.querySelector('[data-testid="collapsedControl"]') || (function(){try{return parent.document.querySelector('[data-testid="collapsedControl"]');}catch(e){return null;}})();
        if(btn){ btn.click(); }
    }
    setTimeout(show, 300);
    setTimeout(show, 800);
    setTimeout(show, 1500);
})();
</script>
""", unsafe_allow_html=True)

# Tab 布局
tab_upload, tab_results, tab_guide = st.tabs(["📤 上传评分", "📊 历史结果", "📖 使用指南"])


# ─────────────────────────────────────────────
# Tab 1: 上传与评分
# ─────────────────────────────────────────────
with tab_upload:
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        st.markdown("### 📹 上传课堂实录视频")
        
        uploaded_files = st.file_uploader(
            "选择视频文件（最多10个，每个≤800MB）",
            type=["mp4", "avi", "mov", "mkv", "wmv", "flv", "m4v", "webm"],
            accept_multiple_files=True,
            help="支持 MP4、AVI、MOV、MKV、WMV 等常见格式"
        )
        
        # 文件数量校验
        if uploaded_files:
            if len(uploaded_files) > 10:
                st.error(f"⚠️ 最多支持 10 个视频，当前已选 {len(uploaded_files)} 个，请移除多余文件。")
                uploaded_files = uploaded_files[:10]
            
            # 显示已上传文件列表
            st.markdown(f"**已选择 {len(uploaded_files)} 个文件：**")
            total_size = 0
            oversized = []
            for f in uploaded_files:
                size_mb = f.size / (1024 * 1024)
                size_gb = size_mb / 1024
                total_size += f.size
                icon = "✅" if size_mb < 800 else "❌"
                if size_mb >= 800:
                    oversized.append(f.name)
                size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_gb:.2f} GB"
                st.markdown(f"{icon} `{f.name}` — {size_str}")
            
            if oversized:
                st.error(f"❌ 以下文件超过 800MB 限制：{', '.join(oversized)}")
            
            total_mb = total_size / (1024 * 1024)
            st.caption(f"📦 总大小：{total_mb:.1f} MB")
        
        # 可选：直接粘贴文本转录（调试/快速模式）
        st.markdown("---")
        st.markdown("### 📝 或者直接粘贴课堂文字记录（可选）")
        st.caption("如果已有文字版课堂实录，可直接粘贴，跳过视频转录步骤。")
        
        manual_text_mode = st.checkbox("使用文字模式（不上传视频）")
        
        if manual_text_mode:
            manual_filename = st.text_input("文件/课程名称", placeholder="如：2026-06-10-张老师-分数乘法.mp4")
            manual_transcript = st.text_area(
                "粘贴课堂实录文字",
                height=250,
                placeholder="请粘贴完整的课堂实录文字内容...\n\n例如：\n老师：同学们，今天我们学习分数的乘法。谁能告诉我，3/4 × 2 等于多少？\n学生：3/2！\n老师：非常好！那你能告诉我为什么吗？..."
            )
    
    with col_right:
        st.markdown("### ✅ 开始评分")
        
        # API Key 检查提示（Ollama 本地模式不需要）
        need_key = preset.get("need_key", True)
        if need_key and not api_key:
            st.warning("⚠️ 请在左侧侧边栏填入 API Key 后开始评分")
        
        # 评分按钮
        key_ok = (not need_key) or bool(api_key)
        has_content = (
            (uploaded_files and len([f for f in uploaded_files if f.size < 800 * 1024 * 1024]) > 0)
            or (manual_text_mode and manual_transcript and manual_filename)
        )
        btn_disabled = not key_ok or not has_content
        
        start_btn = st.button(
            "🚀 开始批量评分",
            type="primary",
            disabled=btn_disabled,
            use_container_width=True
        )
        
        if need_key and not api_key:
            if on_cloud:
                st.info("💡 **没有 API Key？**\n\n前往 [DeepSeek 开放平台](https://platform.deepseek.com) 免费注册获取，新用户赠送额度。填入左侧即可使用。")
            else:
                st.info("💡 **没有 API Key？**\n\n左侧切换为「🤖 Ollama（本地，免费）」，安装后即可完全免费使用！")
        
        st.markdown("---")
        st.markdown("**📋 评分流程：**")
        st.markdown("""
1. 🎬 提取视频音频
2. 🎙️ Whisper 语音转文字
3. 🤖 AI 根据标准评分
4. 📊 生成结构化报告
""")
        
        st.markdown("**⏱️ 预计耗时：**")
        st.caption("每个10分钟视频约需 3-8 分钟（取决于硬件）")


# ─────────────────────────────────────────────
# 评分执行逻辑
# ─────────────────────────────────────────────
if start_btn:
    # 收集待处理任务
    tasks = []
    
    if manual_text_mode and manual_transcript and manual_filename:
        tasks.append({
            "type": "text",
            "filename": manual_filename,
            "transcript": manual_transcript
        })
    
    if uploaded_files:
        valid_files = [f for f in uploaded_files if f.size < 800 * 1024 * 1024]
        for f in valid_files:
            tasks.append({
                "type": "video",
                "file": f,
                "filename": f.name
            })
    
    if not tasks:
        st.error("没有有效的任务，请检查输入。")
    else:
        from scorer import process_video, score_transcript
        
        # 初始化结果存储
        if "results" not in st.session_state:
            st.session_state.results = []
        
        total_tasks = len(tasks)
        
        with tab_upload:
            st.markdown("---")
            st.markdown(f"### ⚙️ 正在处理 {total_tasks} 个文件...")
            
            overall_progress = st.progress(0, text="准备中...")
            
            for idx, task in enumerate(tasks):
                filename = task["filename"]
                
                st.markdown(f"**[{idx+1}/{total_tasks}] 处理：`{filename}`**")
                status_placeholder = st.empty()
                
                def update_status(msg, placeholder=status_placeholder):
                    placeholder.markdown(f'<div class="status-box">{msg}</div>', unsafe_allow_html=True)
                
                update_status("🔄 初始化...")
                
                try:
                    if task["type"] == "text":
                        # 直接评分
                        result = score_transcript(
                            task["transcript"],
                            filename,
                            api_key,
                            base_url,
                            model,
                            proxy_url or None,
                            update_status
                        )
                        result["转录文本"] = task["transcript"]
                        result["处理时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    else:
                        # 视频处理
                        tmp_dir = tempfile.mkdtemp()
                        
                        try:
                            # 保存上传文件到临时目录
                            update_status(f"💾 保存文件到临时目录...")
                            tmp_video = os.path.join(tmp_dir, filename)
                            with open(tmp_video, "wb") as f:
                                f.write(task["file"].read())
                            
                            result = process_video(
                                tmp_video,
                                api_key,
                                base_url,
                                model,
                                whisper_model,
                                proxy_url or None,
                                update_status,
                                tmp_dir
                            )
                        finally:
                            shutil.rmtree(tmp_dir, ignore_errors=True)
                    
                    # 存储结果
                    st.session_state.results.append(result)
                    
                    if "错误" in result:
                        status_placeholder.error(f"❌ 处理失败：{result['错误']}")
                    else:
                        total_score = result.get("总分", 0)
                        grade = result.get("整体档次", "")
                        status_placeholder.success(f"✅ 完成！总分：{total_score} · 档次：{grade}")
                
                except Exception as e:
                    status_placeholder.error(f"❌ 意外错误：{str(e)}")
                    st.session_state.results.append({
                        "文件名": filename,
                        "错误": str(e)
                    })
                
                # 更新总进度
                overall_progress.progress((idx + 1) / total_tasks, text=f"已完成 {idx+1}/{total_tasks}")
            
            overall_progress.progress(1.0, text="✅ 全部完成！")
            st.success(f"🎉 批量评分完成！共处理 {total_tasks} 个文件，请查看「📊 历史结果」标签页。")
            st.balloons()


# ─────────────────────────────────────────────
# Tab 2: 历史结果展示
# ─────────────────────────────────────────────
with tab_results:
    results = st.session_state.get("results", [])
    
    if not results:
        st.info("📭 暂无评分结果，请先在「📤 上传评分」中提交视频或文字记录。")
    else:
        # 顶部操作栏
        col_clear, col_export, col_spacer = st.columns([1, 2, 4])
        with col_clear:
            if st.button("🗑️ 清空结果"):
                st.session_state.results = []
                st.rerun()
        with col_export:
            # 导出所有结果为 JSON
            json_data = json.dumps(results, ensure_ascii=False, indent=2)
            st.download_button(
                "⬇️ 导出全部结果 (JSON)",
                data=json_data,
                file_name=f"评分结果_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        st.markdown(f"**共 {len(results)} 条评分记录**")
        st.divider()
        
        for i, result in enumerate(results):
            filename = result.get("文件名", f"文件{i+1}")
            process_time = result.get("处理时间", "")
            
            if "错误" in result:
                with st.expander(f"❌ {filename}  ({process_time})", expanded=False):
                    st.markdown(f'<div class="error-box">❌ 处理失败：{result["错误"]}</div>', unsafe_allow_html=True)
                continue
            
            total_score = result.get("总分", 0)
            grade = result.get("整体档次", "未知")
            grade_color = get_grade_color(grade)
            
            with st.expander(
                f"📄 {filename}  |  总分 {total_score}/30  |  {grade}  ({process_time})",
                expanded=(i == len(results) - 1)  # 最新结果默认展开
            ):
                # ── 总体评分
                col_score, col_grade, col_summary = st.columns([1, 1, 3])
                
                with col_score:
                    st.markdown(f"<div class='total-score' style='color:{grade_color}'>{total_score}</div>", unsafe_allow_html=True)
                    st.markdown("<div style='text-align:center;color:#666;font-size:0.85rem'>总分（满分30）</div>", unsafe_allow_html=True)
                
                with col_grade:
                    st.markdown(f"""
<div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:8px'>
    <span class='badge badge-{grade}' style='font-size:1.1rem;padding:6px 20px'>{grade}</span>
    <span style='color:#666;font-size:0.8rem'>整体档次</span>
</div>""", unsafe_allow_html=True)
                
                with col_summary:
                    summary = result.get("综合评语", "")
                    if summary:
                        st.markdown(f'<div class="quote-box">📝 <strong>综合评语：</strong>{summary}</div>', unsafe_allow_html=True)
                
                st.divider()
                
                # ── 三维度详细评分
                st.markdown("#### 📊 三维度评分详情")
                
                details = result.get("评分详情", [])
                
                dim_cols = st.columns(3)
                dim_colors = ["#4a90e2", "#e2844a", "#4ae27a"]
                
                for j, detail in enumerate(details):
                    with dim_cols[j % 3]:
                        dim_name = detail.get("评价项", "")
                        dim_score = detail.get("得分", 0)
                        dim_grade = detail.get("档次", "")
                        
                        grade_badge_colors = {
                            "优": "#1a7f37", "良": "#0550ae",
                            "中": "#9a6700", "差": "#cf222e"
                        }
                        badge_color = grade_badge_colors.get(dim_grade, "#666")
                        
                        st.markdown(f"""
<div style='background:#f8f9fa;border-radius:10px;padding:1rem;border-top:4px solid {dim_colors[j % 3]}'>
    <div style='font-weight:600;font-size:1rem;margin-bottom:0.5rem'>{dim_name}</div>
    <div style='font-size:2rem;font-weight:800;color:{dim_colors[j % 3]}'>{dim_score}<span style='font-size:1rem;color:#999'>/10</span></div>
    <span style='background:{badge_color};color:white;padding:2px 10px;border-radius:12px;font-size:0.8rem'>{dim_grade}</span>
</div>""", unsafe_allow_html=True)
                
                st.markdown("")
                
                # ── 各维度得分原因与建议
                for detail in details:
                    dim_name = detail.get("评价项", "")
                    reason = detail.get("得分原因", "")
                    suggestion = detail.get("改进建议", "")
                    
                    with st.expander(f"🔍 {dim_name} — 详细分析", expanded=False):
                        if reason:
                            st.markdown(f'<div class="quote-box">📋 <strong>得分原因：</strong><br>{reason}</div>', unsafe_allow_html=True)
                        if suggestion:
                            st.markdown(f'<div class="suggest-box">💡 <strong>改进建议：</strong><br>{suggestion}</div>', unsafe_allow_html=True)
                
                st.divider()
                
                # ── 核心改进建议
                core_suggestions = result.get("核心改进建议", [])
                if core_suggestions:
                    st.markdown("#### 🎯 给老师的核心改进建议")
                    for k, suggestion in enumerate(core_suggestions, 1):
                        st.markdown(f'<div class="suggest-box">**{k}.** {suggestion}</div>', unsafe_allow_html=True)
                
                # ── 转录文本（折叠）
                transcript = result.get("转录文本", "")
                if transcript:
                    with st.expander("📝 查看课堂实录转录原文", expanded=False):
                        st.text_area("转录文本", transcript, height=200, disabled=True, key=f"transcript_{i}")
                
                # ── 单条结果下载
                st.download_button(
                    f"⬇️ 下载本条结果",
                    data=json.dumps(result, ensure_ascii=False, indent=2),
                    file_name=f"评分_{filename}_{process_time.replace(':', '-') if process_time else ''}.json",
                    mime="application/json",
                    key=f"download_{i}"
                )


# ─────────────────────────────────────────────
# Tab 3: 使用指南
# ─────────────────────────────────────────────
with tab_guide:
    st.markdown("""
## 📖 使用指南

### 🌐 API 推荐

本工具支持接入主流大模型 API 进行智能评分，推荐首选 DeepSeek（中文理解力强、费用极低）。

| 接口 | 推荐模型 | 费用参考 | 特点 |
|------|---------|---------|------|
| 🐋 DeepSeek | deepseek-chat | 极低（约¥0.002/千token） | 中文理解力强、性价比最高，**推荐首选** |
| 🧠 智谱 GLM | glm-4-flash | **免费**（有额度上限） | 国内访问稳定，新用户赠送免费额度 |
| 🌙 阿里通义 | qwen-plus | 低 | 中文语感优秀，阿里云生态集成方便 |
| 🔮 OpenAI | gpt-4o | 较高 | 综合能力最强，适合对精度有极致要求的场景 |

**获取 API Key：**
- 🐋 DeepSeek → [platform.deepseek.com](https://platform.deepseek.com)（新用户注册即赠额度）
- 🧠 智谱 GLM → [open.bigmodel.cn](https://open.bigmodel.cn)（有免费额度，注册即用）
- 🌙 阿里通义 → [dashscope.aliyun.com](https://dashscope.aliyun.com)

> 💡 **提示**：在左侧「🔑 API 设置」中选择对应接口，填入 API Key 即可使用。Key 仅保存在你的浏览器会话中，不会上传到服务器。

---

### 📊 评分维度详解

本工具基于火花思维教师能力模型，从三个核心维度对课堂教学进行客观评分。总分 **30 分**，AI 会结合课堂实录中的具体语句和行为逐项打分。

---

#### 一、启发引导式教学（满分 10 分）

> **核心考察**：教师是否以**开放性提问**引导学生自主思考，而非单纯给出封闭式指令或直接告知答案。

**打分逻辑**：AI 会统计课堂中开放式问题（"你怎么想的？""还有其他方法吗？"）与封闭式问题（"是不是？""对不对？"）的比例，并评估教师是否根据学生反馈**动态调整**引导方向。

| 档次 | 分数 | 行为标准 |
|------|------|---------|
| 🏆 **优** | 9-10 分 | 依据学生实时反馈灵活调整引导方向；鼓励学生**自主质疑、主动探究**；提问具有层次感，能逐层深入；明显培养了学生的思维能力而非仅仅追求正确答案 |
| 🔵 **良** | 7-8.5 分 | 能按教案完成关键提问，过半为开放式问题；能引导学生思考，但开放式问题**数量有限**，引导**深度不够**；遇到学生卡壳时能给予适当提示，但引导方式偏单一 |
| 🟡 **中** | 5-6.5 分 | 依照教案完成基础提问，但开放式问题**比例偏低**；有一定引导意识，但深度不足；学生自主思考空间较小，教师倾向于快速给出答案或直接纠正 |
| 🔴 **差** | 0-4.5 分 | 提问以封闭式为主，频繁出现"是不是""对不对"等确认性语句；引导方向单一，基本不给学生**自主思考的空间**；教学过程以教师讲授为主导，缺少互动启发 |

**典型区分点**：
- 中→良的关键跨越：开放式问题从"偶尔出现"变为"主要提问方式"
- 良→优的关键跨越：从"按预设提问"变为"根据学生反馈动态调整引导策略"

---

#### 二、教学逻辑（满分 10 分）

> **核心考察**：教师是否**讲清思维方法**、帮助学生理解**解题逻辑**而不仅仅关注答案对错。

**打分逻辑**：AI 会评估教师是否展示了完整的思维链条（从问题分析→方法选择→步骤推演→结论验证），以及在讲解复杂题型时能否将思路**逐层拆解**，让学生理解"为什么这样做"而不只是"怎么做"。

| 档次 | 分数 | 行为标准 |
|------|------|---------|
| 🏆 **优** | 9-10 分 | 思维方法讲得**透彻清晰**；能将复杂题型**系统拆解**为可理解的子步骤；学生能**模仿思路举一反三**；讲解中体现了清晰的数学思想（如分类讨论、数形结合、方程建模等），学生不仅会做题，更理解了背后的思维框架 |
| 🔵 **良** | 7-8.5 分 | 教学过程体现了基础思维方法（如分类讨论、方程思想等），讲解有**一定深度**；但在最难题型或关键转折点处，思维拆解仍**不够系统**，学生独立迁移方法可能存在困难 |
| 🟡 **中** | 5-6.5 分 | 引导过程中能体现基础思维方法，但讲解的**深度和广度不足**；在复杂难题中思维方法的应用**不够清晰**，学生难以系统掌握解题思路；重点偏向"做对题"而非"理解思路" |
| 🔴 **差** | 0-4.5 分 | **按部就班**讲解解题步骤，仅关注答案对错；对解题思路的形成过程、常见思维误区**缺乏梳理**；学生听完知道答案，但换一道同类题仍然不会做，方法难以迁移 |

**典型区分点**：
- 中→良的关键跨越：从"提到了思维方法"变为"比较系统地展示了思维方法"
- 良→优的关键跨越：从"展示方法"变为"拆解方法，让学生能举一反三"

---

#### 三、效果外化（满分 10 分）

> **核心考察**：教师是否引导学生**主动整理知识体系**、建立**跨场景迁移能力**，让学习成果可呈现、可迁移。

**打分逻辑**：AI 会评估教师是否在课堂上带领学生归纳总结知识点，是否将当前内容与学生已有知识、其他学科、生活实际或竞赛内容建立**有意义的连接**，以及学生是否形成了可带走的知识结构（如笔记、思维导图、方法总结等）。

| 档次 | 分数 | 行为标准 |
|------|------|---------|
| 🏆 **优** | 9-10 分 | **高度重视**知识整理，课上主动带领学生归纳、串联知识点，帮助学生建立**自己的知识体系**；讲课过程中能**自然地**连接到生活实际、其他学科、竞赛内容或以往所学，让学生清楚知道"这知识能去哪用""遇到类似问题怎么变通" |
| 🔵 **良** | 7-8.5 分 | 重视知识整理，课上**有意识**带学生归纳串联知识点；能帮助学生建立知识体系，但跨学科/跨场景的连接**不够自然**，有时显得生硬或刻意；场景迁移主要靠教师引导，学生自主迁移能力尚未形成 |
| 🟡 **中** | 5-6.5 分 | 能有意识地引导学生**规范整理**知识要点，对重点内容进行归纳与适当分类；偶尔关联校内知识体系或其他学科/生活场景，能**初步建立**知识连接，但不够系统和深入；知识整理以教师主导为主 |
| 🔴 **差** | 0-4.5 分 | 依赖标准笔记模板，仅**口头提醒**学生抄记，缺少逻辑梳理；知识整理停留在**被动复制**层面；几乎没有课程效果外化的意识，极少关联校内知识体系、其他学科或生活场景 |

**典型区分点**：
- 中→良的关键跨越：从"偶尔关联"变为"有意识地系统串联"
- 良→优的关键跨越：从"教师主导关联"变为"学生能自主迁移，教师连接自然流畅"

---

#### 总分定档

三项维度得分相加，对照以下标准确定整体评价等级：

| 档次 | 分数区间 | 含义 |
|------|---------|------|
| 🏆 **优秀** | 27 ≤ N ≤ 30 | 三项维度均表现出色，课堂教学质量达到标杆水平 |
| 🔵 **良好** | 21 ≤ N < 27 | 整体教学扎实，个别维度有提升空间 |
| 🟡 **合格** | 15 ≤ N < 21 | 基本达标，但教学方法和效果外化方面需要系统性改进 |
| 🔴 **不达标** | N < 15 | 多项维度存在明显短板，需要重点帮扶和教学重构 |

> 📌 **评分精度**：AI 支持 0.5 分步进打分，且会引用课堂实录中的**具体语句和行为**作为评分依据，确保结果可追溯、可复核。
""")

