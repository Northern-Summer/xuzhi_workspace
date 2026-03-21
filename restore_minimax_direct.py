#!/usr/bin/env python3
"""
直接修复：恢复Minimax-2.7为默认模型
已收到用户确认，跳过交互
"""

import json
import os
import shutil
from datetime import datetime

def restore_minimax_direct():
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    
    print("🔧 执行Minimax默认模型修复")
    print("=" * 60)
    
    # 1. 备份
    backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"📦 创建备份: {backup_path}")
    shutil.copy2(config_path, backup_path)
    
    # 2. 加载配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 3. 查找Minimax模型ID
    minimax_model_id = None
    providers = config.get('models', {}).get('providers', {})
    
    for provider_name, provider_config in providers.items():
        models = provider_config.get('models', {})
        for model_id, model_config in models.items():
            if 'minimax' in model_id.lower():
                minimax_model_id = model_id
                break
        if minimax_model_id:
            break
    
    if not minimax_model_id:
        # 尝试从其他部分查找
        for provider_name, provider_config in providers.items():
            if 'minimax' in provider_name.lower():
                models = provider_config.get('models', {})
                if models:
                    minimax_model_id = list(models.keys())[0]
                    break
    
    if not minimax_model_id:
        print("❌ 未找到Minimax模型，可能配置不同")
        return False
    
    print(f"✅ 找到Minimax模型: {minimax_model_id}")
    
    # 4. 确保models.defaults结构存在
    models_config = config.setdefault('models', {})
    defaults = models_config.setdefault('defaults', {})
    
    # 当前状态
    current_default = defaults.get('model', '未设置')
    print(f"📊 当前默认模型: {current_default}")
    
    # 5. 更新为Minimax
    defaults['model'] = minimax_model_id
    print(f"🔁 更新默认模型: {minimax_model_id}")
    
    # 6. 同时修复已知配置问题
    print("\n🔧 修复其他配置问题...")
    
    # 修复ollama.models数组问题
    try:
        ollama_provider = config.get('models', {}).get('providers', {}).get('ollama', {})
        if not isinstance(ollama_provider.get('models'), list):
            ollama_provider['models'] = []
            print("✅ models.providers.ollama.models: 设置为空数组 []")
    except Exception as e:
        print(f"⚠️  ollama.models修复失败: {e}")
    
    # 删除agents.defaults.compactOn
    try:
        agent_defaults = config.get('agents', {}).get('defaults', {})
        if 'compactOn' in agent_defaults:
            del agent_defaults['compactOn']
            print("✅ agents.defaults.compactOn: 删除无效字段")
    except Exception as e:
        print(f"⚠️  compactOn删除失败: {e}")
    
    # 7. 保存配置
    print(f"\n💾 保存配置到: {config_path}")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    # 8. 验证
    print("\n🧪 验证配置...")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            json.load(f)
        print("✅ JSON语法验证通过")
        
        # 验证默认模型
        final_config = json.load(open(config_path, 'r'))
        final_default = final_config.get('models', {}).get('defaults', {}).get('model')
        
        if final_default == minimax_model_id:
            print(f"✅ 默认模型验证通过: {final_default}")
        else:
            print(f"⚠️  默认模型设置不一致: 期望={minimax_model_id}, 实际={final_default}")
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        print("正在恢复备份...")
        shutil.copy2(backup_path, config_path)
        print("✅ 已恢复备份")
        return False
    
    print("\n🎯 修复完成!")
    print("=" * 60)
    print(f"备份文件: {backup_path}")
    print(f"默认模型: {minimax_model_id}")
    print("\n下一步: 重启gateway服务应用更改")
    
    return True

if __name__ == "__main__":
    try:
        print("已收到用户确认，开始执行修复...")
        success = restore_minimax_direct()
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        exit(1)