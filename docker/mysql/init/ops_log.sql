-- ops_log 表结构与初始化数据
-- 表结构依据 app/models/ops_model.py 的 OpsLog ORM 映射。
-- log_id 为自增主键；machine_tag 和 level 有独立索引（与 ORM index=True 一致）。
-- 示例数据为脱敏值，不代表真实生产日志。

CREATE TABLE IF NOT EXISTS `ops_log` (
  `log_id`      BIGINT       NOT NULL AUTO_INCREMENT,
  `event_id`    VARCHAR(64) COLLATE utf8mb4_bin,
  `date`        VARCHAR(16),
  `machine_tag` VARCHAR(32),
  `log_name`    VARCHAR(255),
  `level`       VARCHAR(8),
  `log`         TEXT,
  `update_time` VARCHAR(32),
  PRIMARY KEY (`log_id`),
  UNIQUE KEY `uq_ops_log_event_id` (`event_id`),
  KEY `idx_ops_log_machine_tag` (`machine_tag`),
  KEY `idx_ops_log_level` (`level`),
  KEY `idx_ops_log_date_level_log_id` (`date`, `level`, `log_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 脱敏日志：机器标签和日志路径均为示例值
INSERT INTO `ops_log` (`log_id`, `date`, `machine_tag`, `log_name`, `level`, `log`, `update_time`) VALUES
(1, '20260729', 'fut-col-01',    '/var/log/omms/fut_col1_20260729_am.log', 'info',  '[20260729 08:40:01.887327][info] [tlBinTradeLite] START, version=v2601.0.1, args=task_col1.yaml/null, cpu=-1, multi=null, freq=2000',  '20260729 08:40:05'),
(2, '20260729', 'fut-col-02',    '/var/log/omms/fut_col2_20260729_am.log', 'info',  '[20260729 08:40:02.149609][info] [tlBinFutLite] START, version=v2601.0.1, args=task_col2.yaml/null, cpu=-1, multi=null, freq=2000',     '20260729 08:40:05'),
(3, '20260729', 'op-service-01', '/var/log/omms/col_service_ops.log',      'error', '[20260729 09:28:03.824112][error] [login_monitor] OnRspUserLogin, errorID=3 errorMsg=invalid_login',                                  '20260729 09:28:08'),
(4, '20260729', 'op-service-01', '/var/log/omms/col_service_ops.log',      'warn',  '[20260729 09:28:08.573][col_ops_service.py:91][WARN] recv msg_type=log, machine_tag=fut-col-01, status=error',                     '20260729 09:28:24'),
(5, '20260729', 'algo-cta-01',   '/var/log/omms/cta_20260729_am.log',       'info',  '[20260729 09:40:41.000000][info] [tlBinTradeLite] START, version=v2601.0.1, args=sys_simnow.yaml/null, cpu=-1, multi=null, freq=2000',  '20260729 09:40:45'),
(6, '20260729', 'etf-build-01',  '/var/log/omms/etf_build_20260729.log',    'error', '[20260729 09:40:39.000000][error] [etf_builder] connection timeout, retry=3',                                                     '20260729 09:40:42');

-- 设置自增起始值，避免后续上游写入与示例 ID 冲突
ALTER TABLE `ops_log` AUTO_INCREMENT = 100;
