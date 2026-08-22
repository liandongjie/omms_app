-- 现有环境升级：连续覆盖日志日期、级别筛选及单级别倒序分页。
ALTER TABLE `ops_log`
  ADD KEY `idx_ops_log_date_level_log_id` (`date`, `level`, `log_id`);
