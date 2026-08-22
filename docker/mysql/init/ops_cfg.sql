-- ops_cfg 表结构与初始化数据
-- 表结构依据 app/models/ops_model.py 的 OpsCfg ORM 映射。
-- 物理表无数据库主键（ORM 使用逻辑复合键），此处保持一致不加 PRIMARY KEY。
-- 示例数据为脱敏值，不代表真实生产配置；可按需替换。

CREATE TABLE IF NOT EXISTS `ops_cfg` (
  `type`        VARCHAR(8)   NOT NULL,
  `machine_tag` VARCHAR(32)  NOT NULL,
  `group`       VARCHAR(32)  NOT NULL,
  `key`         VARCHAR(128) NOT NULL,
  `value`       TEXT,
  `work_time`   TEXT,
  `status`      INT,
  KEY `idx_ops_cfg_type_status_group` (`type`, `status`, `group`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- OS 配置：每组机器一条 os 类型配置
-- Process 配置：key 为进程二进制名，value 为配置文件名（供 cfg/value 子串匹配）
INSERT INTO `ops_cfg` (`type`, `machine_tag`, `group`, `key`, `value`, `work_time`, `status`) VALUES
('os',      'op-service-01', 'op',      'os',              'os',                 '09:00:00-23:00:00',                          1),
('os',      'fut-col-01',    'op',      'os',              'os',                 '09:00:00-23:00:00',                          1),
('os',      'fut-col-02',    'op',      'os',              'os',                 '09:00:00-23:00:00',                          1),
('os',      'algo-cta-01',   'algo00x', 'os',              'os',                 '09:00:00-23:00:00',                          1),
('os',      'algo-fut-01',   'algo00x', 'os',              'os',                 '08:00:00-23:00:00',                          1),
('os',      'etf-build-01',  'etf',     'os',              'os',                 '09:00:00-16:00:00',                          1),
('process', 'op-service-01', 'op',      'python',          'col_service_ops',    '00:10:00-23:50:00',                          1),
('process', 'fut-col-01',    'op',      'tlBinTradeLite',  'col1',               '08:50:00-15:30:00;20:50:00-23:55:00',        1),
('process', 'fut-col-02',    'op',      'tlBinFutLite',    'col2',               '08:50:00-15:30:00;20:50:00-23:55:00',        1),
('process', 'algo-cta-01',   'algo00x', 'tlBinTradeLite',  'sys_simnow.yaml',    '09:00:00-15:00:00;21:00:00-23:50:00',        1),
('process', 'algo-fut-01',   'algo00x', 'tlBinFutLite',    'sys_demo.yaml',      '09:00:00-15:00:00;21:00:00-23:50:00',        1),
('process', 'etf-build-01',  'etf',     'python',          'build_etf1.yaml',    '09:30:00-15:00:00',                          1);
