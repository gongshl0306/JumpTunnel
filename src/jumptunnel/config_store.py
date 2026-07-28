"""跳板机档案与映射列表的本地持久化。

配置文件位于 ~/.ssh_forward_tool/config.json，结构：
{
    "profiles": [
        {"name": ..., "host": ..., "port": 22, "username": ..., "password": ...},
        ...
    ],
    "last_mappings": [
        {"auto_port": true, "local_port": 0, "target_host": ...,
         "target_port": ..., "scheme": "http|https", "note": ...},
        ...
    ],
    "last_profile": "选中的档案名（可空）"
}
"""

import json
import os
from typing import List, Dict, Any

# 配置目录与文件路径
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".ssh_forward_tool")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config() -> Dict[str, Any]:
    """读取配置文件。文件不存在或损坏时返回空结构。"""
    empty = {"profiles": [], "last_mappings": [], "last_profile": ""}
    if not os.path.exists(CONFIG_FILE):
        return empty
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return empty
    # 容错：补齐缺失的字段
    data.setdefault("profiles", [])
    data.setdefault("last_mappings", [])
    data.setdefault("last_profile", "")
    return data


def save_config(data: Dict[str, Any]) -> None:
    """写入配置文件，自动创建目录。"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- 跳板机档案 CRUD ----------

def upsert_profile(data: Dict[str, Any], profile: Dict[str, Any]) -> None:
    """新增或更新一条跳板机档案（按 name 匹配）。"""
    profiles = data["profiles"]
    for i, p in enumerate(profiles):
        if p["name"] == profile["name"]:
            profiles[i] = profile
            break
    else:
        profiles.append(profile)


def delete_profile(data: Dict[str, Any], name: str) -> None:
    """按名删除一条跳板机档案。"""
    data["profiles"] = [p for p in data["profiles"] if p["name"] != name]
    if data.get("last_profile") == name:
        data["last_profile"] = ""


def set_last_mappings(data: Dict[str, Any], mappings: List[Dict[str, Any]]) -> None:
    """保存上次的映射列表（不含运行状态）。"""
    data["last_mappings"] = mappings


def profile_names(data: Dict[str, Any]) -> List[str]:
    """返回所有档案名，用于下拉列表。"""
    return [p["name"] for p in data["profiles"]]


def find_profile(data: Dict[str, Any], name: str) -> Dict[str, Any]:
    """按名查找档案，找不到返回空字典。"""
    for p in data["profiles"]:
        if p["name"] == name:
            return p
    return {}
