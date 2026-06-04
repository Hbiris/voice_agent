#!/usr/bin/env python3
"""
创建/更新 DashScope Paraformer 热词表，并自动将 vocabulary_id 写入 .env。

用法：
    python scripts/create_vocab.py            # 创建或幂等更新
    python scripts/create_vocab.py --list     # 列出所有 visitor 前缀热词表
    python scripts/create_vocab.py --delete VOCAB_ID  # 删除指定热词表

需要：
    - DASHSCOPE_API_KEY 在 .env 或环境变量中
    - 能连接 dashscope.aliyuncs.com（国内网络 / VPN）
"""

import argparse
import os
import re
import sys
from pathlib import Path

# ── 项目根目录（scripts/ 的上一级）────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

# ── 热词表配置 ────────────────────────────────────────────────
PREFIX = "visitor"          # ≤10 字符，只含小写字母和数字
TARGET_MODEL = "paraformer-realtime-v2"

VOCABULARY: list[dict] = [
    # 公司名热词
    {"text": "蓝色鲸鱼", "weight": 4},
    # 常见车牌省份简称（Paraformer 对单字热词增益明显）
    {"text": "粤", "weight": 3},
    {"text": "沪", "weight": 3},
    {"text": "京", "weight": 3},
    {"text": "苏", "weight": 3},
    {"text": "浙", "weight": 3},
    {"text": "鲁", "weight": 3},
    {"text": "川", "weight": 3},
    {"text": "闽", "weight": 3},
    {"text": "渝", "weight": 3},
    {"text": "皖", "weight": 3},
]


def _load_api_key() -> str:
    # 优先环境变量，其次 .env 文件
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^DASHSCOPE_API_KEY\s*=\s*(.+)$", line.strip())
            if m:
                key = m.group(1).strip()
                break
    if not key:
        sys.exit("ERROR: DASHSCOPE_API_KEY not found in .env or environment.")
    return key


def _patch_env(vocab_id: str) -> None:
    """将 DASHSCOPE_STT_VOCABULARY_ID 写入 .env（原地替换）。"""
    text = ENV_FILE.read_text(encoding="utf-8")
    new_line = f"DASHSCOPE_STT_VOCABULARY_ID={vocab_id}"
    if re.search(r"^DASHSCOPE_STT_VOCABULARY_ID\s*=", text, re.MULTILINE):
        text = re.sub(
            r"^DASHSCOPE_STT_VOCABULARY_ID\s*=.*$",
            new_line,
            text,
            flags=re.MULTILINE,
        )
    else:
        text += f"\n{new_line}\n"
    ENV_FILE.write_text(text, encoding="utf-8")
    print(f"  .env 已更新：DASHSCOPE_STT_VOCABULARY_ID={vocab_id}")


def cmd_create(svc) -> None:
    # 幂等：检查同前缀是否已有词表，有则 update，无则 create
    existing = svc.list_vocabularies(prefix=PREFIX)
    if existing:
        vocab_id = existing[0]["vocabulary_id"]
        print(f"找到已有热词表 {vocab_id}，执行更新（update）…")
        svc.update_vocabulary(vocabulary_id=vocab_id, vocabulary=VOCABULARY)
        print(f"  更新成功，共 {len(VOCABULARY)} 条热词")
    else:
        print(f"未找到前缀为 '{PREFIX}' 的热词表，新建…")
        vocab_id = svc.create_vocabulary(
            target_model=TARGET_MODEL,
            prefix=PREFIX,
            vocabulary=VOCABULARY,
        )
        print(f"  创建成功：vocabulary_id = {vocab_id}")

    _patch_env(vocab_id)
    print(f"\n完成。vocabulary_id = {vocab_id}")


def cmd_list(svc) -> None:
    results = svc.list_vocabularies(prefix=PREFIX)
    if not results:
        print(f"没有前缀为 '{PREFIX}' 的热词表。")
        return
    for item in results:
        print(item)


def cmd_delete(svc, vocab_id: str) -> None:
    svc.delete_vocabulary(vocabulary_id=vocab_id)
    print(f"已删除：{vocab_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DashScope 热词表管理")
    parser.add_argument("--list", action="store_true", help="列出热词表")
    parser.add_argument("--delete", metavar="VOCAB_ID", help="删除热词表")
    args = parser.parse_args()

    api_key = _load_api_key()

    # 延迟导入，避免在没有 dashscope 的环境直接 import 报错
    try:
        from dashscope.audio.asr.vocabulary import VocabularyService
    except ImportError:
        sys.exit("ERROR: dashscope SDK not installed. Run: pip install dashscope")

    svc = VocabularyService(api_key=api_key)

    if args.delete:
        cmd_delete(svc, args.delete)
    elif args.list:
        cmd_list(svc)
    else:
        cmd_create(svc)


if __name__ == "__main__":
    main()
