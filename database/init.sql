CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wechat_openid VARCHAR(128) UNIQUE NOT NULL,
    wechat_unionid VARCHAR(128),
    nickname VARCHAR(64),
    avatar_url TEXT,
    gender VARCHAR(8),
    birthday DATE,
    height_cm DECIMAL(5,1),
    weight_kg DECIMAL(5,1),
    fitness_goal VARCHAR(16),
    daily_calorie_target INT,
    allergies TEXT[],
    dietary_restrictions TEXT[],
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 食物识别记录表
CREATE TABLE food_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    image_url TEXT,
    meal_type VARCHAR(10),
    foods JSONB NOT NULL DEFAULT '[]',
    total_calories INT NOT NULL,
    total_protein_g DECIMAL(6,1),
    total_fat_g DECIMAL(6,1),
    total_carbs_g DECIMAL(6,1),
    recorded_at DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 食谱表（预置数据）
CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    category VARCHAR(20),
    meal_type VARCHAR(10),
    cooking_method VARCHAR(20),
    prep_time_min INT,
    cook_time_min INT,
    difficulty VARCHAR(10),
    image_url TEXT,
    ingredients JSONB NOT NULL DEFAULT '[]',
    steps TEXT[],
    nutrition_per_serving JSONB NOT NULL DEFAULT '{}',
    serving_size VARCHAR(30),
    tags TEXT[],
    suitable_goal VARCHAR(16),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 每日食谱推荐记录表
CREATE TABLE recipe_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    recipe_id UUID REFERENCES recipes(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    meal_type VARCHAR(10) NOT NULL,
    is_accepted BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, date, meal_type, recipe_id)
);

-- 健身打卡表
CREATE TABLE fitness_checkins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    exercise_type VARCHAR(30) NOT NULL,
    duration_min INT NOT NULL,
    intensity INT CHECK(intensity BETWEEN 1 AND 10),
    calories_burned INT,
    notes TEXT,
    image_url TEXT,
    checkin_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 用户 API Key 配置表
CREATE TABLE user_api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    deepseek_api_key TEXT,
    deepseek_base_url TEXT,
    qwen_api_key TEXT,
    qwen_base_url TEXT,
    tavily_api_key TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_food_records_user_date ON food_records(user_id, recorded_at);
CREATE INDEX idx_recipe_recommendations_user_date ON recipe_recommendations(user_id, date);
CREATE INDEX idx_fitness_checkins_user_date ON fitness_checkins(user_id, checkin_date);
