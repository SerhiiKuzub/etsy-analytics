CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;

-- Довідник товарів
CREATE TABLE core.listings (
    listing_id      BIGINT PRIMARY KEY,
    title           TEXT,
    price           NUMERIC(10,2),
    currency        CHAR(3),
    created_at      TIMESTAMP,
    tags            TEXT[],
    views           INT,
    favorites       INT
);

-- Замовлення
CREATE TABLE core.orders (
    order_id        BIGINT PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    buyer_country   CHAR(2),
    buyer_hash      TEXT,
    total_amount    NUMERIC(10,2),
    shipping_amount NUMERIC(10,2),
    currency        CHAR(3)
);

-- Позиції замовлення
CREATE TABLE core.order_items (
    order_id        BIGINT REFERENCES core.orders(order_id),
    listing_id      BIGINT REFERENCES core.listings(listing_id),
    quantity        INT,
    unit_price      NUMERIC(10,2),
    PRIMARY KEY (order_id, listing_id)
);

-- Собівартість (заповнює власник магазину)
CREATE TABLE core.product_costs (
    listing_id      BIGINT PRIMARY KEY REFERENCES core.listings(listing_id),
    unit_cost       NUMERIC(10,2) NOT NULL,
    updated_at      DATE
);

-- Комісії Etsy
CREATE TABLE core.fees (
    fee_id          BIGSERIAL PRIMARY KEY,
    order_id        BIGINT REFERENCES core.orders(order_id),
    fee_type        TEXT,
    amount          NUMERIC(10,2),
    created_at      TIMESTAMP
);
