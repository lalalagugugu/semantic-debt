CREATE DATABASE IF NOT EXISTS retail;
CREATE USER IF NOT EXISTS cube IDENTIFIED WITH no_password;
GRANT SELECT ON retail.* TO cube;
-- readonly=2 permits driver settings (join_use_nulls), while forbidding writes.
ALTER USER cube SETTINGS readonly = 2, max_execution_time = 120, max_memory_usage = 17179869184, max_result_rows = 2000000, result_overflow_mode = 'throw';
