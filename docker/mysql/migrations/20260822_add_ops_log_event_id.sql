-- 现有环境升级：MQ 日志使用稳定事件 ID 去重；历史日志保持 NULL。
ALTER TABLE `ops_log`
  ADD COLUMN `event_id` VARCHAR(64) COLLATE utf8mb4_bin NULL AFTER `log_id`,
  ADD UNIQUE KEY `uq_ops_log_event_id` (`event_id`);
