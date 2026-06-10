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
    
    # 接口预设选择
    preset_name = st.selectbox(
        "选择接口",
        options=list(PRESET_CONFIGS.keys()),
        index=0,  # 默认 DeepSeek
        key="preset_name_select",
        help="选择 Ollama 可完全本地运行，无需任何 API Key"
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

### 🔧 环境准备（首次使用）

#### 1. 安装 Python 依赖
```bash
pip install streamlit openai faster-whisper
```

#### 2. 安装 FFmpeg（用于从视频提取音频）

**Windows：**
```powershell
winget install FFmpeg
```
> 也可前往 https://www.gyan.dev/ffmpeg/builds/ 手动下载，解压后将 bin 目录加入系统 PATH

**Mac：**
```bash
brew install ffmpeg
```

#### 3. 启动程序
```bash
cd classroom_scorer
streamlit run app.py
```

---

### 🖥️ 本地模式（免费，无需 API Key）— 推荐尝试

使用 **Ollama** 在本机运行大模型，**数据完全不出本机，永久免费**。

**第一步：安装 Ollama**
```
前往 https://ollama.com 下载安装（Windows/Mac/Linux 均支持）
```

**第二步：下载推荐模型**
```bash
# 推荐：Qwen2.5 7B，中文理解好，普通电脑可流畅运行（约4.7GB）
ollama pull qwen2.5:7b

# 内存充足（16GB+）可用更强版本
ollama pull qwen2.5:14b

# 极低配置备选（约2GB，速度快但精度略低）
ollama pull qwen2.5:3b
```

**第三步：在本工具中选择**
- 左侧「选择接口」→ **🤖 Ollama（本地，免费）**
- 无需填写 API Key
- 选择对应已下载的模型名称

> 💡 **硬件参考**：8GB 内存可跑 7B 模型；16GB 内存推荐 14B；4GB 内存用 3B

---

### 🌐 在线 API 模式

| 接口 | 推荐模型 | 费用 | 特点 |
|------|---------|------|------|
| 🐋 DeepSeek | deepseek-chat | 极低（约¥0.002/千token） | 中文理解强，**首选** |
| 🧠 智谱 GLM | glm-4-flash | **免费** | 国内稳定，免费额度大 |
| 🌙 阿里通义 | qwen-plus | 低 | 中文好，国内稳定 |
| 🔮 OpenAI | gpt-4o | 较高 | 效果最强 |

**注册 API Key：**
- DeepSeek：https://platform.deepseek.com
- 智谱 GLM：https://open.bigmodel.cn（有免费额度）
- 阿里通义：https://dashscope.aliyun.com

---

### 📊 评分维度说明

| 维度 | 满分 | 核心考察点 |
|------|------|-----------|
| 启发引导式教学 | 10分 | 开放性提问 vs 封闭式问题，是否鼓励自主思考 |
| 教学逻辑 | 10分 | 思维方法是否讲透，能否拆解复杂题型 |
| 效果外化 | 10分 | 知识整理方式，跨学科/跨场景迁移能力 |

**总分档次：**
| 档次 | 分数范围 |
|------|---------|
| 🏆 优秀 | 27-30分 |
| 🔵 良好 | 21-27分 |
| 🟡 合格 | 15-21分 |
| 🔴 不达标 | <15分 |

---

### 💡 常见问题

**Q: 转录很慢怎么办？**  
A: Whisper 首次运行需下载模型。选 `tiny` 最快，或安装 GPU 版 `faster-whisper` 大幅加速。

**Q: 本地 Ollama 评分质量怎样？**  
A: `qwen2.5:7b` 的中文理解和教学分析能力已相当不错，能给出较准确的评分和建议；如追求更高精度可用 14B 模型。

**Q: 可以导出结果吗？**  
A: 可以，「历史结果」页支持导出全部结果为 JSON 文件。
""")

