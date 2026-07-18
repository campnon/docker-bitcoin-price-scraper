-- Create OHLC Table
CREATE TABLE IF NOT EXISTS btc_ohlc (
    period_date DATE,
    period_type VARCHAR(10), -- 'DAILY', 'WEEKLY', 'MONTHLY'
    open DECIMAL(18, 2),
    high DECIMAL(18, 2),
    low DECIMAL(18, 2),
    close DECIMAL(18, 2),
    PRIMARY KEY (period_date, period_type)
);

-- Function to Aggregate Data
CREATE OR REPLACE FUNCTION update_ohlc_from_brti() RETURNS void AS $$
BEGIN
    -- Daily Aggregation
    INSERT INTO btc_ohlc (period_date, period_type, open, high, low, close)
    SELECT 
        (time_est)::DATE as period,
        'DAILY',
        (array_agg(price ORDER BY time_est ASC))[1],
        MAX(price),
        MIN(price),
        (array_agg(price ORDER BY time_est DESC))[1]
    FROM brti_prices
    GROUP BY (time_est)::DATE
    ON CONFLICT (period_date, period_type) DO UPDATE 
    SET high = EXCLUDED.high, 
        low = EXCLUDED.low, 
        close = EXCLUDED.close;
        
    -- Weekly Aggregation (Start of week)
    INSERT INTO btc_ohlc (period_date, period_type, open, high, low, close)
    SELECT 
        date_trunc('week', time_est)::DATE as period,
        'WEEKLY',
        (array_agg(price ORDER BY time_est ASC))[1],
        MAX(price),
        MIN(price),
        (array_agg(price ORDER BY time_est DESC))[1]
    FROM brti_prices
    GROUP BY date_trunc('week', time_est)::DATE
    ON CONFLICT (period_date, period_type) DO UPDATE 
    SET high = EXCLUDED.high, 
        low = EXCLUDED.low, 
        close = EXCLUDED.close;

    -- Monthly Aggregation
    INSERT INTO btc_ohlc (period_date, period_type, open, high, low, close)
    SELECT 
        date_trunc('month', time_est)::DATE as period,
        'MONTHLY',
        (array_agg(price ORDER BY time_est ASC))[1],
        MAX(price),
        MIN(price),
        (array_agg(price ORDER BY time_est DESC))[1]
    FROM brti_prices
    GROUP BY date_trunc('month', time_est)::DATE
    ON CONFLICT (period_date, period_type) DO UPDATE 
    SET high = EXCLUDED.high, 
        low = EXCLUDED.low, 
        close = EXCLUDED.close;
END;
$$ LANGUAGE plpgsql;
