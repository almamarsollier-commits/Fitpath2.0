ALTER TABLE ejercicios
ADD COLUMN wger_id INTEGER;

ALTER TABLE ejercicios
ADD COLUMN imagen_url TEXT;

ALTER TABLE ejercicios
ADD COLUMN video_url TEXT;

CREATE UNIQUE INDEX idx_ejercicios_wger_id
ON ejercicios (wger_id)
WHERE wger_id IS NOT NULL;
