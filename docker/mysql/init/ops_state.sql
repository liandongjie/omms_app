-- ops_state 表结构与初始化数据
-- 表结构依据 app/models/ops_model.py 的 OpsState ORM 映射。
-- 上游服务按 (date, type, machine_tag, key, value) 覆盖最新状态，
-- 故使用复合主键支撑 INSERT ... ON DUPLICATE KEY UPDATE 语义。
-- 示例数据为脱敏值；dat 字段使用 JSON 格式（parse_dat 兼容 JSON）。

CREATE TABLE IF NOT EXISTS `ops_state` (
  `date`        VARCHAR(16)  NOT NULL,
  `type`        VARCHAR(8)   NOT NULL,
  `machine_tag` VARCHAR(32)  NOT NULL,
  `key`         VARCHAR(128) NOT NULL,
  `value`       VARCHAR(255) NOT NULL,
  `update_time` VARCHAR(32),
  `dat`         TEXT,
  PRIMARY KEY (`date`, `type`, `machine_tag`, `key`, `value`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- OS 状态：dat 为 JSON 格式的资源指标
INSERT INTO `ops_state` (`date`, `type`, `machine_tag`, `key`, `value`, `update_time`, `dat`) VALUES
('20260729', 'os', 'op-service-01', 'os', 'os', '20260729 09:40:28', '{"cpu": 0.02, "mem": 0.279, "disk": 0.651, "disk_home": 0.651}'),
('20260729', 'os', 'fut-col-01',    'os', 'os', '20260729 09:40:17', '{"cpu": 0.152, "mem": 0.193, "disk": 0.707}'),
('20260729', 'os', 'fut-col-02',    'os', 'os', '20260729 09:40:06', '{"cpu": 0.014, "mem": 0.173, "disk": 0.518, "disk_home": -1}'),
('20260729', 'os', 'algo-cta-01',   'os', 'os', '20260729 09:40:41', '{"cpu": 0.004, "mem": 0.323, "disk": 0.735}'),
('20260729', 'os', 'algo-fut-01',   'os', 'os', '20260729 09:40:12', '{"cpu": 0.719, "mem": 0.093, "disk": 0.155, "disk_home": 0.124}'),
('20260729', 'os', 'etf-build-01',  'os', 'os', '20260729 09:40:39', '{"cpu": 0.248, "mem": 0.139, "disk": 0.409}');

-- 进程状态：value 使用 JSON 数组格式（parse_process_args 兼容）
-- 含 _am.yaml 的 value 供盘次识别（08:00-18:00 选 AM 盘次）
INSERT INTO `ops_state` (`date`, `type`, `machine_tag`, `key`, `value`, `update_time`, `dat`) VALUES
('20260729', 'process', 'op-service-01', '/opt/anaconda3/bin/python', '["lk_strategy_fw.py", "task_col_service_ops.yaml"]',    '20260729 09:40:28', '{"pid": 833196, "pname": "/opt/anaconda3/bin/python", "cpu": 0.003, "mem": 153.5}'),
('20260729', 'process', 'fut-col-01',    './bin/tlBinTradeLite',      '["task_col1.yaml"]',                                    '20260729 09:40:17', '{"pid": 923154, "pname": "./bin/tlBinTradeLite", "cpu": 0.335, "mem": 107.426}'),
('20260729', 'process', 'fut-col-02',    './bin/tlBinFutLite',         '["task_col2.yaml"]',                                    '20260729 09:40:06', '{"pid": 614894, "pname": "./bin/tlBinFutLite", "cpu": 0.006, "mem": 26.227}'),
('20260729', 'process', 'algo-cta-01',   './bin/tlBinTradeLite',      '["sys_simnow.yaml", "user_simnow_20260729_am.yaml"]',   '20260729 09:40:41', '{"pid": 240966, "pname": "./bin/tlBinTradeLite", "cpu": 0.13, "mem": 1776.355, "algo00x_cfg": "24/4", "ord_speed": 20}'),
('20260729', 'process', 'algo-fut-01',   './bin/tlBinFutLite',         '["sys_demo.yaml", "user_demo_20260729_am.yaml"]',       '20260729 09:40:12', '{"pid": 166342, "pname": "./bin/tlBinFutLite", "cpu": 40.001, "mem": 7439.844, "algo00x_cfg": "68/23"}'),
('20260729', 'process', 'etf-build-01',  '/opt/anaconda3/bin/python', '["lk_strategy_fw.py", "task_build_etf1.yaml"]',          '20260729 09:40:39', '{"pid": 664581, "pname": "/opt/anaconda3/bin/python", "cpu": 0.526, "mem": 238.652}');
