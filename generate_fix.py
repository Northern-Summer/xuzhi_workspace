#!/usr/bin/env python3
"""
OpenClaw修复方案生成器 - 生成安全的diff方案
零风险：仅生成文本，不执行任何修改
"""

import json
import os
import difflib
from datetime import datetime

def generate_fix_proposal():
    """生成修复方案"""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print("🔧 OpenClaw配置修复方案")
    print("=" * 60)
    
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return None
    
    # 1. 加载当前配置
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            current_config = json.load(f)
        print("✅ 当前配置加载成功")
    except Exception as e:
        print(f"❌ 无法加载配置: {e}")
        return None
    
    # 2. 创建修复后的配置副本
    fixed_config = json.loads(json.dumps(current_config))  # 深度复制
    
    # 3. 应用修复规则
    fixes_applied = []
    
    # 修复1: models.providers.ollama.models -> []
    try:
        ollama_models = fixed_config.get('models', {}).get('providers', {}).get('ollama', {}).get('models')
        if ollama_models is not None and isinstance(ollama_models, dict):
            fixed_config['models']['providers']['ollama']['models'] = []
            fixes_applied.append({
                'description': 'models.providers.ollama.models 从对象改为数组',
                'old': '{}',
                'new': '[]',
                'risk': 'LOW'
            })
    except (KeyError, AttributeError):
        pass
    
    # 修复2: 删除 agents.defaults.models.ollama/* 中的冗余字段
    try:
        agent_models = fixed_config.get('agents', {}).get('defaults', {}).get('models', {})
        for model_key in list(agent_models.keys()):
            if 'ollama/' in model_key:
                model_data = agent_models[model_key]
                if 'description' in model_data:
                    del model_data['description']
                if 'taskLayer' in model_data:
                    del model_data['taskLayer']
        
        # 检查是否实际删除了字段
        for model_key in agent_models:
            if 'ollama/' in model_key:
                model_data = agent_models[model_key]
                if 'description' not in model_data and 'taskLayer' not in model_data:
                    fixes_applied.append({
                        'description': f'agents.defaults.models.{model_key} 删除冗余字段',
                        'old': '包含description, taskLayer字段',
                        'new': '空对象 {}',
                        'risk': 'LOW'
                    })
    except (KeyError, AttributeError):
        pass
    
    # 修复3: 删除 agents.defaults.compactOn
    try:
        agent_defaults = fixed_config.get('agents', {}).get('defaults', {})
        if 'compactOn' in agent_defaults:
            old_value = agent_defaults['compactOn']
            del agent_defaults['compactOn']
            fixes_applied.append({
                'description': 'agents.defaults.compactOn 删除无效字段',
                'old': f'compactOn: {old_value}',
                'new': '删除该字段',
                'risk': 'MEDIUM'
            })
        
        # 同时删除其他可能无效的字段
        invalid_fields = ['bootstrapMaxChars', 'bootstrapTotalMaxChars', 'contextPruning', 'imageMaxDimensionPx']
        for field in invalid_fields:
            if field in agent_defaults:
                old_value = agent_defaults[field]
                del agent_defaults[field]
                fixes_applied.append({
                    'description': f'agents.defaults.{field} 删除可能无效字段',
                    'old': f'{field}: {json.dumps(old_value)[:50]}',
                    'new': '删除该字段',
                    'risk': 'MEDIUM'
                })
    except (KeyError, AttributeError):
        pass
    
    # 4. 输出修复摘要
    print(f"\n📋 应用 {len(fixes_applied)} 个修复:")
    print("-" * 60)
    
    for i, fix in enumerate(fixes_applied, 1):
        print(f"{i}. [{fix['risk']}] {fix['description']}")
        print(f"   原值: {fix['old']}")
        print(f"   新值: {fix['new']}")
    
    # 5. 生成diff
    print("\n🔍 生成修复diff:")
    print("-" * 60)
    
    current_json = json.dumps(current_config, indent=2, ensure_ascii=False)
    fixed_json = json.dumps(fixed_config, indent=2, ensure_ascii=False)
    
    current_lines = current_json.splitlines()
    fixed_lines = fixed_json.splitlines()
    
    diff = difflib.unified_diff(
        current_lines, 
        fixed_lines,
        fromfile='当前配置',
        tofile='修复后配置',
        lineterm=''
    )
    
    diff_lines = list(diff)
    if len(diff_lines) > 20:
        print("\n".join(diff_lines[:20]))
        print("... (完整diff见下方)")
    else:
        print("\n".join(diff_lines))
    
    # 6. 完整diff保存到文件
    diff_file = "/home/summer/.openclaw/workspace/fix_proposal.diff"
    with open(diff_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(diff_lines))
    print(f"\n📄 完整diff已保存到: {diff_file}")
    
    # 7. 修复后配置预览
    print("\n👀 修复后关键部分预览:")
    print("-" * 60)
    
    # 显示agents.defaults部分
    agent_defaults_fixed = fixed_config.get('agents', {}).get('defaults', {})
    print("agents.defaults:")
    for k, v in agent_defaults_fixed.items():
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:100]}")
    
    # 显示ollama provider部分
    ollama_fixed = fixed_config.get('models', {}).get('providers', {}).get('ollama', {})
    print("\nmodels.providers.ollama:")
    for k, v in ollama_fixed.items():
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:100]}")
    
    # 8. 安全执行计划
    print("\n🛡️ 安全执行计划:")
    print("-" * 60)
    print("1. 备份原文件:")
    print(f"   cp {config_path} {backup_path}")
    print("")
    print("2. 应用修复:")
    print(f"   python3 -c \"import json; data=json.load(open('{config_path}')); "
          f"[应用修复逻辑]; json.dump(data, open('{config_path}', 'w'), indent=2, ensure_ascii=False)\"")
    print("")
    print("3. 验证新配置:")
    print(f"   python3 -c \"import json; json.load(open('{config_path}')); print('✅ JSON验证通过')\"")
    print("")
    print("4. 重启gateway (高危操作):")
    print("   openclaw gateway restart")
    print("")
    print("5. 验证服务:")
    print("   openclaw gateway status")
    print("")
    print("6. 回滚方案:")
    print(f"   cp {backup_path} {config_path}")
    print("   openclaw gateway restart")
    
    # 9. 生成应用脚本（可选）
    apply_script = f'''#!/usr/bin/env python3
"""
OpenClaw配置修复应用脚本
高危操作：必须人工审核批准后执行
"""

import json
import os
import shutil
from datetime import datetime

def apply_fix():
    config_path = "{config_path}"
    backup_path = f"{{config_path}}.backup.{{datetime.now().strftime('%Y%m%d_%H%M%S')}}"
    
    print("⚠️ 高危操作：应用配置修复")
    print("=" * 60)
    print(f"配置文件: {{config_path}}")
    print(f"备份文件: {{backup_path}}")
    print("")
    print("确认执行？(yes/no): ", end='')
    
    response = input().strip().lower()
    if response != 'yes':
        print("❌ 操作取消")
        return
    
    # 1. 备份
    print("📦 备份原文件...")
    shutil.copy2(config_path, backup_path)
    print(f"✅ 备份完成: {{backup_path}}")
    
    # 2. 加载并修复
    print("🔧 加载并修复配置...")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 应用修复（与generate_fix.py相同逻辑）
    {generate_fix_logic()}
    
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
        print(f"❌ JSON验证失败: {{e}}")
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
'''
    
    apply_script_path = "/home/summer/.openclaw/workspace/apply_fix.py"
    with open(apply_script_path, 'w', encoding='utf-8') as f:
        f.write(apply_script)
    print(f"\n📜 应用脚本已生成: {apply_script_path}")
    print("   注意：必须人工审核批准后执行")
    
    return fixes_applied

def generate_fix_logic():
    """生成修复逻辑代码（用于应用脚本）"""
    return '''
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
    '''

if __name__ == "__main__":
    generate_fix_proposal()