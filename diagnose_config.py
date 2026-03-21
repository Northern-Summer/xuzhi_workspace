#!/usr/bin/env python3
"""
OpenClaw配置诊断工具 - 安全读取模式
零风险：仅读取文件，不进行任何修改
"""

import json
import os
import sys

def diagnose_openclaw_config():
    """诊断OpenClaw配置文件问题"""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    
    print("🔍 OpenClaw配置诊断报告")
    print("=" * 60)
    
    # 1. 检查文件存在性和可读性
    if not os.path.exists(config_path):
        print("❌ 配置文件不存在:", config_path)
        return False
    
    print(f"📂 配置文件: {config_path}")
    print(f"📏 文件大小: {os.path.getsize(config_path)} bytes")
    
    # 2. 验证JSON语法
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✅ JSON语法验证通过")
    except json.JSONDecodeError as e:
        print(f"❌ JSON语法错误: {e}")
        return False
    
    # 3. 诊断已知问题
    issues = []
    
    # 问题1: models.providers.ollama.models 应为数组
    try:
        ollama_models = config.get('models', {}).get('providers', {}).get('ollama', {}).get('models')
        if ollama_models is not None:
            if isinstance(ollama_models, dict) and len(ollama_models) == 0:
                issues.append({
                    'path': 'models.providers.ollama.models',
                    'current': '{} (空对象)',
                    'expected': '[] (空数组)',
                    'severity': 'HIGH'
                })
            elif not isinstance(ollama_models, list):
                issues.append({
                    'path': 'models.providers.ollama.models',
                    'current': str(type(ollama_models)),
                    'expected': 'list',
                    'severity': 'HIGH'
                })
    except (KeyError, AttributeError):
        pass
    
    # 问题2: agents.defaults.models.ollama/* 的冗余字段
    try:
        agent_models = config.get('agents', {}).get('defaults', {}).get('models', {})
        for model_key in agent_models:
            if 'ollama/' in model_key:
                model_data = agent_models[model_key]
                extra_fields = []
                if 'description' in model_data:
                    extra_fields.append('description')
                if 'taskLayer' in model_data:
                    extra_fields.append('taskLayer')
                
                if extra_fields:
                    issues.append({
                        'path': f'agents.defaults.models.{model_key}',
                        'current': f"包含冗余字段: {', '.join(extra_fields)}",
                        'expected': '空对象 {} 或符合 schema 的字段',
                        'severity': 'MEDIUM'
                    })
    except (KeyError, AttributeError):
        pass
    
    # 问题3: agents.defaults.compactOn 冗余字段
    try:
        agent_defaults = config.get('agents', {}).get('defaults', {})
        if 'compactOn' in agent_defaults:
            issues.append({
                'path': 'agents.defaults.compactOn',
                'current': f"存在字段: {agent_defaults['compactOn']}",
                'expected': '应删除此字段',
                'severity': 'MEDIUM'
            })
    except (KeyError, AttributeError):
        pass
    
    # 4. 输出诊断结果
    print(f"\n📋 发现 {len(issues)} 个问题:")
    print("-" * 60)
    
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. [{issue['severity']}] {issue['path']}")
        print(f"   当前: {issue['current']}")
        print(f"   期望: {issue['expected']}")
    
    # 5. 配置结构概览
    print("\n📊 配置结构概览:")
    print("-" * 60)
    
    def print_structure(obj, prefix="", max_depth=3, current_depth=0):
        if current_depth >= max_depth:
            return
        
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)) and len(str(v)) > 50:
                    print(f"{prefix}{k}: {type(v).__name__} ({len(v)} items)")
                    if current_depth < max_depth - 1:
                        print_structure(v, prefix + "  ", max_depth, current_depth + 1)
                else:
                    print(f"{prefix}{k}: {repr(v)[:50]}")
    
    print_structure(config, max_depth=2)
    
    # 6. 安全建议
    print("\n🛡️ 安全建议:")
    print("-" * 60)
    if issues:
        print("1. 生成修复diff，不直接修改文件")
        print("2. 验证修复方案符合官方schema")
        print("3. 人工审核批准后执行")
        print("4. 执行前备份原文件")
        print("5. 验证修改后重启gateway（高危操作）")
    else:
        print("✅ 配置诊断未发现问题")
    
    return len(issues) == 0

if __name__ == "__main__":
    try:
        diagnose_openclaw_config()
    except Exception as e:
        print(f"❌ 诊断过程中出错: {e}")
        sys.exit(1)