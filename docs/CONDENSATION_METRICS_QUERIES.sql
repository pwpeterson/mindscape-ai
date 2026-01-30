-- ============================================================================
-- Mem0 Condensation Effectiveness Metrics
-- Table: model_proxy_api_requests
-- ============================================================================

-- Query 1: Daily Token Usage Trends
-- Track daily average token usage to see condensation impact
SELECT 
    DATE(timestamp) as date,
    model,
    COUNT(*) as request_count,
    ROUND(AVG(prompt_tokens)::numeric, 0) as avg_prompt_tokens,
    ROUND(AVG(completion_tokens)::numeric, 0) as avg_completion_tokens,
    ROUND(AVG(total_cost_usd)::numeric, 6) as avg_cost,
    ROUND(SUM(total_cost_usd)::numeric, 4) as total_cost,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY prompt_tokens) as median_prompt_tokens,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prompt_tokens) as p95_prompt_tokens,
    MAX(prompt_tokens) as max_prompt_tokens
FROM model_proxy_api_requests
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE(timestamp), model
ORDER BY date DESC, model;

-- Query 2: Before/After Condensation Comparison
-- Replace '2026-01-23' with your actual enable date
WITH before AS (
    SELECT 
        'Before' as period,
        COUNT(*) as requests,
        ROUND(AVG(prompt_tokens)::numeric, 0) as avg_prompt_tokens,
        ROUND(AVG(completion_tokens)::numeric, 0) as avg_completion_tokens,
        ROUND(AVG(total_cost_usd)::numeric, 6) as avg_cost,
        ROUND(SUM(total_cost_usd)::numeric, 4) as total_cost,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prompt_tokens) as p95_prompt_tokens,
        MAX(prompt_tokens) as max_prompt_tokens
    FROM model_proxy_api_requests
    WHERE timestamp < '2026-01-23'::timestamptz
      AND timestamp >= '2026-01-23'::timestamptz - INTERVAL '7 days'
),
after AS (
    SELECT 
        'After' as period,
        COUNT(*) as requests,
        ROUND(AVG(prompt_tokens)::numeric, 0) as avg_prompt_tokens,
        ROUND(AVG(completion_tokens)::numeric, 0) as avg_completion_tokens,
        ROUND(AVG(total_cost_usd)::numeric, 6) as avg_cost,
        ROUND(SUM(total_cost_usd)::numeric, 4) as total_cost,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prompt_tokens) as p95_prompt_tokens,
        MAX(prompt_tokens) as max_prompt_tokens
    FROM model_proxy_api_requests
    WHERE timestamp >= '2026-01-23'::timestamptz
      AND timestamp < '2026-01-23'::timestamptz + INTERVAL '7 days'
)
SELECT * FROM before
UNION ALL
SELECT * FROM after;

-- Query 3: Condensation Effectiveness by Type
-- Track rules injection, code JIT, and context condensation separately
SELECT 
    DATE(timestamp) as date,
    model,
    COUNT(*) as total_requests,
    -- Rules injection stats
    COUNT(*) FILTER (WHERE (metadata->>'rules_injected')::boolean = true) as rules_injected_count,
    ROUND(AVG((metadata->>'rules_tokens')::int) FILTER (WHERE metadata->>'rules_tokens' IS NOT NULL)::numeric, 0) as avg_rules_tokens,
    -- Code JIT stats
    COUNT(*) FILTER (WHERE (metadata->>'code_jit_injected')::boolean = true) as code_jit_count,
    ROUND(AVG((metadata->>'code_jit_tokens')::int) FILTER (WHERE metadata->>'code_jit_tokens' IS NOT NULL)::numeric, 0) as avg_code_jit_tokens,
    -- Context condensation stats
    COUNT(*) FILTER (WHERE (metadata->>'context_condensed')::boolean = true) as condensed_count,
    ROUND(AVG((metadata->>'context_tokens_saved')::int) FILTER (WHERE metadata->>'context_tokens_saved' IS NOT NULL)::numeric, 0) as avg_tokens_saved,
    -- Overall metrics
    ROUND(AVG(prompt_tokens)::numeric, 0) as avg_prompt_tokens,
    ROUND(AVG(total_cost_usd)::numeric, 6) as avg_cost
FROM model_proxy_api_requests
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE(timestamp), model
ORDER BY date DESC;

-- Query 4: Message-Level Token Analysis
-- Compare token usage per message before/after
SELECT 
    DATE(timestamp) as date,
    model,
    COUNT(*) as requests,
    ROUND(AVG(message_count)::numeric, 1) as avg_messages,
    ROUND(AVG(prompt_tokens)::numeric, 0) as avg_prompt_tokens,
    ROUND(AVG(prompt_tokens::DECIMAL / NULLIF(message_count, 0))::numeric, 0) as avg_tokens_per_message,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY message_count) as p95_messages,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prompt_tokens) as p95_prompt_tokens
FROM model_proxy_api_requests
WHERE timestamp >= NOW() - INTERVAL '14 days'
  AND message_count > 0
GROUP BY DATE(timestamp), model
ORDER BY date DESC;

-- Query 5: Cost Savings Analysis
-- Calculate actual cost savings from condensation
WITH daily_costs AS (
    SELECT 
        DATE(timestamp) as date,
        ROUND(SUM(total_cost_usd)::numeric, 4) as daily_cost,
        ROUND(AVG(prompt_tokens)::numeric, 0) as avg_prompt_tokens,
        COUNT(*) as request_count
    FROM model_proxy_api_requests
    WHERE timestamp >= NOW() - INTERVAL '30 days'
    GROUP BY DATE(timestamp)
)
SELECT 
    date,
    daily_cost,
    avg_prompt_tokens,
    request_count,
    LAG(daily_cost) OVER (ORDER BY date) as previous_day_cost,
    ROUND((daily_cost - LAG(daily_cost) OVER (ORDER BY date))::numeric, 4) as day_over_day_change,
    ROUND(((daily_cost - LAG(daily_cost) OVER (ORDER BY date)) / NULLIF(LAG(daily_cost) OVER (ORDER BY date), 0) * 100)::numeric, 1) as pct_change
FROM daily_costs
ORDER BY date DESC;

-- Query 6: Top Cost Requests (Find Optimization Targets)
-- Identify the most expensive requests
SELECT 
    request_id,
    timestamp,
    model,
    prompt_tokens,
    completion_tokens,
    total_tokens,
    ROUND(total_cost_usd::numeric, 4) as cost_usd,
    message_count,
    prompt_char_count,
    duration_ms,
    status_code,
    metadata->>'rules_injected' as rules_injected,
    metadata->>'context_condensed' as context_condensed
FROM model_proxy_api_requests
WHERE timestamp >= NOW() - INTERVAL '7 days'
ORDER BY total_cost_usd DESC
LIMIT 50;

-- Query 7: Hourly Usage Patterns
-- Identify peak usage times and token consumption
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    model,
    COUNT(*) as request_count,
    ROUND(AVG(prompt_tokens)::numeric, 0) as avg_prompt_tokens,
    ROUND(SUM(total_cost_usd)::numeric, 4) as total_cost_usd,
    ROUND(AVG(duration_ms)::numeric, 0) as avg_latency_ms
FROM model_proxy_api_requests
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', timestamp), model
ORDER BY hour DESC, model;

-- Query 8: Condensation ROI Calculator
-- Calculate return on investment for condensation
WITH condensation_stats AS (
    SELECT 
        COUNT(*) as total_requests,
        COUNT(*) FILTER (WHERE (metadata->>'context_condensed')::boolean = true) as condensed_requests,
        AVG(prompt_tokens) FILTER (WHERE (metadata->>'context_condensed')::boolean = true) as avg_tokens_condensed,
        AVG(prompt_tokens) FILTER (WHERE (metadata->>'context_condensed')::boolean = false) as avg_tokens_not_condensed,
        AVG((metadata->>'context_tokens_saved')::int) FILTER (WHERE metadata->>'context_tokens_saved' IS NOT NULL) as avg_tokens_saved,
        SUM(total_cost_usd) as total_cost
    FROM model_proxy_api_requests
    WHERE timestamp >= NOW() - INTERVAL '7 days'
)
SELECT 
    total_requests,
    condensed_requests,
    ROUND((condensed_requests::DECIMAL / total_requests * 100)::numeric, 1) as condensation_rate_pct,
    ROUND(avg_tokens_condensed::numeric, 0) as avg_tokens_condensed,
    ROUND(avg_tokens_not_condensed::numeric, 0) as avg_tokens_not_condensed,
    ROUND(avg_tokens_saved::numeric, 0) as avg_tokens_saved_per_request,
    ROUND(((avg_tokens_not_condensed - avg_tokens_condensed) / NULLIF(avg_tokens_not_condensed, 0) * 100)::numeric, 1) as token_reduction_pct,
    ROUND(total_cost::numeric, 4) as total_cost_usd,
    ROUND((avg_tokens_saved * condensed_requests * 0.000005)::numeric, 4) as estimated_savings_usd
FROM condensation_stats;

-- Query 9: Error Rate Monitoring
-- Ensure condensation doesn't break requests
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE status_code >= 400) as error_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status_code >= 400) / NULLIF(COUNT(*), 0), 2) as error_rate_pct,
    COUNT(*) FILTER (WHERE status_code = 400) as bad_request_errors,
    COUNT(*) FILTER (WHERE status_code = 429) as rate_limit_errors,
    COUNT(*) FILTER (WHERE status_code >= 500) as server_errors,
    ROUND(AVG(duration_ms)::numeric, 0) as avg_latency_ms
FROM model_proxy_api_requests
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- Query 10: Use Built-in Views
-- The migration created useful views
SELECT * FROM model_proxy_cost_summary
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY date DESC;

SELECT * FROM model_proxy_hourly_usage
WHERE hour >= NOW() - INTERVAL '7 days'
ORDER BY hour DESC;

SELECT * FROM model_proxy_performance;
