#!/usr/bin/env python3
"""
OpenClaw Schema提取工具 - 从npm包提取schema信息
零风险：仅分析本地缓存文件，不调用任何API
"""

import re
import json
import os

def extract_agentconfig_schema():
    """从dist文件中提取AgentConfig schema"""
    dist_file = "/tmp/openclaw-src/package/dist/index-B3LIgyiT.js"
    
    print("📚 提取OpenClaw Schema信息")
    print("=" * 60)
    
    if not os.path.exists(dist_file):
        print(f"❌ dist文件不存在: {dist_file}")
        print("提示：npm包可能未缓存，需要从npm registry获取")
        return None
    
    try:
        with open(dist_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 1. 查找defaultAgentConfig (包含默认值)
        default_config_match = re.search(r'defaultAgentConfig\s*[=:]\s*(\{[\s\S]*?\})', content)
        if default_config_match:
            print("✅ 找到defaultAgentConfig定义")
            # 尝试提取可读部分
            config_block = default_config_match.group(1)
            lines = config_block.split('\n')
            print("\n🔧 AgentConfig默认值:")
            print("-" * 40)
            for line in lines[:20]:  # 限制输出长度
                line = line.strip()
                if line and not line.startswith('/') and not line.startswith('*'):
                    print(f"  {line}")
            print("  ...")
        else:
            print("⚠️  未找到defaultAgentConfig")
        
        # 2. 查找compactOn及相关字段的使用
        print("\n🔍 查找关键配置字段:")
        print("-" * 40)
        
        key_fields = [
            'compactOn',
            'bootstrapMaxChars', 
            'bootstrapTotalMaxChars',
            'contextPruning',
            'contextKeep',
            'imageMaxDimensionPx',
            'models',
            'thinkingType'
        ]
        
        for field in key_fields:
            # 查找字段定义模式
            pattern = rf'{field}\b\s*[?:]\s*([^,\n}}]+)'
            matches = re.findall(pattern, content)
            if matches:
                # 取第一个有意义的匹配
                for match in matches[:1]:
                    if match.strip() and not match.strip().startswith('/'):
                        print(f"  {field}: {match.strip()}")
        
        # 3. 查找workspaceConfig结构
        workspace_match = re.search(r'workspaceConfig\b[\s\S]{0,500}agents[\s\S]{0,500}\}', content)
        if workspace_match:
            print("\n🏗️  workspaceConfig结构 (片段):")
            print("-" * 40)
            ws_text = workspace_match.group(0)[:300]
            # 清理和格式化
            ws_text = re.sub(r'\s+', ' ', ws_text)
            print(f"  {ws_text[:200]}...")
        
        # 4. 查找Provider配置结构
        print("\n🔌 Provider配置结构:")
        print("-" * 40)
        
        # 查找provider配置示例
        provider_pattern = r'providers\s*[=:]\s*\{[\s\S]{0,300}ollama[\s\S]{0,200}\}'
        provider_match = re.search(provider_pattern, content)
        if provider_match:
            provider_text = provider_match.group(0)
            # 简化显示
            lines = provider_text.split('\n')
            for line in lines[:10]:
                if 'ollama' in line or 'models' in line:
                    print(f"  {line.strip()}")
        
        # 5. 生成schema验证规则
        print("\n📋 Schema验证规则总结:")
        print("-" * 40)
        
        schema_rules = {
            "agents.defaults": {
                "valid_fields": ["workspace", "userTimezone", "list"],
                "notes": "其他字段如compactOn可能仅适用于单agent配置"
            },
            "models.providers.ollama": {
                "models": "应为数组 [] 而非对象 {}",
                "baseUrl": "可选，字符串格式",
                "apiKey": "可选，字符串格式"
            },
            "AgentConfig字段 (单agent用)": {
                "compactOn": "number, 范围 0-1",
                "bootstrapMaxChars": "number, 字符限制",
                "bootstrapTotalMaxChars": "number, 总字符限制", 
                "contextPruning": "object, 包含mode/amount等",
                "contextKeep": "number, 上下文保留数",
                "imageMaxDimensionPx": "number, 图片最大尺寸",
                "models": "Record<string, ModelOptions>"
            }
        }
        
        for section, rules in schema_rules.items():
            print(f"\n{section}:")
            for field, rule in rules.items():
                print(f"  - {field}: {rule}")
        
        return schema_rules
        
    except Exception as e:
        print(f"❌ 提取过程中出错: {e}")
        return None

def validate_against_schema(current_config, schema_rules):
    """根据schema验证当前配置"""
    print("\n🧪 配置验证:")
    print("=" * 60)
    
    issues = []
    
    # 验证agents.defaults
    agent_defaults = current_config.get('agents', {}).get('defaults', {})
    valid_agent_fields = schema_rules["agents.defaults"]["valid_fields"]
    
    for field in agent_defaults:
        if field not in valid_agent_fields:
            issues.append({
                'path': f'agents.defaults.{field}',
                'issue': f'可能无效的字段，有效字段为: {valid_agent_fields}',
                'action': '检查是否应移至单agent配置或删除'
            })
    
    # 验证ollama provider
    ollama_config = current_config.get('models', {}).get('providers', {}).get('ollama', {})
    if 'models' in ollama_config and isinstance(ollama_config['models'], dict):
        issues.append({
            'path': 'models.providers.ollama.models',
            'issue': '应为数组 []',
            'action': '改为空数组 []'
        })
    
    # 输出验证结果
    if issues:
        print(f"❌ 发现 {len(issues)} 个schema违例:")
        for issue in issues:
            print(f"\n  [{issue['path']}]")
            print(f"   问题: {issue['issue']}")
            print(f"   建议: {issue['action']}")
    else:
        print("✅ 配置通过schema验证")
    
    return issues

if __name__ == "__main__":
    schema = extract_agentconfig_schema()
    
    # 可选：加载当前配置进行验证
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    if os.path.exists(config_path) and schema:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
            validate_against_schema(current_config, schema)
        except Exception as e:
            print(f"⚠️  无法验证当前配置: {e}")