# scorer.py - 核心评分逻辑：Whisper 转录 + AI 评分

import os
# HuggingFace 国内镜像（faster-whisper 模型下载用）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# 全局模型缓存（避免云端每次请求都重新加载模型）
_whisper_models = {}

import json
import time
import tempfile
import subprocess
import re
from pathlib import Path


# ─────────────────────────────────────────────
# 音频提取（从视频中提取音频）
# ─────────────────────────────────────────────

def extract_audio(video_path: str, output_dir: str) -> str:
    """使用 ffmpeg 从视频提取音频，返回 wav 路径"""
    video_path = Path(video_path)
    audio_path = Path(output_dir) / (video_path.stem + ".wav")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                    # 不要视频流
        "-acodec", "pcm_s16le",   # WAV 格式
        "-ar", "16000",           # 16kHz（Whisper 最佳）
        "-ac", "1",               # 单声道
        str(audio_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取音频失败：{result.stderr}")
    
    return str(audio_path)


# ─────────────────────────────────────────────
# Whisper 转录
# ─────────────────────────────────────────────

def transcribe_with_whisper(audio_path: str, model_size: str = "base", progress_callback=None) -> str:
    """
    使用 openai-whisper 转录音频，返回文本
    model_size: tiny / base / small / medium / large
    """
    try:
        import whisper
    except ImportError:
        raise ImportError("请先安装 openai-whisper：pip install openai-whisper")
    
    if progress_callback:
        progress_callback("⏳ 正在加载 Whisper 模型...")
    
    model = whisper.load_model(model_size)
    
    if progress_callback:
        progress_callback("🎙️ 正在转录音频（可能需要几分钟）...")
    
    result = model.transcribe(audio_path, language="zh", fp16=False)
    return result["text"]


def transcribe_with_faster_whisper(audio_path: str, model_size: str = "base", progress_callback=None) -> str:
    """
    使用 faster-whisper 转录（速度更快，推荐）
    模型全局缓存，避免云端每次请求都重新加载
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError("请先安装 faster-whisper：pip install faster-whisper")
    
    # 全局模型缓存
    if model_size not in _whisper_models:
        if progress_callback:
            progress_callback(f"⏳ 正在下载/加载 Faster-Whisper {model_size} 模型（首次约需 1-3 分钟）...")
        _whisper_models[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    else:
        if progress_callback:
            progress_callback(f"✅ 使用已缓存的 Whisper {model_size} 模型")
    
    model = _whisper_models[model_size]
    
    if progress_callback:
        progress_callback("🎙️ 正在转录音频（可能需要几分钟）...")
    
    segments, info = model.transcribe(audio_path, language="zh", beam_size=5)
    
    full_text = ""
    for segment in segments:
        full_text += segment.text
    
    return full_text


def transcribe_audio(audio_path: str, model_size: str = "base", progress_callback=None) -> str:
    """优先使用 faster-whisper，fallback 到 openai-whisper"""
    try:
        return transcribe_with_faster_whisper(audio_path, model_size, progress_callback)
    except ImportError:
        try:
            return transcribe_with_whisper(audio_path, model_size, progress_callback)
        except ImportError:
            raise ImportError(
                "未找到 Whisper。请安装：\n"
                "  pip install faster-whisper\n"
                "或：pip install openai-whisper"
            )


# ─────────────────────────────────────────────
# AI 评分（调用本地或远程 API）
# ─────────────────────────────────────────────

def score_with_api(prompt: str, api_key: str, base_url: str, model: str, proxy: str = None) -> dict:
    """调用 OpenAI 兼容 API 进行评分，返回解析后的 JSON 结果"""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("请先安装 openai：pip install openai")
    
    import httpx
    http_client = httpx.Client(proxy=proxy) if proxy else None
    client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是专业的数学思维课堂教学评估专家，请严格按照评分标准进行评分，只输出 JSON 格式结果。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
        max_tokens=2000,
    )
    
    raw = response.choices[0].message.content.strip()
    
    # 提取 JSON（去掉可能的 markdown 代码块）
    json_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw)
    if json_match:
        raw = json_match.group(1)
    
    return json.loads(raw)


def score_transcript(
    transcript: str,
    filename: str,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4o",
    proxy: str = None,
    progress_callback=None
) -> dict:
    """完整评分流程：给定文本 → 调用 API → 返回结构化结果"""
    from rubric import build_scoring_prompt
    
    if progress_callback:
        progress_callback("🤖 正在进行 AI 评分分析...")
    
    prompt = build_scoring_prompt(transcript, filename)
    result = score_with_api(prompt, api_key, base_url, model, proxy)
    
    return result


# ─────────────────────────────────────────────
# 完整处理管线（视频 → 转录 → 评分）
# ─────────────────────────────────────────────

def process_video(
    video_path: str,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4o",
    whisper_model: str = "base",
    proxy: str = None,
    progress_callback=None,
    temp_dir: str = None,
) -> dict:
    """
    完整处理一个视频文件：
    1. 提取音频
    2. Whisper 转录
    3. AI 评分
    返回评分结果 dict
    """
    filename = Path(video_path).name
    
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()
    
    try:
        # Step 1: 提取音频
        if progress_callback:
            progress_callback(f"🎬 正在提取音频：{filename}")
        audio_path = extract_audio(video_path, temp_dir)
        
        # Step 2: 转录
        transcript = transcribe_audio(audio_path, whisper_model, progress_callback)
        
        if not transcript.strip():
            return {
                "文件名": filename,
                "错误": "未能识别到有效语音内容，请检查视频是否有清晰的教学音频。",
                "转录文本": ""
            }
        
        # Step 3: AI 评分
        result = score_transcript(transcript, filename, api_key, base_url, model, proxy, progress_callback)
        result["转录文本"] = transcript
        result["处理时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        return result
        
    except Exception as e:
        return {
            "文件名": filename,
            "错误": str(e),
            "转录文本": ""
        }
    finally:
        # 清理临时音频文件
        try:
            audio_file = Path(temp_dir) / (Path(video_path).stem + ".wav")
            if audio_file.exists():
                audio_file.unlink()
        except Exception:
            pass
