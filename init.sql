CREATE TABLE IF NOT EXISTS brti_prices (
    time_raw BIGINT PRIMARY KEY,
    price DECIMAL(18, 2),
    -- Convert epoch to UTC, then to EST/EDT wall-clock.
    -- precision (3) ensures milliseconds are stored/displayed.
    time_est TIMESTAMP(3) GENERATED ALWAYS AS (to_timestamp(time_raw / 1000.0) AT TIME ZONE 'America/New_York') STORED
);

CREATE TABLE IF NOT EXISTS eth_prices (
    time_raw BIGINT PRIMARY KEY,
    price DECIMAL(18, 2),
    -- Convert epoch to UTC, then to EST/EDT wall-clock.
    -- precision (3) ensures milliseconds are stored/displayed.
    time_est TIMESTAMP(3) GENERATED ALWAYS AS (to_timestamp(time_raw / 1000.0) AT TIME ZONE 'America/New_York') STORED
);
