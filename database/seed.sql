-- WILAYA
INSERT INTO wilaya (code,name_fr,name_ar,name_en)
VALUES
('16','Alger','الجزائر','Algiers'),
('31','Oran','وهران','Oran'),
('25','Constantine','قسنطينة','Constantine');

-- COMMUNE
INSERT INTO commune (name_fr,name_ar,postal_code,wilaya_id)
VALUES
('Bab Ezzouar','باب الزوار',16024,1),
('Bir Mourad Rais','بئر مراد رايس',16000,1),
('Es Senia','السانية',31000,2);

-- USERS
INSERT INTO users (name,email,password_hash,role)
VALUES
('Admin System','admin@algeo.com','hash_admin','admin'),
('Ahmed Benali','agent@algeo.com','hash_agent','agent');