#!/usr/bin/env python3
"""
智能密度监控 - Token使用追踪器
用于估算和追踪OpenClaw会话的token使用效率
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
import re

class TokenTracker:
    def __init__(self, openclaw_path="/home/summer/.openclaw"):
        self.openclaw_path = Path(openclaw_path)
        self.logs_path = self.openclaw_path / "logs"
        self.agents_path = self.openclaw_path / "agents"
        self.workspace_path = self.openclaw_path / "workspace"
        
        # 创建追踪文件
        self.tracker_file = self.workspace_path / "token_usage.json"
        self.ensure_tracker()
        
    def ensure_tracker(self):
        """确保追踪文件存在"""
        if not self.tracker_file.exists():
            initial_data = {
                "created": datetime.now().isoformat(),
                "daily_summary": {},
                "session_history": [],
                "efficiency_metrics": {
                    "avg_tokens_per_request": 0,
                    "batch_efficiency_score": 0,
                    "compression_ratio": 1.0
                }
            }
            self.save_data(initial_data)
            
    def save_data(self, data):
        """保存数据到追踪文件"""
        with open(self.tracker_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def load_data(self):
        """加载追踪数据"""
        with open(self.tracker_file, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def estimate_token_usage(self, text):
        """估算文本的token使用量（基于近似规则）"""
        # 简单估算：1 token ≈ 4个英文字符或1个中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(re.findall(r'[a-zA-Z0-9\s\p{P}]', text))
        
        # 估算token数
        estimated_tokens = chinese_chars + english_chars // 4
        return max(10, estimated_tokens)  # 最小10个token
        
    def analyze_recent_activity(self, hours=1):
        """分析最近的活动"""
        data = self.load_data()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 检查最近的日志文件
        token_estimates = []
        
        # 扫描agent目录中的session文件
        for agent_dir in self.agents_path.iterdir():
            if agent_dir.is_dir():
                sessions_dir = agent_dir / "sessions"
                if sessions_dir.exists():
                    # 简单估算：每个session文件代表一次交互
                    session_files = list(sessions_dir.glob("*.json"))
                    for session_file in session_files:
                        try:
                            with open(session_file, 'r', encoding='utf-8') as f:
                                session_data = json.load(f)
                                # 估算消息内容的token
                                if isinstance(session_data, dict):
                                    messages = session_data.get("messages", [])
                                    for msg in messages:
                                        if isinstance(msg, dict) and "content" in msg:
                                            content = msg["content"]
                                            if content:
                                                tokens = self.estimate_token_usage(str(content))
                                                token_estimates.append({
                                                    "agent": agent_dir.name,
                                                    "tokens": tokens,
                                                    "timestamp": datetime.fromtimestamp(
                                                        session_file.stat().st_mtime
                                                    ).isoformat()
                                                })
                        except:
                            continue
        
        # 计算今日摘要
        today_estimates = [e for e in token_estimates 
                          if e["timestamp"].startswith(today)]
        
        total_today = sum(e["tokens"] for e in today_estimates)
        
        # 更新数据
        data["daily_summary"][today] = {
            "estimated_tokens": total_today,
            "interactions": len(today_estimates),
            "avg_tokens_per_interaction": total_today / max(1, len(today_estimates))
        }
        
        # 添加最近会话历史
        recent_sessions = sorted(token_estimates, 
                               key=lambda x: x["timestamp"], 
                               reverse=True)[:10]
        data["session_history"] = recent_sessions
        
        # 计算效率指标
        if today_estimates:
            avg_tokens = total_today / len(today_estimates)
            data["efficiency_metrics"]["avg_tokens_per_request"] = avg_tokens
            
            # 批处理效率评分（假设：token越少，效率越高）
            # 基准：平均500 tokens/请求
            batch_efficiency = max(0, 100 - (avg_tokens / 5))
            data["efficiency_metrics"]["batch_efficiency_score"] = min(100, batch_efficiency)
        
        self.save_data(data)
        return data
        
    def calculate_id_score_contribution(self):
        """计算token效率对ID-Score的贡献"""
        data = self.load_data()
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today in data["daily_summary"]:
            daily = data["daily_summary"][today]
            efficiency = data["efficiency_metrics"]
            
            # token效率评分（0-100）
            avg_tokens = efficiency["avg_tokens_per_request"]
            if avg_tokens > 0:
                # 理想值：200 tokens/请求，超过则扣分
                token_score = max(0, 100 - (avg_tokens - 200) / 5)
            else:
                token_score = 50  # 默认分数
                
            # 批处理效率评分
            batch_score = efficiency["batch_efficiency_score"]
            
            return {
                "token_efficiency": min(100, token_score),
                "batch_efficiency": min(100, batch_score),
                "overall_contribution": (token_score + batch_score) / 2
            }
        return {"token_efficiency": 50, "batch_efficiency": 50, "overall_contribution": 50}
        
    def generate_report(self):
        """生成token使用报告"""
        data = self.analyze_recent_activity()
        contribution = self.calculate_id_score_contribution()
        
        today = datetime.now().strftime("%Y-%m-%d")
        daily = data["daily_summary"].get(today, {})
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "daily_summary": daily,
            "efficiency_metrics": data["efficiency_metrics"],
            "id_score_contribution": contribution,
            "recommendations": []
        }
        
        # 生成优化建议
        avg_tokens = data["efficiency_metrics"]["avg_tokens_per_request"]
        if avg_tokens > 500:
            report["recommendations"].append("减少单次请求token使用：考虑消息压缩")
        if avg_tokens < 100:
            report["recommendations"].append("增加信息密度：合并相关请求")
            
        return report

def main():
    """主函数"""
    tracker = TokenTracker()
    
    print("开始智能密度token分析...")
    report = tracker.generate_report()
    
    print(f"\n📊 Token使用报告")
    print(f"时间: {report['timestamp']}")
    
    if report['daily_summary']:
        daily = report['daily_summary']
        print(f"今日估算token数: {daily.get('estimated_tokens', 0):.0f}")
        print(f"交互次数: {daily.get('interactions', 0)}")
        print(f"平均token/请求: {daily.get('avg_tokens_per_interaction', 0):.1f}")
    
    print(f"\n🎯 效率指标")
    print(f"批处理效率评分: {report['efficiency_metrics']['batch_efficiency_score']:.1f}/100")
    
    print(f"\n📈 ID-Score贡献")
    print(f"Token效率: {report['id_score_contribution']['token_efficiency']:.1f}/100")
    print(f"批处理效率: {report['id_score_contribution']['batch_efficiency']:.1f}/100")
    print(f"总体贡献: {report['id_score_contribution']['overall_contribution']:.1f}/100")
    
    if report['recommendations']:
        print(f"\n💡 优化建议")
        for rec in report['recommendations']:
            print(f"  • {rec}")
    
    # 保存报告到文件
    report_file = tracker.workspace_path / "token_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ 报告已保存到: {report_file}")

if __name__ == "__main__":
    main()