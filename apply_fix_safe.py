#!/usr/bin/env python3
"""
OpenClaw配置安全修复脚本 - 修正版本
严格遵循最佳工程实践，仅修复明确无效字段
高危操作：必须人工审核批准后执行
"""

import json
import os
import shutil
import sys
from datetime import datetime

def get_config_path():
    """获取配置路径，支持不同用户"""
    return os.path.expanduser("~/.openclaw/openclaw.json")

def backup_config(config_path):
    """创建配置备份"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{config_path}.backup.{timestamp}"
    
    print(f"📦 创建备份...")
    try:
        shutil.copy2(config_path, backup_path)
        print(f"✅ 备份完成: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return None

def load_config(config_path):
    """安全加载配置"""
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ 配置加载成功: {config_path}")
        return config
    except json.JSONDecodeError as e:
        print(f"❌ JSON语法错误: {e}")
        return None
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return None

def save_config(config, config_path):
    """安全保存配置"""
    try:
        # 首先写入临时文件
        temp_path = f"{config_path}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        # 验证临时文件
        with open(temp_path, 'r', encoding='utf-8') as f:
            json.load(f)
        
        # 替换原文件
        shutil.move(temp_path, config_path)
        print(f"✅ 配置保存成功: {config_path}")
        return True
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

def apply_safe_fixes(config):
    """应用安全修复 - 仅修复明确无效的字段"""
    fixes_applied = []
    
    print("\n🔧 应用安全修复...")
    
    # 修复1: 确保 models.providers.ollama.models 存在且为数组
    try:
        models = config.setdefault('models', {})
        providers = models.setdefault('providers', {})
        ollama_provider = providers.setdefault('ollama', {})
        
        current_models = ollama_provider.get('models')
        if current_models is None:
            # 字段不存在，需要创建
            ollama_provider['models'] = []
            fixes_applied.append("models.providers.ollama.models: 创建空数组 []")
        elif isinstance(current_models, dict):
            # 字段存在但是对象，改为数组
            ollama_provider['models'] = []
            fixes_applied.append("models.providers.ollama.models: 对象 {} → 数组 []")
        elif not isinstance(current_models, list):
            # 字段存在但类型错误
            ollama_provider['models'] = []
            fixes_applied.append(f"models.providers.ollama.models: 类型 {type(current_models).__name__} → 数组 []")
        else:
            print("✅ models.providers.ollama.models 已为数组，无需修改")
    except Exception as e:
        print(f"⚠️  修复ollama.models时出错: {e}")
    
    # 修复2: 删除 agents.defaults.models.ollama/* 中的冗余字段
    try:
        agents = config.get('agents', {})
        defaults = agents.get('defaults', {})
        agent_models = defaults.get('models', {})
        
        removed_count = 0
        for model_key, model_data in list(agent_models.items()):
            if 'ollama/' in model_key and isinstance(model_data, dict):
                original_size = len(str(model_data))
                # 仅删除明确冗余的字段
                if 'description' in model_data:
                    del model_data['description']
                if 'taskLayer' in model_data:
                    del model_data['taskLayer']
                
                if len(str(model_data)) != original_size:
                    removed_count += 1
        
        if removed_count > 0:
            fixes_applied.append(f"删除 {removed_count} 个ollama模型的冗余字段 (description, taskLayer)")
    except Exception as e:
        print(f"⚠️  删除冗余字段时出错: {e}")
    
    # 修复3: 仅删除明确无效的 agents.defaults.compactOn
    try:
        agents = config.get('agents', {})
        defaults = agents.get('defaults', {})
        
        if 'compactOn' in defaults:
            del defaults['compactOn']
            fixes_applied.append("agents.defaults.compactOn: 删除无效字段")
        else:
            print("✅ agents.defaults.compactOn 不存在，无需操作")
    except Exception as e:
        print(f"⚠️  删除compactOn时出错: {e}")
    
    # 输出修复摘要
    if fixes_applied:
        print("\n📋 应用的修复:")
        for fix in fixes_applied:
            print(f"  ✅ {fix}")
    else:
        print("\n📋 未应用任何修复")
    
    return len(fixes_applied) > 0

def validate_fixed_config(config):
    """验证修复后的配置"""
    print("\n🧪 验证修复后配置...")
    
    try:
        # 基本验证
        config_str = json.dumps(config, indent=2, ensure_ascii=False)
        
        # 检查关键修复
        issues = []
        
        # 1. 检查 ollama.models 是否为数组
        ollama_models = config.get('models', {}).get('providers', {}).get('ollama', {}).get('models')
        if ollama_models is not None and not isinstance(ollama_models, list):
            issues.append("models.providers.ollama.models 仍不是数组")
        
        # 2. 检查 agents.defaults.compactOn 是否已删除
        if 'compactOn' in config.get('agents', {}).get('defaults', {}):
            issues.append("agents.defaults.compactOn 仍然存在")
        
        # 3. 检查 ollama 模型是否有冗余字段
        agent_models = config.get('agents', {}).get('defaults', {}).get('models', {})
        for model_key, model_data in agent_models.items():
            if 'ollama/' in model_key and isinstance(model_data, dict):
                if 'description' in model_data or 'taskLayer' in model_data:
                    issues.append(f"agents.defaults.models.{model_key} 仍有冗余字段")
        
        if issues:
            print("❌ 验证发现的问题:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✅ 配置验证通过")
            return True
            
    except Exception as e:
        print(f"❌ 验证过程中出错: {e}")
        return False

def main():
    """主执行函数"""
    print("🔧 OpenClaw配置安全修复脚本")
    print("=" * 60)
    
    config_path = get_config_path()
    print(f"配置文件: {config_path}")
    
    # 检查文件存在性
    if not os.path.exists(config_path):
        print("❌ 配置文件不存在，无法修复")
        return False
    
    # 人工确认
    print("\n⚠️ 高危操作警告:")
    print("1. 将修改OpenClaw配置文件")
    print("2. 将创建备份")
    print("3. 需要验证新配置")
    print("4. 可能需要重启gateway服务")
    print("\n确认执行修复？(输入 'yes' 继续): ", end='')
    
    response = input().strip().lower()
    if response != 'yes':
        print("❌ 操作取消")
        return False
    
    # 二次确认
    print("\n⚠️ 二次确认：")
    print("这可能会影响OpenClaw服务运行")
    print("确认继续？(输入 'confirm' 继续): ", end='')
    
    response = input().strip().lower()
    if response != 'confirm':
        print("❌ 操作取消")
        return False
    
    # 1. 备份
    backup_path = backup_config(config_path)
    if not backup_path:
        return False
    
    # 2. 加载配置
    config = load_config(config_path)
    if config is None:
        return False
    
    # 3. 应用安全修复
    config_modified = apply_safe_fixes(config)
    
    if not config_modified:
        print("\n📋 未进行任何修改，操作完成")
        return True
    
    # 4. 验证修复后的配置
    if not validate_fixed_config(config):
        print("\n❌ 修复后验证失败，恢复备份...")
        try:
            shutil.copy2(backup_path, config_path)
            print(f"✅ 已恢复备份: {backup_path}")
        except Exception as e:
            print(f"❌ 恢复备份失败: {e}")
        return False
    
    # 5. 保存配置
    if not save_config(config, config_path):
        return False
    
    # 6. 最终验证
    print("\n🎯 最终验证...")
    final_config = load_config(config_path)
    if final_config is None:
        return False
    
    # 生成修复摘要
    print("\n" + "=" * 60)
    print("🎉 修复完成!")
    print("=" * 60)
    print(f"📂 原文件: {config_path}")
    print(f"📦 备份文件: {backup_path}")
    print("\n📋 下一步:")
    print("1. 验证配置: openclaw config")
    print("2. 重启gateway: openclaw gateway restart (高危操作)")
    print("3. 检查状态: openclaw gateway status")
    print("\n⚠️ 警告: gateway重启需要权限，可能失败")
    print("   如果重启失败，请手动检查配置")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ 操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}")
        sys.exit(1)