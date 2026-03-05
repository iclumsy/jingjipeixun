"""
路由包（Routes Package）。

本包包含所有 HTTP 路由定义，每个模块对应一个 Flask Blueprint：
    - auth_routes.py        : 管理后台登录/登出认证路由
    - student_routes.py     : 学员信息 CRUD、审核、附件上传等核心业务路由
    - export_routes.py      : 学员数据 Excel 导出路由
    - miniprogram_routes.py : 微信小程序登录认证路由
    - file_routes.py        : 学员附件文件静态服务路由
    - config_routes.py      : 作业类别等配置数据查询路由
"""
