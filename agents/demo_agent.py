"""
haibala · M3 · agents/demo_agent.py
===================================
【这一课：一个"真实可运行"的 CLI agent（用于证明驱动机制）】
它读一个任务文件，把结果写到 stdout（被 CLIWorker 以文件方式捕获）。
这样我们就能验证：supervisor 能**真正启动一个子进程 agent、传任务、拿结果**，
而不只是 mock。你以后把 cmd 换成 codex/dsh 等真命令即可，机制完全一样。
"""
import sys

def main():
    task_file = sys.argv[1]
    task = open(task_file, encoding="utf-8").read()
    # 模拟一个真实 agent "干了活" 并输出结果
    result = (
        "# demo-agent 产物\n"
        "收到任务：%s\n\n"
        "完成内容(模拟)：\n"
        "1) 已按需求实现功能\n"
        "2) 单元测试通过\n"
        "3) 输出可复用、有文档\n" % task[:80]
    )
    sys.stdout.write(result)

if __name__ == "__main__":
    main()
