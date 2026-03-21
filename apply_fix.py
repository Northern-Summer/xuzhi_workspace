#!/usr/bin/env python3
"""
OpenClaw配置修复应用脚本
高危操作：必须人工审核批准后执行
"""

import json
import os
import shutil
from datetime import datetime

def apply_fix():
    config_path = "/home/summer/.openclaw/openclaw.json"
    backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print("⚠️ 高危操作：应用配置修复")
    print("=" * 60)
    print(f"配置文件: {config_path}")
    print(f"备份文件: {backup_path}")
    print("")
    print("确认执行？(yes/no): ", end='')
    
    response = input().strip().lower()
    if response != 'yes':
        print("❌ 操作取消")
        return
    
    # 1. 备份
    print("📦 备份原文件...")
    shutil.copy2(config_path, backup_path)
    print(f"✅ 备份完成: {backup_path}")
    
    # 2. 加载并修复
    print("🔧 加载并修复配置...")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 应用修复（与generate_fix.py相同逻辑）
    
    # 修复1: models.providers.ollama.models -> []
    try:
        ollama_models = config.get('models', {}).get('providers', {}).get('ollama', {}).get('models')
        if ollama_models is not None and isinstance(ollama_models, dict):
            config['models']['providers']['ollama']['models'] = []
            print("✅ models.providers.ollama.models: {} -> []")
    except (KeyError, AttributeError):
        pass
    
    # 修复2: 删除 agents.defaults.models.ollama/* 中的冗余字段
    try:
        agent_models = config.get('agents', {}).get('defaults', {}).get('models', {})
        for model_key in list(agent_models.keys()):
            if 'ollama/' in model_key:
                model_data = agent_models[model_key]
                if 'description' in model_data:
                    del model_data['description']
                if 'taskLayer' in model_data:
                    del model_data['taskLayer']
        print("✅ 删除 ollama 模型的冗余字段")
    except (KeyError, AttributeError):
        pass
    
    # 修复3: 删除 agents.defaults 中的无效字段
    try:
        agent_defaults = config.get('agents', {}).get('defaults', {})
        invalid_fields = ['compactOn', 'bootstrapMaxChars', 'bootstrapTotalMaxChars', 'contextPruning', 'imageMaxDimensionPx']
        deleted = []
        for field in invalid_fields:
            if field in agent_defaults:
                del agent_defaults[field]
                deleted.append(field)
        if deleted:
            print(f"✅ 删除无效字段: {', '.join(deleted)}")
    except (KeyError, AttributeError):
        pass
    
    
    # 3. 保存修复后的配置
    print("💾 保存修复后的配置...")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("✅ 配置已保存")
    
    # 4. 验证
    print("🧪 验证新配置...")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            json.load(f)
        print("✅ JSON验证通过")
    except Exception as e:
        print(f"❌ JSON验证失败: {e}")
        print("正在恢复备份...")
        shutil.copy2(backup_path, config_path)
        print("✅ 已恢复备份")
        return
    
    print("")
    print("🎯 修复完成！")
    print("")
    print("下一步：手动重启gateway服务")
    print("命令: openclaw gateway restart")

if __name__ == "__main__":
    apply_fix()
