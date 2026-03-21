#!/usr/bin/env python3
"""
恢复Minimax-2.7为默认模型配置
同时修复OpenClaw配置问题
"""

import json
import os
import shutil
from datetime import datetime

def restore_minimax_default():
    """恢复Minimax-2.7为默认模型"""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    
    print("🔧 恢复Minimax-2.7为默认模型")
    print("=" * 60)
    
    # 1. 备份
    backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"📦 创建备份: {backup_path}")
    shutil.copy2(config_path, backup_path)
    
    # 2. 加载配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 3. 确认Minimax模型ID
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
        print("❌ 未找到Minimax模型配置")
        return False
    
    print(f"✅ 找到Minimax模型: {minimax_model_id}")
    
    # 4. 设置Minimax为默认模型
    models_config = config.setdefault('models', {})
    defaults = models_config.setdefault('defaults', {})
    
    # 当前默认配置
    current_default = defaults.get('model', '未设置')
    
    # 更新为Minimax
    defaults['model'] = minimax_model_id
    
    print(f"🔁 默认模型更新: {current_default} → {minimax_model_id}")
    
    # 5. 同时修复之前发现的配置问题（可选）
    print("\n🔧 修复其他配置问题...")
    
    # 修复1: models.providers.ollama.models 确保为数组
    try:
        ollama_provider = config.get('models', {}).get('providers', {}).get('ollama', {})
        if not isinstance(ollama_provider.get('models'), list):
            ollama_provider['models'] = []
            print("✅ models.providers.ollama.models: 设置为空数组 []")
    except:
        pass
    
    # 修复2: 删除 agents.defaults.compactOn
    try:
        agent_defaults = config.get('agents', {}).get('defaults', {})
        if 'compactOn' in agent_defaults:
            del agent_defaults['compactOn']
            print("✅ agents.defaults.compactOn: 删除无效字段")
    except:
        pass
    
    # 6. 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 配置已更新: {config_path}")
    
    # 7. 验证配置
    print("\n🧪 验证配置...")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            json.load(f)
        print("✅ JSON语法验证通过")
        
        # 验证默认模型已设置
        final_config = json.load(open(config_path, 'r'))
        final_default = final_config.get('models', {}).get('defaults', {}).get('model')
        if final_default == minimax_model_id:
            print(f"✅ 默认模型验证通过: {final_default}")
        else:
            print(f"⚠️  默认模型可能未正确设置: {final_default}")
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        print("正在恢复备份...")
        shutil.copy2(backup_path, config_path)
        print("✅ 已恢复备份")
        return False
    
    # 8. 下一步建议
    print("\n🎯 下一步建议:")
    print("-" * 60)
    print("1. 验证配置: openclaw config")
    print("2. 重启gateway: openclaw gateway restart (高危)")
    print("3. 测试Minimax模型响应")
    print("")
    print("📊 资源管理提醒:")
    print("- Minimax-2.7 (云端): 重要推理、规划、设计")
    print("- Ollama模型 (本地): 配置验证、基础任务")
    print("- 避免无意义POST消耗")
    
    return True

def main():
    """主函数"""
    print("⚠️ 高危操作：修改OpenClaw默认模型配置")
    print("确认执行？(输入 'yes' 继续): ", end='')
    
    if input().strip().lower() != 'yes':
        print("❌ 操作取消")
        return False
    
    return restore_minimax_default()

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ 操作被用户中断")
        exit(1)
    except Exception as e:
        print(f"❌ 未预期的错误: {e}")
        exit(1)