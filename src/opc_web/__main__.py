# -*- coding: utf-8 -*-
"""入口：python run.py / python -m opc_web / console script 共用。
   python -m opc_web roles list|add  角色管理子命令。"""
import os
import sys
import threading
import webbrowser

from . import bootstrap, config, roles, scheduler, server


def _roles_cli(args):
    """角色管理：list（默认）/ add --name .. --duty .. [--position ..] [--type ..] [--dry]。"""
    if args and args[0] == 'add':
        kv = {}
        for i in range(1, len(args), 2):
            kv[args[i].lstrip('-')] = args[i + 1] if i + 1 < len(args) else ''
        r = roles.add_role(
            kv.get('name', '新角色'), kv.get('duty', '待补充职责'),
            kv.get('position', '一句话定位'), kv.get('type', '业务'),
            dry='--dry' in args)
        print('新增角色：%s %s' % (r['no'], r['name']))
        print('  角色卡: %s' % r['cardPath'])
        print('  作业区: %s' % r['sbRoot'])
        return
    for no, name in roles.role_files():
        print('%s %s' % (no, name))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'roles':
        _roles_cli(sys.argv[2:])
        return
    # 捆绑分发（PyInstaller 打包）：exe 旁 _dsh/ 内置 dsh 运行时（node + @deepseek-ai/dsh），
    # 把其加入 PATH，使 shutil.which("dsh") 命中内置 dsh，实现"开箱即用"免装 dsh
    _dsh = config.BASE / "_dsh"
    if _dsh.is_dir():
        os.environ["PATH"] = str(_dsh) + os.pathsep + os.environ.get("PATH", "")
    bootstrap.bootstrap()
    for line in bootstrap.BOOT_LOG:
        print('  · ' + line)
    threading.Thread(target=scheduler.auto_pilot, daemon=True).start()
    srv = server.create_server()
    url = 'http://%s:%d' % (config.HOST, config.PORT)
    print('OPC 控制台（opc-web）已启动 → ' + url)
    print('  根目录: %s（自动 批阅台/工作区/知识库）· 调度: 台账有待派任务即生成【调度指令】待常驻主会话 R1（subagent 派发）' % config.ROOT)
    webbrowser.open(url)      # 在这里开浏览器，端口才跟得上配置（启动脚本写死过 8901）
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

