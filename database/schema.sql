-- USERS (authentification)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) CHECK (role IN ('admin','agent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

--------------------------------------------------

-- WILAYA
CREATE TABLE wilaya (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10),
    name_fr VARCHAR(100),
    name_ar VARCHAR(100),
    name_en VARCHAR(100)
);

--------------------------------------------------

-- COMMUNE
CREATE TABLE commune (
    id SERIAL PRIMARY KEY,
    name_fr VARCHAR(100),
    name_ar VARCHAR(100),
    postal_code INTEGER,
    wilaya_id INTEGER REFERENCES wilaya(id)
);

--------------------------------------------------

-- DELIVERY AGENTS
CREATE TABLE delivery_agents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id),
    company_id INTEGER,
    phone VARCHAR(20)
);

--------------------------------------------------

-- DELIVERY
CREATE TABLE delivery (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES delivery_agents(id),
    status VARCHAR(50),
    scheduled_date DATE
);

--------------------------------------------------

-- ADDRESS VERIFICATION
CREATE TABLE address_verification (
    id SERIAL PRIMARY KEY,
    raw_address TEXT,
    normalized_address TEXT,
    confidence_score FLOAT,
    match_details JSONB,
    detected_entities JSONB,
    risk_flags JSONB,
    commune_id INTEGER REFERENCES commune(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

--------------------------------------------------

-- VERIFICATION RECORD
CREATE TABLE verification_record (
    id SERIAL PRIMARY KEY,
    address_verification_id INTEGER REFERENCES address_verification(id),
    verification_date DATE,
    result_score FLOAT
);

--------------------------------------------------

-- FEEDBACK
CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    delivery_id INTEGER REFERENCES delivery(id),
    outcome VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

--------------------------------------------------

-- API LOGS
CREATE TABLE api_logs (
    id SERIAL PRIMARY KEY,
    endpoint VARCHAR(100),
    request_time TIMESTAMP,
    status_code INTEGER
);