#!/usr/bin/env python3
"""
OpenClaw修复预览脚本
安全预览修复效果，不进行任何实际修改
"""

import json
import os
import copy

def preview_fixes():
    """预览修复效果"""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    
    print("👀 OpenClaw修复效果预览")
    print("=" * 60)
    
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return
    
    # 加载当前配置
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            current_config = json.load(f)
        print(f"✅ 当前配置加载成功")
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return
    
    # 创建副本用于预览
    preview_config = copy.deepcopy(current_config)
    
    print("\n📋 预览将应用的修复:")
    print("-" * 60)
    
    # 预览修复1: models.providers.ollama.models
    try:
        models = preview_config.setdefault('models', {})
        providers = models.setdefault('providers', {})
        ollama_provider = providers.setdefault('ollama', {})
        
        current_models = ollama_provider.get('models')
        if current_models is None:
            print("1. models.providers.ollama.models: [创建] 空数组 []")
            ollama_provider['models'] = []
        elif isinstance(current_models, dict):
            print(f"1. models.providers.ollama.models: [修复] 对象 → 数组 []")
            ollama_provider['models'] = []
        elif not isinstance(current_models, list):
            print(f"1. models.providers.ollama.models: [修复] {type(current_models).__name__} → 数组 []")
            ollama_provider['models'] = []
        else:
            print("1. models.providers.ollama.models: [无变化] 已为数组")
    except Exception as e:
        print(f"1. models.providers.ollama.models: [错误] {e}")
    
    # 预览修复2: 删除冗余字段
    try:
        agents = preview_config.get('agents', {})
        defaults = agents.get('defaults', {})
        agent_models = defaults.get('models', {})
        
        removed_count = 0
        for model_key, model_data in list(agent_models.items()):
            if 'ollama/' in model_key and isinstance(model_data, dict):
                original_fields = list(model_data.keys())
                if 'description' in model_data:
                    del model_data['description']
                if 'taskLayer' in model_data:
                    del model_data['taskLayer']
                
                if list(model_data.keys()) != original_fields:
                    removed_count += 1
        
        if removed_count > 0:
            print(f"2. agents.defaults.models.ollama/*: [修复] 删除 {removed_count} 个模型的冗余字段")
        else:
            print("2. agents.defaults.models.ollama/*: [无变化] 无冗余字段")
    except Exception as e:
        print(f"2. agents.defaults.models.ollama/*: [错误] {e}")
    
    # 预览修复3: 删除 compactOn
    try:
        agents = preview_config.get('agents', {})
        defaults = agents.get('defaults', {})
        
        if 'compactOn' in defaults:
            print(f"3. agents.defaults.compactOn: [删除] 值={defaults['compactOn']}")
            del defaults['compactOn']
        else:
            print("3. agents.defaults.compactOn: [无变化] 字段不存在")
    except Exception as e:
        print(f"3. agents.defaults.compactOn: [错误] {e}")
    
    # 显示关键部分的对比
    print("\n🔍 关键部分对比:")
    print("-" * 60)
    
    # 对比 ollama.models
    print("models.providers.ollama.models:")
    try:
        current_val = current_config.get('models', {}).get('providers', {}).get('ollama', {}).get('models', 'MISSING')
        preview_val = preview_config.get('models', {}).get('providers', {}).get('ollama', {}).get('models', 'MISSING')
        print(f"  当前: {current_val!r} ({type(current_val).__name__})")
        print(f"  修复后: {preview_val!r} ({type(preview_val).__name__})")
    except:
        print("  无法对比")
    
    # 对比 agents.defaults.compactOn
    print("\nagents.defaults.compactOn:")
    try:
        current_val = current_config.get('agents', {}).get('defaults', {}).get('compactOn', 'MISSING')
        preview_val = preview_config.get('agents', {}).get('defaults', {}).get('compactOn', 'MISSING')
        print(f"  当前: {current_val!r}")
        print(f"  修复后: {preview_val!r}")
    except:
        print("  无法对比")
    
    # 对比 ollama 模型字段
    print("\nagents.defaults.models.ollama 模型字段:")
    try:
        current_models = current_config.get('agents', {}).get('defaults', {}).get('models', {})
        preview_models = preview_config.get('agents', {}).get('defaults', {}).get('models', {})
        
        ollama_keys = [k for k in current_models if 'ollama/' in k]
        for key in ollama_keys[:2]:  # 只显示前2个
            current_fields = list(current_models.get(key, {}).keys())
            preview_fields = list(preview_models.get(key, {}).keys())
            print(f"  {key}:")
            print(f"    当前字段: {current_fields}")
            print(f"    修复后字段: {preview_fields}")
    except:
        print("  无法对比")
    
    # 验证修复后的配置
    print("\n🧪 修复后配置验证:")
    print("-" * 60)
    
    try:
        # 模拟验证
        config_str = json.dumps(preview_config, indent=2, ensure_ascii=False)
        
        issues = []
        
        # 检查 ollama.models 是否为数组
        ollama_models = preview_config.get('models', {}).get('providers', {}).get('ollama', {}).get('models')
        if ollama_models is not None and not isinstance(ollama_models, list):
            issues.append("models.providers.ollama.models 不是数组")
        
        # 检查 compactOn 是否已删除
        if 'compactOn' in preview_config.get('agents', {}).get('defaults', {}):
            issues.append("agents.defaults.compactOn 仍然存在")
        
        if issues:
            print("❌ 预览验证发现问题:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✅ 预览验证通过")
            
    except Exception as e:
        print(f"⚠️  验证过程中出错: {e}")
    
    # 执行建议
    print("\n🎯 执行建议:")
    print("-" * 60)
    print("1. 预览验证通过后，可执行安全修复:")
    print("   python3 /home/summer/.openclaw/workspace/apply_fix_safe.py")
    print("\n2. 修复后验证:")
    print("   openclaw config")
    print("\n3. 重启gateway (高危操作):")
    print("   openclaw gateway restart")
    print("\n⚠️  注意: 所有操作都有风险，请确保有备份")

if __name__ == "__main__":
    preview_fixes()