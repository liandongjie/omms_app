# -*- coding: utf-8 -*-
"""pytest 全局装配。

单测全部通过 Fake 服务/依赖覆盖注入数据，不连接真实 MySQL；
这里在导入任何应用模块前固定测试环境，避免本机未启动 MySQL 时
pytest 因数据库 fail-fast 直接失败。
"""
import os

os.environ.setdefault("ENVIRONMENT", "testing")
